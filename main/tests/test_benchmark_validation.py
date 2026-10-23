"""Notebook 执行到末尾不足以证明评测完成；必须检查逐题状态和覆盖。"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generators"))
from validate_notebooks import BENCHMARK_AUDIT


class BenchmarkValidationTests(unittest.TestCase):
    def check_rows(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tasks").mkdir()
            (root / "tasks/public_all.jsonl").write_text('{"id":"a"}\n{"id":"b"}\n')
            results = root / "runs/notebook-demo/real/jev/results.jsonl"
            results.parent.mkdir(parents=True)
            results.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with contextlib.redirect_stdout(io.StringIO()):
                exec(BENCHMARK_AUDIT, {"PROJ": root, "json": json})

    def test_complete_success_passes(self):
        self.check_rows([{"task_id": "a", "status": "ok"}, {"task_id": "b", "status": "ok"}])

    def test_unattempted_result_is_not_a_success(self):
        with self.assertRaises(AssertionError):
            self.check_rows([{"task_id": "a", "status": "ok"}, {"task_id": "b", "status": "unattempted"}])

    def test_missing_or_duplicate_task_is_not_a_success(self):
        for rows in [[{"task_id": "a", "status": "ok"}],
                     [{"task_id": "a", "status": "ok"}, {"task_id": "a", "status": "ok"}]]:
            with self.assertRaises(AssertionError):
                self.check_rows(rows)


if __name__ == "__main__":
    unittest.main()
