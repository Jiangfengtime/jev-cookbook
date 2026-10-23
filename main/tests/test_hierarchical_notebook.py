"""层级分类的配置来源、SDK 请求和服务故障回归；不访问外部服务。"""
import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx2
from typesafe_sdk import RetryPolicy, TypeSafeClient, TypeSafeInternalServerError

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = ROOT / "main/04_实战指南/16_层级分类.ipynb"
FILE_CONFIG = {
    "TYPESAFE_API_KEY": "file-test-key",
    "TYPESAFE_BASE_URL": "https://configured.example/compatible-mode",
    "TYPESAFE_DEFAULT_MODEL": "decision-model-preview",
}


class HierarchicalNotebookTests(unittest.TestCase):
    def execute(self, status=200):
        notebook = json.loads(NOTEBOOK.read_text())
        requests = []
        loaded_paths = []
        scope = {}

        def handler(request):
            requests.append(request)
            if status != 200:
                return httpx2.Response(status, json={"detail": "test service unavailable"})
            body = json.loads(request.content)
            answers = {}
            for name, question in body["questions"].items():
                if question["type"] == "noul":
                    answers[name] = {"type": "noul", "noul": 0.99}
                    continue
                labels = list(question["criteria"])
                state = body["state"]
                wanted = (["digital", "audio", "headphones"] if "耳机" in state else
                          ["digital", "computer", "laptop"] if "笔记本" in state else
                          ["digital", "phone", "flagship"])
                chosen = next((label for label in wanted if label in labels), labels[0])
                probabilities = {label: (0.9 if label == chosen else 0.1 / (len(labels) - 1))
                                 for label in labels} if len(labels) > 1 else {chosen: 1.0}
                answers[name] = {"type": "choice", "choice": chosen, "confidence": 0.9,
                                 "probabilities": probabilities}
            return httpx2.Response(200, json={"model": "decision-model-preview", "answers": answers,
                                             "usage": {"input_tokens": 1, "output_tokens": 0}})

        def client_factory(**kwargs):
            return TypeSafeClient(**kwargs, transport=httpx2.MockTransport(handler),
                                  retry=RetryPolicy(max_retries=0))

        def file_values(path):
            loaded_paths.append(path)
            return FILE_CONFIG

        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "stale-key",
                                    "TYPESAFE_BASE_URL": "http://127.0.0.1:8811",
                                    "TYPESAFE_DEFAULT_MODEL": "laya-multilingual"}), \
                patch("pathlib.Path.cwd", return_value=NOTEBOOK.parent), \
                patch("dotenv.dotenv_values", side_effect=file_values), \
                patch("dotenv.load_dotenv", return_value=False), \
                patch("typesafe_sdk.TypeSafeClient", side_effect=client_factory), \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                for index, cell in enumerate(notebook["cells"]):
                    source = "".join(cell.get("source", []))
                    if cell["cell_type"] == "code" and "%pip" not in source:
                        exec(compile(source, f"hierarchical:cell-{index}", "exec"), scope)
            finally:
                if scope.get("client") is not None:
                    scope["client"].close()
        return scope, requests, loaded_paths

    def test_file_configuration_overrides_stale_localhost_and_algorithms_finish(self):
        scope, requests, loaded_paths = self.execute()
        self.assertEqual(loaded_paths, [ROOT / "main/.env"])
        self.assertTrue(requests)
        for request in requests:
            self.assertEqual(str(request.url), FILE_CONFIG["TYPESAFE_BASE_URL"] + "/v1/systemone")
            self.assertEqual(request.headers["Authorization"], "Bearer file-test-key")
            self.assertEqual(json.loads(request.content)["model"], "decision-model-preview")
        self.assertFalse(scope["TS"].offline)
        self.assertEqual(scope["TS"].real_calls, len(requests) - 1)
        self.assertEqual([row[0][-1] for row in scope["GREEDY_RESULTS"]],
                         ["flagship", "laptop", "headphones"])

    def test_502_is_reported_instead_of_falling_back_to_fake_results(self):
        with self.assertRaises(TypeSafeInternalServerError):
            self.execute(status=502)


if __name__ == "__main__":
    unittest.main()
