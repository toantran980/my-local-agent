import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent_cli import (
    LocalTools,
    apply_pending_writes,
    is_sensitive_path,
    resolve_repo_path,
    tool_definitions,
)


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
        body = io.BytesIO(json.dumps("[0.9] eval/rag/docs/vram.md").encode())
        with mock.patch("agent_cli.urllib.request.urlopen", return_value=body):
            result = self.tools.call("semantic_search", {"query": "vram", "k": 3})
        self.assertIn("vram.md", result)

    def test_semantic_search_is_read_only_in_every_mode(self):
        for mode in ("ask", "plan", "agent"):
            names = [t["function"]["name"] for t in tool_definitions(mode)]
            self.assertIn("semantic_search", names)


if __name__ == "__main__":
    unittest.main()
