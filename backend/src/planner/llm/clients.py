"""Transport layer: send chat messages to a model and get text back."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx
import yaml

from planner.llm.contracts import Contract


class ModelUnavailableError(RuntimeError):
    """The model server could not be reached or returned an error."""


@dataclass
class TaskModelConfig:
    backend: Literal["mock", "openai"] = "mock"
    base_url: str = "http://localhost:8001/v1"
    api_key: str = "EMPTY"
    model: str = "planner"
    temperature: float = 0.5
    max_tokens: int = 800
    timeout_seconds: float = 120
    structured_output: Literal["json_schema", "json_object", "none"] = "json_schema"
    max_retries: int = 1


@dataclass
class CompletionRequest:
    task: str
    messages: list[dict[str, str]]
    config: TaskModelConfig
    json_schema: dict[str, Any] | None = None
    # The structured input the messages were built from. Real models ignore it; the mock uses it.
    payload: Contract | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    def complete(self, req: CompletionRequest) -> str: ...


class OpenAICompatClient:
    """Calls ``POST {base_url}/chat/completions`` on vLLM / Ollama / llama.cpp / any OpenAI-style server."""

    def __init__(self) -> None:
        self._clients: dict[tuple[str, float], httpx.Client] = {}

    def _http(self, cfg: TaskModelConfig) -> httpx.Client:
        key = (cfg.base_url, cfg.timeout_seconds)
        if key not in self._clients:
            self._clients[key] = httpx.Client(base_url=cfg.base_url.rstrip("/"), timeout=cfg.timeout_seconds)
        return self._clients[key]

    def complete(self, req: CompletionRequest) -> str:
        cfg = req.config
        body: dict[str, Any] = {
            "model": cfg.model,
            "messages": req.messages,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
        if req.json_schema is not None and cfg.structured_output == "json_schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": req.task.replace(".", "_"), "schema": req.json_schema},
            }
        elif req.json_schema is not None and cfg.structured_output == "json_object":
            body["response_format"] = {"type": "json_object"}
        try:
            resp = self._http(cfg).post(
                "/chat/completions", json=body, headers={"Authorization": f"Bearer {cfg.api_key}"}
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise ModelUnavailableError(f"{req.task} -> {cfg.base_url} ({cfg.model}): {e}") from e


def load_task_configs(path: Path) -> dict[str, TaskModelConfig]:
    raw = yaml.safe_load(path.read_text()) if path.exists() else {}
    defaults = raw.get("defaults", {}) or {}
    if env_backend := os.environ.get("PLANNER_MODELS_BACKEND"):
        defaults["backend"] = env_backend
    configs: dict[str, TaskModelConfig] = {}
    for task, overrides in (raw.get("tasks", {}) or {}).items():
        configs[task] = TaskModelConfig(**{**defaults, **(overrides or {})})
    return configs
