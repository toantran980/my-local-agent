import contextlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from agent_cli import (
    LocalTools,
    RunResult,
    apply_pending_writes,
    finish_run,
    is_sensitive_path,
    post,
    post_stream,
    resolve_repo_path,
    run_agent,
    run_planned,
    system_prompt,
    tool_definitions,
)


def _reply(content="", calls=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return {"choices": [{"message": message}]}


def _write_call(path="a.py", content="x = 1\n"):
    return {"id": "1", "function": {"name": "write_file",
                                    "arguments": json.dumps({"path": path, "content": content})}}


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
        result = self.tools.call("write_file", {"path": "src/example.py",
                                 "content": "answer = 42\n"})
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
        with mock.patch("agent_cli.urllib.request.urlopen", side_effect=OSError("refused")):
            result = self.tools.call("semantic_search", {"query": "vram"})
        self.assertTrue(result.startswith("ERROR: RAG service unavailable"))

    def test_semantic_search_returns_service_text(self):
        responses = [io.BytesIO(json.dumps(text).encode()) for text in ("indexed", "[0.9] vram.md")]
        with mock.patch("agent_cli.urllib.request.urlopen", side_effect=responses):
            result = self.tools.call("semantic_search", {"query": "vram", "k": 3})
        self.assertIn("vram.md", result)

    def test_semantic_search_reindexes_once_per_run(self):
        def fresh(*_args, **_kwargs):
            return io.BytesIO(json.dumps("ok").encode())

        with mock.patch("agent_cli.urllib.request.urlopen", side_effect=fresh) as opened:
            self.tools.call("semantic_search", {"query": "a"})
            self.tools.call("semantic_search", {"query": "b"})
        urls = [call.args[0].full_url for call in opened.call_args_list]
        self.assertEqual([u.rsplit("/", 1)[-1] for u in urls],
                         ["index_sources", "semantic_search", "semantic_search"])

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
        patcher = mock.patch("agent_cli.MEMORY_ENABLED", new=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _agent(self, replies, test_outputs, mode="agent"):
        with mock.patch("agent_cli.post", side_effect=replies) as post, mock.patch(
            "agent_cli.LocalTools._run_staged_tests", side_effect=test_outputs
        ):
            result = run_agent(mode, "task", self.repo, "m", "http://x", apply=False)
        return result, post

    def test_reflection_retries_once_then_passes(self):
        replies = [_reply(calls=[_write_call()]), _reply("done"),
                   _reply(calls=[_write_call(content="x = 2\n")]), _reply("fixed")]
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

    def test_memory_entry_is_written_and_redacted(self):
        memory = self.repo / "memory"
        with mock.patch("agent_cli.MEMORY_ENABLED", new=True), mock.patch(
            "agent_cli.MEMORY_DIR", new=memory
        ), mock.patch("agent_cli.post", return_value=_reply("all good")):
            run_agent("ask", "check password=hunter2 please", self.repo, "m", "http://x", False)
        text = next(memory.glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("Task:", text)
        self.assertIn("all good", text)
        self.assertNotIn("hunter2", text)

    def test_post_stream_assembles_text_and_tool_calls(self):
        lines = [
            {"choices": [{"delta": {"reasoning": "hmm"}}]},
            {"choices": [{"delta": {"content": "Hel"}}]},
            {"choices": [{"delta": {"content": "lo"}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {
                "name": "search", "arguments": '{"pattern":'}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {
                "arguments": '"x"}'}}]}}]},
        ]
        body = "".join(f"data: {json.dumps(line)}\n\n" for line in lines) + "data: [DONE]\n"
        out = io.StringIO()
        stream = io.BytesIO(body.encode())
        with mock.patch("agent_cli.urllib.request.urlopen", return_value=stream), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
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
        with mock.patch("agent_cli.urllib.request.urlopen", side_effect=error):
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
            RunResult("tried", staged, self.repo / "a.jsonl", tests_passed=False,
                      test_output="exit=1"),
            RunResult("plan two", {}, self.repo / "a.jsonl"),
            RunResult("done", staged, self.repo / "a.jsonl", tests_passed=True),
        ]
        with mock.patch("agent_cli.run_agent", side_effect=results) as runner, \
                contextlib.redirect_stdout(io.StringIO()):
            final = run_planned("fix it", self.repo, "m", "http://x", apply=False)
        self.assertTrue(final.tests_passed)
        self.assertEqual(runner.call_count, len(results))
        self.assertEqual(runner.call_args_list[-1].kwargs["seed_writes"], staged)

    def test_planned_run_does_not_replan_when_tests_pass(self):
        results = [RunResult("plan", {}, self.repo / "a.jsonl"),
                   RunResult("done", {}, self.repo / "a.jsonl", tests_passed=True)]
        with mock.patch("agent_cli.run_agent", side_effect=results) as runner, \
                contextlib.redirect_stdout(io.StringIO()):
            run_planned("fix it", self.repo, "m", "http://x", apply=False)
        self.assertEqual(runner.call_count, len(results))


if __name__ == "__main__":
    unittest.main()
