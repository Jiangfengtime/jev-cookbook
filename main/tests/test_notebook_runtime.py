"""扩展 Notebook 的配置、路径和评测题库回归测试；不发外部请求。"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "main"))
from notebook_runtime import benchmark_workspace, jev_mem_root, load_project_env, project_root


class NotebookRuntimeTests(unittest.TestCase):
    def test_find_root_from_nested_notebook(self):
        self.assertEqual(project_root(ROOT / "main/09_Agent集成"), ROOT)

    def test_env_file_overrides_stale_process_values_and_parses_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main").mkdir()
            (root / "main/.env").write_text('TYPESAFE_API_KEY="file-test-key"\nTYPESAFE_DEFAULT_MODEL=decision-model-preview\nTYPESAFE_BASE_URL=https://configured.example/compatible-mode\n')
            with patch.dict(os.environ, {"TYPESAFE_API_KEY": "stale-key", "TYPESAFE_BASE_URL": "http://127.0.0.1:8811"}):
                load_project_env(root)
                self.assertEqual(os.environ["TYPESAFE_API_KEY"], "file-test-key")
                self.assertEqual(os.environ["TYPESAFE_DEFAULT_MODEL"], "decision-model-preview")
                self.assertEqual(os.environ["TYPESAFE_BASE_URL"], "https://configured.example/compatible-mode")

    def test_existing_public_tasks_are_converted_without_modifying_sources(self):
        sources = ROOT / "main/06_模型评测/benchmark/tasks"
        before = {p.name: p.read_bytes() for p in sources.glob("*.jsonl")}
        workspace = benchmark_workspace(ROOT)
        try:
            records = [json.loads(line) for line in (workspace / "tasks/public_all.jsonl").read_text().splitlines()]
            self.assertEqual(len(records), 231)
            self.assertEqual(len({r["id"] for r in records}), 231)
            self.assertTrue(all("question_type" in r and "instructions" in r for r in records))
            smoke = [json.loads(line) for line in (workspace / "tasks/smoke.jsonl").read_text().splitlines()]
            self.assertEqual({r["question_type"] for r in smoke}, {"choice", "noul", "score"})
            self.assertEqual({p.name: p.read_bytes() for p in sources.glob("*.jsonl")}, before)
        finally:
            shutil.rmtree(workspace)

    def test_external_memory_project_can_be_configured_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "jev_mem").mkdir()
            with patch.dict(os.environ, {"JEV_MEM_ROOT": str(path)}):
                self.assertEqual(jev_mem_root(ROOT), path.resolve())


if __name__ == "__main__":
    unittest.main()
