"""A fake Anthropic Messages client for offline runs and tests.

It mimics the subset of ``AsyncAnthropic`` the pipeline uses — ``messages.parse``,
``messages.create``, ``messages.count_tokens`` — and returns validated instances of
the requested ``output_format`` model, either from a scripted responder or from the
schema-driven example builder. Every call is recorded for assertions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel

from .examples import build_example

Responder = Callable[["FakeCall"], "BaseModel | dict | str | None"]


@dataclass
class FakeCall:
    model: str
    system: Any
    messages: list[dict[str, Any]]
    output_format: type[BaseModel] | None
    max_tokens: int
    kwargs: dict[str, Any]
    hints: dict[str, Any] = field(default_factory=dict)

    @property
    def prompt(self) -> str:
        last = self.messages[-1]["content"] if self.messages else ""
        if isinstance(last, list):
            return "\n".join(b.get("text", "") for b in last if isinstance(b, dict))
        return str(last)

    @property
    def system_text(self) -> str:
        if isinstance(self.system, str):
            return self.system
        if isinstance(self.system, list):
            return "\n".join(b.get("text", "") for b in self.system if isinstance(b, dict))
        return ""

    @property
    def is_repair(self) -> bool:
        return len(self.messages) >= 3


class FakeUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int | None = 0
    cache_read_input_tokens: int | None = 0


class FakeTextBlock(BaseModel):
    type: str = "text"
    text: str
    parsed_output: Any = None


class FakeParsedMessage(BaseModel):
    id: str = "msg_fake"
    model: str = "fake"
    role: str = "assistant"
    stop_reason: str = "end_turn"
    stop_details: Any = None
    content: list[FakeTextBlock]
    usage: FakeUsage

    @property
    def parsed_output(self) -> Any:
        for c in self.content:
            if c.type == "text" and c.parsed_output is not None:
                return c.parsed_output
        return None


class _FakeMessages:
    def __init__(self, owner: "FakeLLM"):
        self._owner = owner

    async def parse(self, *, model: str, max_tokens: int, messages: list[dict[str, Any]], output_format: type[BaseModel], system: Any = None, **kwargs: Any) -> FakeParsedMessage:
        call = FakeCall(model=model, system=system, messages=list(messages), output_format=output_format, max_tokens=max_tokens, kwargs=kwargs, hints=dict(self._owner.hints))
        self._owner.calls.append(call)
        obj = self._owner._respond(call)
        text = obj.model_dump_json() if isinstance(obj, BaseModel) else json.dumps(obj, default=str)
        out_tokens = max(1, len(text) // 4)
        in_tokens = max(1, (len(call.prompt) + len(call.system_text)) // 4)
        cached = max(0, len(call.system_text) // 4) if self._owner.calls[:-1] else 0
        return FakeParsedMessage(
            model=model,
            content=[FakeTextBlock(text=text, parsed_output=obj)],
            usage=FakeUsage(input_tokens=in_tokens - cached, output_tokens=out_tokens, cache_creation_input_tokens=0 if cached else len(call.system_text) // 4, cache_read_input_tokens=cached),
        )

    async def create(self, *, model: str, max_tokens: int, messages: list[dict[str, Any]], system: Any = None, **kwargs: Any) -> FakeParsedMessage:
        call = FakeCall(model=model, system=system, messages=list(messages), output_format=None, max_tokens=max_tokens, kwargs=kwargs, hints=dict(self._owner.hints))
        self._owner.calls.append(call)
        obj = self._owner._respond(call)
        text = obj if isinstance(obj, str) else (obj.model_dump_json() if isinstance(obj, BaseModel) else json.dumps(obj, default=str))
        return FakeParsedMessage(model=model, content=[FakeTextBlock(text=text)], usage=FakeUsage(input_tokens=len(call.prompt) // 4, output_tokens=len(text) // 4))

    async def count_tokens(self, *, model: str, messages: list[dict[str, Any]], system: Any = None, **kwargs: Any) -> Any:
        text = json.dumps(messages, default=str) + (json.dumps(system, default=str) if system else "")

        class _Count(BaseModel):
            input_tokens: int

        return _Count(input_tokens=max(1, len(text) // 4))


class FakeLLM:
    """Drop-in for ``AsyncAnthropic`` in offline mode.

    ``responder(call)`` may return a model instance, a dict (validated against the
    requested schema), a string (for ``create``) or ``None`` to fall back to the example
    builder. ``hints`` are merged into example building (e.g. ``{"scene_id": "S3"}``).
    ``fail_first`` makes the first N parse calls raise a validation error so repair
    retries can be tested.
    """

    is_fake = True

    def __init__(self, responder: Responder | None = None, *, hints: dict[str, Any] | None = None, fail_first: int = 0):
        self.responder = responder
        self.hints: dict[str, Any] = dict(hints or {})
        self.calls: list[FakeCall] = []
        self.fail_first = fail_first
        self._failures = 0
        self.messages = _FakeMessages(self)

    def set_hints(self, **hints: Any) -> None:
        self.hints.update(hints)

    def clear_hints(self) -> None:
        self.hints.clear()

    def _respond(self, call: FakeCall) -> Any:
        if self.fail_first and self._failures < self.fail_first and call.output_format is not None:
            self._failures += 1
            from pydantic import ValidationError

            try:
                call.output_format.model_validate({"__fake_invalid__": True})
            except ValidationError as e:  # re-raise as the SDK would
                raise e
        obj = self.responder(call) if self.responder else None
        if obj is None:
            if call.output_format is None:
                return "{}"
            return build_example(call.output_format, call.hints)
        if isinstance(obj, dict) and call.output_format is not None:
            return call.output_format.model_validate(obj)
        return obj

    # convenience for tests
    def calls_for(self, needle: str) -> list[FakeCall]:
        return [c for c in self.calls if needle in c.prompt or needle in c.system_text]

    @property
    def last(self) -> FakeCall:
        return self.calls[-1]
