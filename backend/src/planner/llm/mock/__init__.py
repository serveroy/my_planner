"""Heuristic stand-ins for the fine-tuned models.

``MockClient`` implements the same ``LLMClient`` interface as the real OpenAI-compatible client and
returns text in exactly the format the real model must produce (JSON for JSON tasks), so the
whole pipeline -- parsing, validation, retries, logging -- is exercised without a GPU.
"""

import json

from planner.llm.clients import CompletionRequest
from planner.llm.mock import coach, interview, plan

_HANDLERS = {
    "planner.interview": interview.interview,
    "planner.generate": plan.generate,
    "planner.revise": plan.revise,
    "coach.chat": coach.chat,
    "coach.checkin": coach.checkin,
    "coach.extract": coach.extract,
    "coach.summarize": coach.summarize,
}


class MockClient:
    def complete(self, req: CompletionRequest) -> str:
        if req.payload is None:
            raise ValueError("MockClient needs the structured payload")
        result = _HANDLERS[req.task](req.payload)
        if isinstance(result, str):
            return result
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
