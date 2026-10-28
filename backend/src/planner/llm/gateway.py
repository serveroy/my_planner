"""The only entry point the app uses to talk to models.

``ModelGateway`` builds the prompt for a task, sends it to whichever backend serves that task
(mock or an OpenAI-compatible server), parses and validates the output against the task's
contract, retries once with the validation error on failure, and logs the call.
"""

import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from planner.config import get_settings
from planner.llm.clients import (
    CompletionRequest,
    LLMClient,
    ModelUnavailableError,
    OpenAICompatClient,
    TaskModelConfig,
    load_task_configs,
)
from planner.llm.contracts import (
    TASKS,
    CheckinInput,
    CoachChatInput,
    Contract,
    ExtractInput,
    ExtractOutput,
    GenerateInput,
    InterviewInput,
    InterviewOutput,
    Plan,
    ReviseInput,
    ReviseOutput,
    SummarizeInput,
)
from planner.llm.prompts import build_messages

log = logging.getLogger(__name__)


class ModelOutputError(RuntimeError):
    """The model answered, but not with something that satisfies the task contract."""


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> object:
    """Parse a JSON object from model output, tolerating code fences and leading/trailing chatter."""
    text = text.strip()
    if m := _FENCE_RE.search(text):
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


class CallLogger:
    """Appends every model call to ``<dir>/<task>.jsonl`` as {"messages": [...], ...}."""

    def __init__(self, directory: Path | None) -> None:
        self.directory = directory
        self._lock = threading.Lock()

    def write(self, task: str, cfg: TaskModelConfig, messages: list[dict], output: str, ok: bool, ms: int) -> None:
        if self.directory is None:
            return
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "task": task,
            "backend": cfg.backend,
            "model": cfg.model,
            "valid": ok,
            "latency_ms": ms,
            "messages": messages + [{"role": "assistant", "content": output}],
        }
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with self._lock, open(self.directory / f"{task}.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            log.exception("could not write model call log")


class ModelGateway:
    def __init__(
        self,
        configs: dict[str, TaskModelConfig],
        clients: dict[str, LLMClient] | None = None,
        logger: CallLogger | None = None,
    ) -> None:
        self.configs = configs
        if clients is None:
            from planner.llm.mock import MockClient

            clients = {"mock": MockClient(), "openai": OpenAICompatClient()}
        self.clients = clients
        self.logger = logger or CallLogger(None)

    # ---- typed task API --------------------------------------------------------------------

    def interview(self, inp: InterviewInput) -> InterviewOutput:
        return self._run_json("planner.interview", inp, InterviewOutput)

    def generate_plan(self, inp: GenerateInput) -> Plan:
        return self._run_json("planner.generate", inp, Plan)

    def revise_plan(self, inp: ReviseInput) -> ReviseOutput:
        return self._run_json("planner.revise", inp, ReviseOutput)

    def chat(self, inp: CoachChatInput) -> str:
        return self._run_text("coach.chat", inp)

    def checkin(self, inp: CheckinInput) -> str:
        return self._run_text("coach.checkin", inp)

    def extract(self, inp: ExtractInput) -> ExtractOutput:
        return self._run_json("coach.extract", inp, ExtractOutput)

    def summarize(self, inp: SummarizeInput) -> str:
        return self._run_text("coach.summarize", inp)

    # ---- plumbing ----------------------------------------------------------------------------

    def _config(self, task: str) -> TaskModelConfig:
        return self.configs.get(task) or TaskModelConfig()

    def _call(self, task: str, messages: list[dict], payload: Contract, schema: dict | None) -> tuple[str, int]:
        cfg = self._config(task)
        client = self.clients[cfg.backend]
        started = time.monotonic()
        out = client.complete(
            CompletionRequest(task=task, messages=messages, config=cfg, json_schema=schema, payload=payload)
        )
        return out, int((time.monotonic() - started) * 1000)

    def _run_json[T: Contract](self, task: str, payload: Contract, out_model: type[T]) -> T:
        assert isinstance(payload, TASKS[task].input)
        cfg = self._config(task)
        messages = build_messages(task, payload)
        schema = out_model.model_json_schema()
        attempt_messages = messages
        last_error = ""
        for _attempt in range(cfg.max_retries + 1):
            raw, ms = self._call(task, attempt_messages, payload, schema)
            try:
                result = out_model.model_validate(extract_json(raw))
            except (ValueError, ValidationError) as e:
                last_error = str(e)
                self.logger.write(task, cfg, attempt_messages, raw, False, ms)
                log.warning("%s returned invalid output: %s", task, last_error[:300])
                attempt_messages = messages + [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": f"Your output was invalid: {last_error[:800]}\nReturn only the corrected JSON object.",
                    },
                ]
                continue
            # Log with the original prompt so the record is a clean training example.
            self.logger.write(task, cfg, messages, raw, True, ms)
            return result
        raise ModelOutputError(f"{task}: invalid output after retries: {last_error[:500]}")

    def _run_text(self, task: str, payload: Contract) -> str:
        assert isinstance(payload, TASKS[task].input)
        cfg = self._config(task)
        messages = build_messages(task, payload)
        raw, ms = self._call(task, messages, payload, None)
        text = raw.strip()
        self.logger.write(task, cfg, messages, text, bool(text), ms)
        if not text:
            raise ModelOutputError(f"{task}: empty output")
        return text


@lru_cache
def get_gateway() -> ModelGateway:
    settings = get_settings()
    return ModelGateway(
        load_task_configs(settings.models_config_path),
        logger=CallLogger(settings.llm_log_dir if settings.llm_log_enabled else None),
    )


__all__ = ["ModelGateway", "ModelOutputError", "ModelUnavailableError", "extract_json", "get_gateway"]
