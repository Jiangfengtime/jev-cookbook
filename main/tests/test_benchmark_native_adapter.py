"""真实 SDK 的 MockTransport 覆盖原生评测请求；不联网。"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx2
from typesafe_sdk import TypeSafeClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "06_模型评测/benchmark"))
from llm_eval.adapters import typesafe as adapter_module
from llm_eval.adapters.base import AdapterError
from llm_eval.task import Task


class NativeAdapterTests(unittest.TestCase):
    def task(self):
        return Task(id="nested", family="policy", question_type="choice", instructions="判断是否通过",
                    state={"matrix": {"rows": [["审批", "通过"]]}, "archive": ["中文记录"] * 500},
                    labels=["allow", "deny"], expected="allow", criteria={"allow": "允许", "deny": "拒绝"})

    def test_sdk_preserves_nested_state_and_sends_to_configured_service(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx2.Response(200, json={"model": "decision-model-preview",
                "answers": {"q": {"type": "choice", "choice": "allow", "confidence": 0.9,
                    "probabilities": {"allow": 0.9, "deny": 0.1}}}, "usage": {"input_tokens": 2500}})

        def factory(**kwargs):
            return TypeSafeClient(**kwargs, transport=httpx2.MockTransport(handler))

        task = self.task()
        with patch.object(adapter_module, "TypeSafeClient", side_effect=factory):
            result = adapter_module.TypesafeAdapter(base_url="https://configured.example/compatible-mode",
                model="decision-model-preview", key="test-key").call(task)
        body = json.loads(requests[0].content)
        self.assertEqual(body["state"], task.state)
        self.assertNotIn("expected", body)
        self.assertEqual(str(requests[0].url), "https://configured.example/compatible-mode/v1/systemone")
        self.assertEqual(result["usage"]["prompt_tokens"], 2500)
        self.assertEqual(result["probs"], {"allow": 0.9, "deny": 0.1})

    def test_authentication_failure_remains_fatal_without_automatic_retry(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx2.Response(401, json={"message": "private server detail"})

        def factory(**kwargs):
            return TypeSafeClient(**kwargs, transport=httpx2.MockTransport(handler))

        with patch.object(adapter_module, "TypeSafeClient", side_effect=factory):
            with self.assertRaises(AdapterError) as error:
                adapter_module.TypesafeAdapter(key="test-key").call(self.task())
        self.assertTrue(error.exception.fatal)
        self.assertEqual(error.exception.code, 401)
        self.assertEqual(len(requests), 1)
        self.assertNotIn("private server detail", str(error.exception))


if __name__ == "__main__":
    unittest.main()
