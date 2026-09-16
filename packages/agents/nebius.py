"""Nebius Token Factory client (OpenAI-compatible) hosting NVIDIA Nemotron.

Two tiers:
  REASONING_MODEL  - interview branching, adjudicator pass (Nemotron 3 Super 120B)
  FAST_MODEL       - field explanations, translation, sentinel nudges (Nemotron 3 Nano)

Model IDs are read from .env so they can be corrected from the Token Factory
console without a code change. Only the Super ID is confirmed on the public page;
verify the Nano ID at https://tokenfactory.nebius.com before first run.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

NEBIUS_BASE_URL = os.getenv(
    "NEBIUS_BASE_URL", "https://api.tokenfactory.us-central1.nebius.com/v1/"
)
REASONING_MODEL = os.getenv("NEBIUS_REASONING_MODEL", "nvidia/nemotron-3-super-120b-a12b")
FAST_MODEL = os.getenv("NEBIUS_FAST_MODEL", "nvidia/nemotron-3-nano-30b-a3b")

T = TypeVar("T", bound=BaseModel)


class MissingKeyError(RuntimeError):
    """Raised when NEBIUS_API_KEY is not configured."""


@lru_cache(maxsize=1)
def client() -> OpenAI:
    key = os.getenv("NEBIUS_API_KEY")
    if not key:
        raise MissingKeyError(
            "NEBIUS_API_KEY is not set. Create one at https://tokenfactory.nebius.com "
            "and put it in .env (see .env.example)."
        )
    return OpenAI(api_key=key, base_url=NEBIUS_BASE_URL)


def chat(system: str, user: str, *, model: str = FAST_MODEL, temperature: float = 0.2) -> str:
    """Plain text completion."""
    resp = client().chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return resp.choices[0].message.content or ""


def structured(system: str, user: str, schema: Type[T], *, model: str = REASONING_MODEL) -> T:
    """Completion parsed into a Pydantic model via JSON-schema response_format.

    Falls back to json_object mode + manual validation if the endpoint rejects
    json_schema (some open-model backends only support json_object).
    """
    try:
        resp = client().chat.completions.parse(
            model=model,
            temperature=0,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format=schema,
        )
        parsed = resp.choices[0].message.parsed
        if parsed is not None:
            return parsed
    except Exception:  # noqa: BLE001 - fall through to json_object mode
        pass
    resp = client().chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system + "\nRespond with JSON matching this schema: "
             + schema.model_json_schema().__repr__()},
            {"role": "user", "content": user},
        ],
    )
    return schema.model_validate_json(resp.choices[0].message.content or "{}")
