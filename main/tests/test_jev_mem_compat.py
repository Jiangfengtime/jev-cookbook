"""需 JEV_MEM_ROOT 指向外部 Jev-Mem；通过 MockTransport 检查分批，不联网。"""
import json
import os
import sys
import unittest
from pathlib import Path

import httpx2
from typesafe_sdk import Noul

EXTERNAL = Path(os.environ.get("JEV_MEM_ROOT", "/missing-jev-mem"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if (EXTERNAL / "jev_mem").is_dir():
    sys.path.insert(0, str(EXTERNAL))
    from jev_mem_compat import NotebookJevClient
    from memory.jev_mem_config import JevMemConfig


@unittest.skipUnless((EXTERNAL / "jev_mem").is_dir(), "设置 JEV_MEM_ROOT 后验证外部集成")
class MemoryBatchTests(unittest.TestCase):
    def test_large_question_set_is_split_without_changing_state_or_answers(self):
        bodies = []

        def handler(request):
            body = json.loads(request.content)
            bodies.append(body)
            self.assertLessEqual(len(body["questions"]), 16)
            return httpx2.Response(200, json={"model": "decision-model-preview",
                "answers": {k: {"type": "noul", "noul": 0.8} for k in body["questions"]},
                "usage": {"input_tokens": 5}})

        config = JevMemConfig(jev_base_url="https://configured.example/compatible-mode",
                              jev_model="decision-model-preview", max_retries=0)
        questions = {f"q_{i}": Noul(instructions=f"第 {i} 项是否有关？") for i in range(34)}
        state = {"observation": "用户修改了出差计划"}
        with NotebookJevClient(config, api_key="test-key", transport=httpx2.MockTransport(handler)) as client:
            result = client.evaluate("relations", state, questions)
        self.assertEqual([len(body["questions"]) for body in bodies], [16, 16, 2])
        self.assertTrue(all(body["state"] == state for body in bodies))
        self.assertEqual(set(result.values), set(questions))
        self.assertEqual(result.usage["input_tokens"], 15)
        self.assertIsNone(result.usage["output_tokens"])
        self.assertEqual(result.source, "jev")


if __name__ == "__main__":
    unittest.main()
