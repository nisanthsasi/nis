"""Versioned JSON snapshots — the minimum persistence every agent call writes to.

Layout: ``<root>/<stage>/<key>.v<N>.json`` with ``raw`` and ``parsed`` side by side.
The SQLite store (``store/db.py``) mirrors the same records with queryable columns.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_key(key: str) -> str:
    return _SAFE.sub("_", key).strip("_") or "item"


class SnapshotStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, stage: str) -> Path:
        d = self.root / safe_key(stage)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def next_version(self, stage: str, key: str) -> int:
        existing = list(self._dir(stage).glob(f"{safe_key(key)}.v*.json"))
        versions = [int(p.name.rsplit(".v", 1)[1].split(".")[0]) for p in existing]
        return (max(versions) + 1) if versions else 1

    def save(self, stage: str, key: str, parsed: Any, raw: str | None = None, meta: dict[str, Any] | None = None) -> Path:
        v = self.next_version(stage, key)
        path = self._dir(stage) / f"{safe_key(key)}.v{v}.json"
        record = {
            "stage": stage,
            "key": key,
            "version": v,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "meta": meta or {},
            "raw": raw,
            "parsed": parsed.model_dump(mode="json") if hasattr(parsed, "model_dump") else parsed,
        }
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def latest(self, stage: str, key: str) -> dict[str, Any] | None:
        existing = sorted(self._dir(stage).glob(f"{safe_key(key)}.v*.json"), key=lambda p: int(p.name.rsplit(".v", 1)[1].split(".")[0]))
        if not existing:
            return None
        return json.loads(existing[-1].read_text(encoding="utf-8"))

    def latest_parsed(self, stage: str, key: str, model: type | None = None) -> Any:
        rec = self.latest(stage, key)
        if rec is None:
            return None
        data = rec["parsed"]
        return model.model_validate(data) if model is not None and hasattr(model, "model_validate") else data

    def keys(self, stage: str) -> list[str]:
        seen: dict[str, None] = {}
        for p in sorted(self._dir(stage).glob("*.v*.json")):
            seen[p.name.rsplit(".v", 1)[0]] = None
        return list(seen)

    def all_latest(self, stage: str, model: type | None = None) -> dict[str, Any]:
        return {k: self.latest_parsed(stage, k, model) for k in self.keys(stage)}
