"""BaseAgent — the one code path every model call takes.

render template → call ``messages.parse`` with the output schema → validate (Pydantic +
agent-specific checks) → on failure, retry ONCE with the validation error as a repair
instruction → persist raw and parsed → return an :class:`AgentResult`.

System content is stable-first for prompt caching: [P0 laws digest] + [Film Brief Header]
(both cached), then everything volatile goes in the user turn.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Generic, TypeVar

import jinja2
from pydantic import BaseModel, ValidationError

from ..config import PanelConfig, load_config
from ..orchestrator.header import FilmBriefHeader
from ..orchestrator.routing import budget_for, max_tokens_for, model_for, request_kwargs
from ..prompts.registry import TEMPLATES, make_env
from ..schemas.common import Usage
from ..store.snapshots import SnapshotStore

log = logging.getLogger("the_panel.agents")

T = TypeVar("T", bound=BaseModel)

SHOWRUNNER_LAWS = """You are one specialist inside THE PANEL, an AI Director system serving a human director-writer
working in Malayalam cinema and Indian OTT, with world-cinema grounding. Laws you obey:
1. Understanding precedes vision. 2. Every handoff is a schema — output only the requested JSON.
3. Lenses are constrained priors, not impersonations: never invent quotes, anecdotes or biography.
4. Proposals are scored, not averaged. 5. The Style Bible is the constitution; cite compliance or propose an explicit amendment.
6. Departments derive; they do not re-decide. 7. Auditors hold cross-scene context. 8. The human director is sovereign.
9. Pleasure is engineered: posture, caps and permissions come from the Style Bible, never from taste; a device is judged earned or unearned, never by pedigree.
Analysis is in English; dialogue is quoted in its original language and never translated; name the Malayalam register when dialogue is analysed.
When uncertain about intent, do not guess: raise a HUMAN_QUESTION with two concrete options and continue with the more conservative one."""


class ValidationRejected(RuntimeError):
    """Raised when an output fails validation twice (initial + one repair)."""

    def __init__(self, agent: str, error: str, raw: str):
        super().__init__(f"{agent}: output rejected after repair: {error[:400]}")
        self.agent = agent
        self.error = error
        self.raw = raw


@dataclass
class AgentResult(Generic[T]):
    stage: str
    agent: str
    model: str
    parsed: T
    raw_text: str
    usage: Usage
    attempts: int
    budget: int
    over_budget: bool
    key: str
    repair_error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    variables_sha: str = ""
    snapshot_path: Path | None = None

    @property
    def output_tokens(self) -> int:
        return self.usage.output_tokens


@dataclass
class AgentContext:
    """Everything an agent needs that is not the prompt variables."""

    config: PanelConfig
    client: Any  # anthropic.AsyncAnthropic or the_panel.testing.FakeLLM
    env: jinja2.Environment
    store: SnapshotStore | None = None
    header: FilmBriefHeader | None = None
    lens_cards: dict[str, dict[str, Any]] = field(default_factory=dict)
    usage_ledger: dict[str, Usage] = field(default_factory=dict)
    strict_no_impersonation: bool = True

    @classmethod
    def offline(cls, config: PanelConfig | None = None, *, store_root: str | Path | None = None, responder=None, hints: dict[str, Any] | None = None) -> "AgentContext":
        from ..testing.fake_llm import FakeLLM

        config = config or load_config()
        return cls(config=config, client=FakeLLM(responder, hints=hints), env=make_env(), store=SnapshotStore(store_root) if store_root else None)

    @classmethod
    def live(cls, config: PanelConfig | None = None, *, store_root: str | Path | None = None) -> "AgentContext":
        import anthropic

        config = config or load_config()
        client = anthropic.AsyncAnthropic(timeout=config.request.timeout_s, max_retries=config.request.max_retries)
        return cls(config=config, client=client, env=make_env(), store=SnapshotStore(store_root or config.path("snapshots")))

    @property
    def is_offline(self) -> bool:
        return bool(getattr(self.client, "is_fake", False))

    def system_blocks(self, *, use_header: bool = True) -> list[dict[str, Any]]:
        ttl = self.config.request.cache_ttl
        blocks: list[dict[str, Any]] = [{"type": "text", "text": SHOWRUNNER_LAWS, "cache_control": {"type": "ephemeral", "ttl": ttl}}]
        if use_header and self.header is not None:
            blocks.append(self.header.system_block(ttl))
        return blocks

    def record_usage(self, stage: str, usage: Usage) -> None:
        self.usage_ledger[stage] = self.usage_ledger.get(stage, Usage()) + usage

    def total_usage(self) -> Usage:
        total = Usage()
        for u in self.usage_ledger.values():
            total = total + u
        return total


IMPERSONATION_MARKERS = ("as i once said", "as he once said", "as she once said", "i remember when i shot", "as [", "in my film", "when i directed")


class BaseAgent(Generic[T]):
    """Subclass, set the ClassVars, optionally override ``check`` for agent-specific validation."""

    stage: ClassVar[str] = "reasoning"
    name: ClassVar[str] = "base"
    template: ClassVar[str] = ""
    output_model: ClassVar[type[BaseModel]] = BaseModel
    uses_header: ClassVar[bool] = True

    def __init__(self, ctx: AgentContext):
        self.ctx = ctx

    # --- hooks -------------------------------------------------------------------
    def check(self, parsed: T, variables: dict[str, Any]) -> None:
        """Raise ``ValueError`` with a repair instruction if the parsed output is unacceptable."""

    def prepare(self, variables: dict[str, Any]) -> dict[str, Any]:
        """Transform variables before rendering (default: JSON-serialise pydantic models)."""
        out: dict[str, Any] = {}
        for k, v in variables.items():
            out[k] = _jsonable(v)
        return out

    # --- rendering ---------------------------------------------------------------
    def render(self, **variables: Any) -> str:
        spec = TEMPLATES[self.template]
        prepared = self.prepare(variables)
        missing = [v for v in spec.required if v not in prepared]
        if missing:
            raise KeyError(f"{self.name}: template '{self.template}' missing required variables {missing}")
        return self.ctx.env.get_template(spec.file).render(**prepared)

    # --- the call ----------------------------------------------------------------
    async def run(self, *, key: str, **variables: Any) -> AgentResult[T]:
        prompt = self.render(**variables)
        cfg = self.ctx.config
        model = model_for(cfg, self.stage)
        max_tokens = max_tokens_for(cfg, self.stage)
        budget = budget_for(cfg, self.stage)
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        system = self.ctx.system_blocks(use_header=self.uses_header)
        usage_total = Usage()
        raw_text = ""
        repair_error: str | None = None
        if self.ctx.is_offline and hasattr(self.ctx.client, "set_hints"):
            self.ctx.client.set_hints(**self._fake_hints(variables))
        for attempt in (1, 2):
            try:
                resp = await self.ctx.client.messages.parse(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                    output_format=self.output_model,
                    **request_kwargs(cfg, self.stage),
                )
            except ValidationError as e:  # schema-level rejection surfaced by the SDK's parse
                repair_error = _format_validation_error(e)
                raw_text = getattr(e, "raw_text", raw_text) or raw_text
                if attempt == 2:
                    raise ValidationRejected(self.name, repair_error, raw_text) from e
                messages = messages + [
                    {"role": "assistant", "content": raw_text or "(invalid JSON)"},
                    {"role": "user", "content": _repair_instruction(repair_error)},
                ]
                continue
            usage_total = usage_total + _usage_of(resp)
            raw_text = _text_of(resp)
            if getattr(resp, "stop_reason", None) == "refusal":
                raise ValidationRejected(self.name, "model refused the request", raw_text)
            parsed = resp.parsed_output
            try:
                if parsed is None:
                    parsed = self.output_model.model_validate_json(raw_text)
                if self.ctx.strict_no_impersonation:
                    _reject_impersonation(raw_text)
                self.check(parsed, variables)  # type: ignore[arg-type]
            except (ValidationError, ValueError) as e:
                repair_error = _format_validation_error(e)
                if attempt == 2:
                    raise ValidationRejected(self.name, repair_error, raw_text) from e
                messages = messages + [
                    {"role": "assistant", "content": raw_text},
                    {"role": "user", "content": _repair_instruction(repair_error)},
                ]
                continue
            over = usage_total.output_tokens > budget
            if over and cfg.budgets.strict_budgets:
                raise ValidationRejected(self.name, f"output {usage_total.output_tokens} tokens exceeds budget {budget}", raw_text)
            if over:
                log.warning("%s over budget: %s > %s output tokens", self.name, usage_total.output_tokens, budget)
            self.ctx.record_usage(self.stage, usage_total)
            result = AgentResult(
                stage=self.stage,
                agent=self.name,
                model=model,
                parsed=parsed,
                raw_text=raw_text,
                usage=usage_total,
                attempts=attempt,
                budget=budget,
                over_budget=over,
                key=key,
                repair_error=repair_error if attempt == 2 else None,
                variables_sha=_sha(variables),
            )
            if self.ctx.store is not None:
                result.snapshot_path = self.ctx.store.save(
                    self.name,
                    key,
                    parsed,
                    raw=raw_text,
                    meta={"model": model, "usage": usage_total.model_dump(), "attempts": attempt, "over_budget": over, "variables_sha": result.variables_sha},
                )
            return result
        raise AssertionError("unreachable")

    def _fake_hints(self, variables: dict[str, Any]) -> dict[str, Any]:
        """Let the offline fake produce ids that line up with the call (scene_id, lens, …)."""
        hints: dict[str, Any] = {}
        scene = variables.get("scene")
        if isinstance(scene, BaseModel) and hasattr(scene, "id"):
            hints["scene_id"] = getattr(scene, "id")
        elif isinstance(scene, dict) and "id" in scene:
            hints["scene_id"] = scene["id"]
        card = variables.get("lens_card")
        if isinstance(card, dict) and "name" in card:
            hints["lens"] = card["name"]
        seq = variables.get("sequence") or variables.get("sequence_plan")
        if isinstance(seq, BaseModel) and hasattr(seq, "sequence_id"):
            hints["sequence_id"] = getattr(seq, "sequence_id")
        elif isinstance(seq, dict) and "sequence_id" in seq:
            hints["sequence_id"] = seq["sequence_id"]
        if "dept" in variables:
            hints["dept"] = variables["dept"]
        return hints


# --- helpers ----------------------------------------------------------------------


def _jsonable(v: Any) -> Any:
    if isinstance(v, BaseModel):
        return v.model_dump(mode="json")
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if hasattr(v, "__dataclass_fields__"):
        return {k: _jsonable(getattr(v, k)) for k in v.__dataclass_fields__}
    return v


def _sha(variables: dict[str, Any]) -> str:
    try:
        payload = json.dumps(_jsonable(variables), sort_keys=True, default=str, ensure_ascii=False)
    except TypeError:
        payload = repr(variables)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _usage_of(resp: Any) -> Usage:
    u = getattr(resp, "usage", None)
    if u is None:
        return Usage()
    return Usage(
        input_tokens=int(getattr(u, "input_tokens", 0) or 0),
        output_tokens=int(getattr(u, "output_tokens", 0) or 0),
        cache_creation_input_tokens=int(getattr(u, "cache_creation_input_tokens", 0) or 0),
        cache_read_input_tokens=int(getattr(u, "cache_read_input_tokens", 0) or 0),
    )


def _text_of(resp: Any) -> str:
    for block in getattr(resp, "content", []) or []:
        if getattr(block, "type", "") == "text":
            return getattr(block, "text", "") or ""
    return ""


def _format_validation_error(e: Exception) -> str:
    if isinstance(e, ValidationError):
        parts = []
        for err in e.errors()[:12]:
            loc = ".".join(str(x) for x in err.get("loc", ()))
            parts.append(f"{loc}: {err.get('msg')}")
        return "; ".join(parts)
    return str(e)


def _repair_instruction(error: str) -> str:
    return (
        "REPAIR: your previous output failed validation against the required schema. "
        f"Errors: {error}. Return the corrected JSON only — same content, valid against the schema, "
        "every shot with a beat_ref, every device with a setup_ref, no prose outside the JSON."
    )


def _reject_impersonation(raw: str) -> None:
    low = raw.lower()
    for marker in IMPERSONATION_MARKERS:
        if marker in low:
            raise ValueError(f"impersonation language detected ('{marker}'): speak as the lens, never as the person; remove quotes, anecdotes and biography")
