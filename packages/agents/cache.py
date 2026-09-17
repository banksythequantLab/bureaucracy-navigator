"""Tiny disk cache for deterministic-enough model outputs (question phrasing, field explanations).

Key = sha256(model + prompt material). Stored as JSON under BN_MODEL_CACHE_DIR
(default .cache/model). Phrasing and explanations depend only on the schema text,
language and model, so caching them is safe and makes repeat interviews instant.
Adjudication and free-text parsing are NOT cached (they depend on the applicant).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Optional

CACHE_DIR = Path(os.getenv("BN_MODEL_CACHE_DIR", ".cache/model"))


def _key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:32]


def get(*parts: str) -> Optional[str]:
    p = CACHE_DIR / f"{_key(*parts)}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))["text"]
    except Exception:  # noqa: BLE001
        return None


def put(text: str, *parts: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{_key(*parts)}.json").write_text(json.dumps({"text": text, "key_parts": len(parts)}), encoding="utf-8")


def cached(fn: Callable[[], str], *parts: str) -> str:
    hit = get(*parts)
    if hit is not None:
        return hit
    out = fn()
    if out:
        put(out, *parts)
    return out
