import contextlib
import datetime as dt
import io
import json
import sqlite3
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from agent_cli import (
    PLAN_SCHEMA,
    LocalTools,
    RunResult,
    answer_cache_path,
    apply_pending_writes,
    cached_answer,
    choose_model,
    consolidate_memory,
    estimate_history_tokens,
    finish_run,
    is_sensitive_path,
    post,
    post_stream,
    remember,
    resolve_repo_path,
    routed_model,
    run_agent,
    run_planned,
    store_cached_answer,
    structured_plan,
    summarize_history,
    system_prompt,
    tool_definitions,
    validate_arguments,
)


def _reply(content="", calls=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return {"choices": [{"message": message}]}


def _write_call(path="a.py", content="x = 1\n"):
    return {
        "id": "1",
        "function": {
            "name": "write_file",
            "arguments": json.dumps({"path": path, "content": content}),
        },
    }


class AgentCliSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.tools = LocalTools(self.repo, apply=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_sensitive_file_cannot_be_read_or_written(self):
        (self.repo / ".env").write_text("TOKEN=top-secret\n", encoding="utf-8")
        self.assertIn("denied", self.tools.call("read_file", {"path": ".env"}))
        self.assertIn(
            "denied", self.tools.call("write_file", {"path": ".env", "content": "TOKEN=replaced"})
        )

    def test_write_is_staged_until_confirmation(self):
        result = self.tools.call(
            "write_file", {"path": "src/example.py", "content": "answer = 42\n"}
        )
        target = self.repo / "src" / "example.py"
        self.assertIn("STAGED", result)
        self.assertFalse(target.exists())
        apply_pending_writes(self.tools.pending_writes)
        self.assertEqual(target.read_text(encoding="utf-8"), "answer = 42\n")

    def test_path_escaping_repo_rejected(self):
        with self.assertRaises(ValueError):
            resolve_repo_path(self.repo, "../../../etc/passwd")

    def test_sensitive_path_detection(self):
        self.assertTrue(is_sensitive_path(self.repo, self.repo / ".env"))
        self.assertTrue(is_sensitive_path(self.repo, self.repo / ".npmrc"))
        self.assertTrue(is_sensitive_path(self.repo, self.repo / "secrets.key"))
        self.assertFalse(is_sensitive_path(self.repo, self.repo / "README.md"))
        self.assertTrue(is_sensitive_path(self.repo, self.repo / ".git" / "config"))
        self.assertTrue(is_sensitive_path(self.repo, self.repo / "__pycache__" / "test.pyc"))

    def test_git_status_tool(self):
        result = self.tools.call("git_status", {})
        self.assertIn("exit=", result)

    def test_read_file_tool(self):
        (self.repo / "test.txt").write_text("hello world", encoding="utf-8")
        result = self.tools.call("read_file", {"path": "test.txt"})
        self.assertEqual(result, "hello world")

    def test_search_tool(self):
        (self.repo / "test.py").write_text("def test():\n    pass\n", encoding="utf-8")
        result = self.tools.call("search", {"pattern": "def", "glob": "*.py"})
        self.assertIn("test.py", result)

    def test_dry_run_mode(self):
        dry_tools = LocalTools(self.repo, apply=False)
        result = dry_tools.call("write_file", {"path": "test.txt", "content": "test"})
        self.assertIn("DRY-RUN", result)
        self.assertIn("without --apply", result)

    def test_semantic_search_degrades_when_service_down(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("refused")):
            result = self.tools.call("semantic_search", {"query": "vram"})
        self.assertTrue(result.startswith("ERROR: RAG service unavailable"))

    def test_semantic_search_returns_service_text(self):
        responses = [io.BytesIO(json.dumps(text).encode()) for text in ("indexed", "[0.9] vram.md")]
        with mock.patch("urllib.request.urlopen", side_effect=responses):
            result = self.tools.call("semantic_search", {"query": "vram", "k": 3})
        self.assertIn("vram.md", result)

    def test_semantic_search_reindexes_once_per_run(self):
        def fresh(*_args, **_kwargs):
            return io.BytesIO(json.dumps("ok").encode())

        with mock.patch("urllib.request.urlopen", side_effect=fresh) as opened:
            self.tools.call("semantic_search", {"query": "a"})
            self.tools.call("semantic_search", {"query": "b"})
        urls = [call.args[0].full_url for call in opened.call_args_list]
        self.assertEqual(
            [u.rsplit("/", 1)[-1] for u in urls],
            ["index_sources", "semantic_search", "semantic_search"],
        )

    def test_system_prompt_requires_citations(self):
        self.assertIn("cite", system_prompt("ask", apply=False).lower())

    def test_semantic_search_is_read_only_in_every_mode(self):
        for mode in ("ask", "plan", "agent"):
            names = [t["function"]["name"] for t in tool_definitions(mode)]
            self.assertIn("semantic_search", names)


class AgentFeatureTests(unittest.TestCase):
    PASS = "verification=staged-copy\nexit=0\nok"
    FAIL = "verification=staged-copy\nexit=1\nFAILED a.py::test_x - boom"
    UNRELATED = "verification=staged-copy\nexit=1\nFAILED other/test_old.py::test_y"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        patcher = mock.patch("agent.memory.MEMORY_ENABLED", new=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _agent(self, replies, test_outputs, mode="agent"):
        with (
            mock.patch("agent.loop.post", side_effect=replies) as post,
            mock.patch("agent.tools.LocalTools._run_staged_tests", side_effect=test_outputs),
        ):
            result = run_agent(mode, "task", self.repo, "m", "http://x", apply=False)
        return result, post

    def test_validate_arguments_catches_bad_calls(self):
        self.assertIsNone(validate_arguments("read_file", {"path": "a.py"}, "ask"))
        self.assertIn("unknown tool", validate_arguments("rm_rf", {}, "ask"))
        self.assertIn("missing", validate_arguments("read_file", {}, "ask"))
        self.assertIn("JSON object", validate_arguments("read_file", None, "ask"))
        self.assertIn("must be string", validate_arguments("read_file", {"path": 3}, "ask"))
        self.assertIn(
            "must be integer",
            validate_arguments("semantic_search", {"query": "q", "k": True}, "ask"),
        )
        self.assertIn("unknown tool", validate_arguments("write_file", {}, "ask"))

    def test_malformed_tool_call_is_reported_back_to_the_model(self):
        bad = {"id": "1", "function": {"name": "read_file", "arguments": "{not json"}}
        result, post = self._agent([_reply(calls=[bad]), _reply("done")], [], mode="ask")
        self.assertEqual(result.answer, "done")
        sent = post.call_args_list[-1].args[1]["messages"]
        self.assertTrue(any("JSON object" in str(m.get("content")) for m in sent))

    def test_requests_use_top_level_sampling_fields(self):
        payload = {}
        with mock.patch("agent.ollama._open_chat") as opened:
            opened.return_value.__enter__.return_value = io.BytesIO(b"{}")
            post("http://x", {"model": "m", "messages": []})
            payload = json.loads(opened.call_args.args[0].data)
        self.assertEqual((payload["temperature"], payload["seed"]), (0, 0))
        self.assertNotIn("options", payload)

    def test_model_router_uses_easy_and_hard_models(self):
        self.assertEqual(routed_model("What is this repository for?"), "qwen3.5:4b")
        self.assertEqual(
            routed_model("Debug the API authentication failure and add regression tests."),
            "qwen3:14b",
        )

    def test_choose_model_falls_back_when_route_target_is_unavailable(self):
        with mock.patch("agent.routing._installed_models", return_value={"qwen3:8b"}):
            selected, warning = choose_model(
                "Debug the API authentication failure and add regression tests.",
                "qwen3:8b",
                "http://x",
            )
        self.assertEqual(selected, "qwen3:8b")
        self.assertIn("ollama pull qwen3:14b", warning)

    def test_run_agent_uses_and_audits_routed_model(self):
        with (
            mock.patch("agent.loop.choose_model", return_value=("qwen3.5:4b", None)),
            mock.patch("agent.loop.post", return_value=_reply("simple answer")) as post,
        ):
            run_agent(
                "ask",
                "short question",
                self.repo,
                "qwen3:8b",
                "http://x",
                apply=False,
                auto_route=True,
            )
        self.assertEqual(post.call_args.args[1]["model"], "qwen3.5:4b")

    def test_summarize_history_preserves_recent_messages(self):
        history = [
            {"role": "user", "content": f"question {index} " + "x" * 100}
            if index % 2 == 0
            else {"role": "assistant", "content": f"answer {index} " + "y" * 100}
            for index in range(12)
        ]
        summary = json.dumps({"summary": "Earlier goal: fix RAG."})
        body = json.dumps({"message": {"content": summary}})
        with (
            mock.patch("agent.history.HISTORY_TOKEN_BUDGET", 1),
            mock.patch("urllib.request.urlopen", return_value=io.BytesIO(body.encode())),
        ):
            compacted = summarize_history(history, "qwen3:8b", "http://x")
        self.assertEqual(len(compacted), 1 + 4)
        self.assertIn("untrusted context", compacted[0]["content"])
        self.assertEqual(compacted[1:], history[-4:])
        self.assertLess(estimate_history_tokens(compacted), estimate_history_tokens(history))

    def test_summarize_history_skips_small_history(self):
        history = [{"role": "user", "content": "short"}]
        with (
            mock.patch("agent.history.HISTORY_TOKEN_BUDGET", 100),
            mock.patch("urllib.request.urlopen") as opened,
        ):
            self.assertIs(summarize_history(history, "qwen3:8b", "http://x"), history)
        opened.assert_not_called()

    def test_structured_plan_uses_native_schema_and_formats_sections(self):
        output = json.dumps(
            {
                "summary": "Add bounded cache.",
                "files": ["agent_cli.py"],
                "steps": ["Add storage", "Verify expiry"],
                "tests": ["Run focused tests"],
                "risks": ["Old answers may become stale"],
            }
        )
        body = json.dumps({"message": {"content": output}})
        captured = {}

        def open_request(request, timeout):
            captured["request"] = json.loads(request.data)
            return io.BytesIO(body.encode())

        with mock.patch("urllib.request.urlopen", side_effect=open_request):
            plan = structured_plan("Add a cache", [], "qwen3:8b", "http://x")
        self.assertEqual(captured["request"]["format"], PLAN_SCHEMA)
        self.assertIn("### Affected files", plan)
        self.assertIn("1. Add storage", plan)
        self.assertIn("- Old answers may become stale", plan)

    def test_run_agent_plan_uses_structured_output(self):
        with (
            mock.patch("agent.loop.post", return_value=_reply("draft")),
            mock.patch(
                "agent.loop.structured_plan", return_value="### Steps\n1. Inspect"
            ) as plan_writer,
        ):
            result = run_agent("plan", "task", self.repo, "m", "http://x", False)
        self.assertEqual(result.answer, "### Steps\n1. Inspect")
        self.assertEqual(plan_writer.call_args.args[0], "task")

    def test_memory_only_stores_verified_agent_runs_and_consolidates(self):
        memory = self.repo / "memory"
        old = memory / "2020-01-01.md"
        old.parent.mkdir()
        old.write_text("## old\nTask: unverified\n", encoding="utf-8")
        today = memory / f"{dt.datetime.now(dt.UTC).date().isoformat()}.md"
        today.write_text(
            "## old\nTask: unverified\n\n"
            "## 12:00:00Z agent (model)\nTask: verified\nOutcome: passed\n"
            "Verified: tests passed\n",
            encoding="utf-8",
        )
        with (
            mock.patch("agent.memory.MEMORY_ENABLED", new=True),
            mock.patch("agent.memory.MEMORY_DIR", new=memory),
        ):
            consolidate_memory()
            remember("agent", "m", "question", "answer", verified=True)
        self.assertFalse(old.exists())
        text = today.read_text(encoding="utf-8")
        self.assertNotIn("unverified", text)
        self.assertEqual(text.count("Verified: tests passed"), 2)

    def test_memory_does_not_store_unverified_or_non_agent_runs(self):
        memory = self.repo / "memory"
        with (
            mock.patch("agent.memory.MEMORY_ENABLED", new=True),
            mock.patch("agent.memory.MEMORY_DIR", new=memory),
        ):
            remember("ask", "m", "question", "answer", verified=True)
            remember("agent", "m", "question", "answer", verified=False)
        self.assertFalse(memory.exists())

    def test_semantic_cache_stores_redacted_answer_and_retrieves_similar(self):
        with mock.patch("agent.cache.answer_embedding", return_value=[1.0, 0.0]):
            store_cached_answer(self.repo, "token=secret", "Answer", "http://x")
            answer = cached_answer(self.repo, "similar question", "http://x")
        self.assertEqual(answer, "Answer")
        with contextlib.closing(sqlite3.connect(answer_cache_path(self.repo))) as connection:
            prompt = connection.execute("SELECT prompt FROM answers").fetchone()[0]
        self.assertNotIn("secret", prompt)

    def test_semantic_cache_rejects_low_similarity(self):
        with mock.patch("agent.cache.answer_embedding", side_effect=([1.0, 0.0], [0.0, 1.0])):
            store_cached_answer(self.repo, "first", "Answer", "http://x")
            answer = cached_answer(self.repo, "different", "http://x")
        self.assertIsNone(answer)

    def test_semantic_cache_hit_skips_model_for_ask_mode(self):
        with (
            mock.patch("agent.loop.ANSWER_CACHE_ENABLED", new=True),
            mock.patch("agent.loop.cached_answer", return_value="cached"),
            mock.patch("agent.loop.post") as post,
        ):
            result = run_agent("ask", "question", self.repo, "m", "http://x", False)
        self.assertEqual(result.answer, "cached")
        post.assert_not_called()

    def test_planned_run_can_split_models(self):
        results = [
            RunResult("plan", {}, self.repo / "a.jsonl"),
            RunResult("done", {}, self.repo / "a.jsonl", tests_passed=True),
        ]
        with (
            mock.patch("agent.loop._installed_models", return_value={"qwen3:14b", "qwen3.5:4b"}),
            mock.patch("agent.loop.PLANNER_MODEL", "qwen3:14b"),
            mock.patch("agent.loop.EXECUTOR_MODEL", "qwen3.5:4b"),
            mock.patch("agent.loop.run_agent", side_effect=results) as runner,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            run_planned("task", self.repo, "qwen3:8b", "http://x", False, split_models=True)
        self.assertEqual(runner.call_args_list[0].args[3], "qwen3:14b")
        self.assertEqual(runner.call_args_list[1].args[3], "qwen3.5:4b")

    def test_split_models_fall_back_when_models_are_unavailable(self):
        results = [
            RunResult("plan", {}, self.repo / "a.jsonl"),
            RunResult("done", {}, self.repo / "a.jsonl", tests_passed=True),
        ]
        with (
            mock.patch("agent.loop._installed_models", return_value=set()),
            mock.patch("agent.loop.run_agent", side_effect=results) as runner,
            contextlib.redirect_stderr(io.StringIO()),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            run_planned("task", self.repo, "fallback", "http://x", False, split_models=True)
        self.assertEqual(runner.call_args_list[0].args[3], "fallback")
        self.assertEqual(runner.call_args_list[1].args[3], "fallback")

    def test_unsupported_citation_triggers_one_retry(self):
        search = {
            "id": "1",
            "function": {"name": "semantic_search", "arguments": json.dumps({"query": "vram"})},
        }
        hits = "[0.900] /repo/docs/vram.md (chunk 0)\\nbudget"
        replies = [_reply(calls=[search]), _reply("See [made_up.md]."), _reply("See [vram.md].")]
        with mock.patch("agent.tools.LocalTools._rag_post", return_value=hits):
            result, post = self._agent(replies, [], mode="ask")
        self.assertEqual(result.answer, "See [vram.md].")
        self.assertEqual(post.call_count, 3)

    def test_still_unsupported_citation_is_flagged(self):
        replies = [_reply("See [ghost.md]."), _reply("Still [ghost.md].")]
        result, _ = self._agent(replies, [], mode="ask")
        self.assertIn("unverified citations: ghost.md", result.answer)

    def test_answers_without_citations_are_untouched(self):
        result, post = self._agent([_reply("plain answer")], [], mode="ask")
        self.assertEqual(result.answer, "plain answer")
        self.assertEqual(post.call_count, 1)

    def test_reflection_retries_once_then_passes(self):
        replies = [
            _reply(calls=[_write_call()]),
            _reply("done"),
            _reply(calls=[_write_call(content="x = 2\n")]),
            _reply("fixed"),
        ]
        result, post = self._agent(replies, [self.FAIL, self.PASS])
        self.assertTrue(result.tests_passed)
        self.assertEqual(post.call_count, len(replies))
        sent = post.call_args_list[-1].args[1]["messages"]
        self.assertTrue(any("FAILED" in str(m.get("content")) for m in sent))

    def test_reflection_is_capped_at_one_retry(self):
        replies = [_reply(calls=[_write_call()]), _reply("done"), _reply("still broken")]
        result, post = self._agent(replies, [self.FAIL])
        self.assertIs(result.tests_passed, False)
        self.assertEqual(post.call_count, len(replies))

    def test_unrelated_failing_tests_do_not_trigger_reflection(self):
        replies = [_reply(calls=[_write_call()]), _reply("done")]
        result, post = self._agent(replies, [self.UNRELATED])
        self.assertIsNone(result.tests_passed)
        self.assertEqual(post.call_count, len(replies))

    def test_no_verification_without_staged_writes(self):
        result, _ = self._agent([_reply("just an answer")], [], mode="ask")
        self.assertIsNone(result.tests_passed)

    def test_unverified_ask_run_is_not_written_to_memory(self):
        memory = self.repo / "memory"
        with (
            mock.patch("agent.memory.MEMORY_ENABLED", new=True),
            mock.patch("agent.memory.MEMORY_DIR", new=memory),
            mock.patch("agent.loop.post", return_value=_reply("all good")),
        ):
            run_agent("ask", "check password=hunter2 please", self.repo, "m", "http://x", False)
        self.assertFalse(memory.exists())

    def test_post_stream_assembles_text_and_tool_calls(self):
        lines = [
            {"choices": [{"delta": {"reasoning": "hmm"}}]},
            {"choices": [{"delta": {"content": "Hel"}}]},
            {"choices": [{"delta": {"content": "lo"}}]},
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "c1",
                                    "function": {"name": "search", "arguments": '{"pattern":'},
                                }
                            ]
                        }
                    }
                ]
            },
            {
                "choices": [
                    {"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"x"}'}}]}}
                ]
            },
        ]
        body = "".join(f"data: {json.dumps(line)}\n\n" for line in lines) + "data: [DONE]\n"
        out = io.StringIO()
        stream = io.BytesIO(body.encode())
        with (
            mock.patch("urllib.request.urlopen", return_value=stream),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            reply = post_stream("http://x", {"model": "m", "messages": []})
        message = reply["choices"][0]["message"]
        self.assertEqual(message["content"], "Hello")
        self.assertEqual(out.getvalue(), "Hello\n")
        call = message["tool_calls"][0]
        self.assertEqual((call["id"], call["function"]["name"]), ("c1", "search"))
        self.assertEqual(json.loads(call["function"]["arguments"]), {"pattern": "x"})

    def test_finish_run_without_plan_file_does_not_crash(self):
        result = RunResult("answer", {}, self.repo / ".agent" / "audit" / "a.jsonl")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            finish_run(result, "agent", self.repo, apply=False)
        self.assertIn("answer", out.getvalue())
        self.assertNotIn("Plan saved", out.getvalue())

    def test_unknown_model_gives_actionable_error(self):
        error = urllib.error.HTTPError("http://x", 404, "Not Found", {}, io.BytesIO(b"{}"))
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                post("http://x", {"model": "qwen3.8", "messages": []})
        self.assertIn("qwen3.8", str(caught.exception))
        self.assertIn("ollama list", str(caught.exception))

    def test_streamed_answer_is_not_printed_twice(self):
        result = RunResult("hi", {}, self.repo / "a.jsonl", streamed=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            finish_run(result, "ask", self.repo, apply=False)
        self.assertNotIn("hi\n", out.getvalue().replace("Audit log", ""))

    def test_planned_run_replans_once_and_keeps_staged_writes(self):
        staged = {Path("a.py"): "x"}
        results = [
            RunResult("plan one", {}, self.repo / "a.jsonl"),
            RunResult(
                "tried", staged, self.repo / "a.jsonl", tests_passed=False, test_output="exit=1"
            ),
            RunResult("plan two", {}, self.repo / "a.jsonl"),
            RunResult("done", staged, self.repo / "a.jsonl", tests_passed=True),
        ]
        with (
            mock.patch("agent.loop.run_agent", side_effect=results) as runner,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            final = run_planned("fix it", self.repo, "m", "http://x", apply=False)
        self.assertTrue(final.tests_passed)
        self.assertEqual(runner.call_count, len(results))
        self.assertEqual(runner.call_args_list[-1].kwargs["seed_writes"], staged)

    def test_planned_run_does_not_replan_when_tests_pass(self):
        results = [
            RunResult("plan", {}, self.repo / "a.jsonl"),
            RunResult("done", {}, self.repo / "a.jsonl", tests_passed=True),
        ]
        with (
            mock.patch("agent.loop.run_agent", side_effect=results) as runner,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            run_planned("fix it", self.repo, "m", "http://x", apply=False)
        self.assertEqual(runner.call_count, len(results))


if __name__ == "__main__":
    unittest.main()
