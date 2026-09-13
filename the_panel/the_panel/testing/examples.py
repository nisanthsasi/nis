"""Build a valid example instance of any Pydantic output model — the offline stand-in for a model call.

Constraints honoured: enums (first member), Literal (first), ``ge``/``le``/``gt``, list
``min_length``, nested models, ``X | None`` (X preferred), dicts (empty). Hints override
field values by ``"Model.field"`` or bare ``"field"`` name.
"""
from __future__ import annotations

import enum
import types
import typing
from typing import Any, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

MAX_DEPTH = 8


def _constraint(fi: FieldInfo, name: str) -> Any:
    for m in fi.metadata:
        if hasattr(m, name):
            return getattr(m, name)
    return None


def _example_str(model_name: str, field: str) -> str:
    return f"{field.replace('_', ' ')} for {model_name}"


def build_example(model: type[BaseModel], hints: dict[str, Any] | None = None, *, _depth: int = 0) -> BaseModel:
    hints = hints or {}
    values: dict[str, Any] = {}
    for name, fi in model.model_fields.items():
        hint_key_full = f"{model.__name__}.{name}"
        if hint_key_full in hints:
            values[name] = hints[hint_key_full]
            continue
        if name in hints:
            values[name] = hints[name]
            continue
        values[name] = _value_for(fi.annotation, fi, model.__name__, name, hints, _depth)
    return model.model_validate(values)


def _value_for(annotation: Any, fi: FieldInfo | None, model_name: str, field: str, hints: dict[str, Any], depth: int) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)

    # Optional / Union
    if origin is types.UnionType or origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        if depth > MAX_DEPTH or not non_none:
            return None
        return _value_for(non_none[0], fi, model_name, field, hints, depth)

    if origin is typing.Literal:
        return args[0]

    if origin in (list, typing.List):
        min_len = (_constraint(fi, "min_length") if fi else None) or 0
        n = max(min_len, 1 if depth < 3 else 0)
        max_len = _constraint(fi, "max_length") if fi else None
        if max_len is not None:
            n = min(n, max_len)
        inner = args[0] if args else str
        return [_value_for(inner, None, model_name, f"{field}[{i}]", hints, depth + 1) for i in range(n)]

    if origin in (dict, typing.Dict):
        return {}

    if origin in (tuple, typing.Tuple):
        return tuple(_value_for(a, None, model_name, field, hints, depth + 1) for a in args)

    if isinstance(annotation, type):
        if issubclass(annotation, BaseModel):
            if depth > MAX_DEPTH:
                raise RecursionError(f"example depth exceeded at {model_name}.{field}")
            return build_example(annotation, hints, _depth=depth + 1)
        if issubclass(annotation, enum.Enum):
            return list(annotation)[0]
        if annotation is bool:
            return False
        if annotation is int:
            return _number(fi, int)
        if annotation is float:
            return _number(fi, float)
        if annotation is str:
            return _example_str(model_name, field)
    # datetime and friends
    if getattr(annotation, "__name__", "") == "datetime":
        from datetime import datetime, timezone

        return datetime(2026, 1, 1, tzinfo=timezone.utc)
    if annotation is Any:
        return _example_str(model_name, field)
    return _example_str(model_name, field)


def _number(fi: FieldInfo | None, typ: type) -> Any:
    ge = _constraint(fi, "ge") if fi else None
    gt = _constraint(fi, "gt") if fi else None
    le = _constraint(fi, "le") if fi else None
    lt = _constraint(fi, "lt") if fi else None
    lo = ge if ge is not None else (gt + (1 if typ is int else 0.5) if gt is not None else None)
    hi = le if le is not None else (lt - (1 if typ is int else 0.5) if lt is not None else None)
    default = 1 if typ is int else 1.0
    if lo is not None and hi is not None:
        v = lo if lo <= default <= hi else lo
        # prefer a value strictly inside the range when possible
        mid = (lo + hi) / 2
        v = typ(mid) if typ is float else int(mid)
        if v < lo:
            v = lo
        if v > hi:
            v = hi
        return typ(v)
    if lo is not None:
        return typ(max(default, lo))
    if hi is not None:
        return typ(min(default, hi))
    return typ(default)
