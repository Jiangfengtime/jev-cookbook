"""让 Jev-Mem 的独立问题批次适配服务端单请求 16 题的限制。

只拆分 questions，不截断候选记忆，也不把前一批答案塞回 state。
外部 Jev-Mem 项目须先加入 sys.path。
"""
import math
import time

from memory.jev_client import CallBudget, JevClient, ProbabilityResult


class NotebookJevClient(JevClient):
    max_questions = 16

    def evaluate(self, operation, state, questions, *, mock_values=None, budget=None):
        if len(questions) <= self.max_questions:
            return super().evaluate(operation, state, questions, mock_values=mock_values, budget=budget)
        items = list(questions.items())
        batches = math.ceil(len(items) / self.max_questions)
        if budget is None:
            attempts = batches * (self.config.max_retries + 1)
            budget = CallBudget(attempts, time.monotonic() + self.config.timeout_seconds * attempts)
        parts = []
        for start in range(0, len(items), self.max_questions):
            group = dict(items[start:start + self.max_questions])
            values = {k: v for k, v in (mock_values or {}).items() if k in group} if mock_values is not None else None
            result = super().evaluate(operation, state, group, mock_values=values, budget=budget)
            if result is None:
                return None
            parts.append(result)
        sources = {part.source for part in parts}
        source = "cache" if sources == {"cache"} else next(s for s in sources if s != "cache")
        usage = {}
        for key in ("input_tokens", "output_tokens"):
            counts = [part.usage.get(key) for part in parts]
            usage[key] = sum(counts) if all(isinstance(count, (int, float)) for count in counts) else None
        return ProbabilityResult(
            {k: v for part in parts for k, v in part.values.items()}, source,
            {k: v for part in parts for k, v in part.choices.items()}, parts[0].model, usage,
        )
