"""Processing-time predictor.

USCIS publishes processing times per form / category / office at
egov.uscis.gov/processing-times, which is JS-rendered AND refuses non-browser
fetches (Tavily Extract returns "Failed to fetch url"). Live path therefore reads
a monthly-updated third-party compilation of the USCIS numbers (manifestlaw.com)
via Tavily Extract and parses the "X to Y months" range next to the category;
the source is labelled as such. Fallback: packages/rules/known/processing_times.json
(compiled Sep 2026), flagged `stale=True`.

The key is chosen from the applicant's answers:
  i-765 → category code           n-400 → default
  i-130 → f"{petitioner_status}:{relationship}"
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

KNOWN = Path(__file__).parent / "known" / "processing_times.json"
LIVE_PAGE = "https://egov.uscis.gov/processing-times/"  # authoritative, but unfetchable headlessly
LIVE_SOURCES = {  # third-party compilations that Tavily can read; updated monthly
    "i-765": "https://manifestlaw.com/blog/i765-processing-time",
    "n-400": "https://manifestlaw.com/blog/uscis-processing-times",
    "i-130": "https://manifestlaw.com/blog/i-130-processing-time",
}
LIVE_ANCHORS = {  # text to look for near the range, per key; falls back to the form's headline range
    ("i-765", "(c)(8):initial"): "Pending asylum - initial",
    ("i-765", "(c)(8):renewal"): "Pending asylum - renewal",
    ("i-765", "(c)(9)"): "Pending I-485",
    ("i-765", "(a)(12)"): "TPS",
    ("n-400", "default"): "N-400 | Application for Naturalization",
    ("i-130", "usc:spouse"): "spouse, parent, or unmarried child under 21",
    ("i-130", "usc:parent"): "spouse, parent, or unmarried child under 21",
    ("i-130", "usc:child"): "spouse, parent, or unmarried child under 21",
    ("i-130", "usc:sibling"): "Sibling",
    ("i-130", "lpr:spouse"): "Green card holder",
    ("i-130", "lpr:child"): "Green card holder",
}


class Timeline(BaseModel):
    form: str
    key: str
    label: str
    min_months: float
    max_months: float
    as_of: str
    stale: bool
    source: str
    filed_on: Optional[str] = None
    earliest: Optional[str] = None
    latest: Optional[str] = None
    inquiry_after: Optional[str] = None  # USCIS lets you ask about a case once it is past the posted time


def select_key(form: str, answers: dict[str, Any]) -> str:
    if form == "i-765":
        cat = (answers.get("category") or "default").replace(" ", "")
        if cat == "(c)(8)":  # USCIS posts separate times for initial vs renewal asylum EADs
            return f"(c)(8):{'renewal' if answers.get('reason') == 'renewal' else 'initial'}"
        return cat
    if form == "i-130":
        return f"{answers.get('petitioner_status') or 'usc'}:{answers.get('relationship') or 'spouse'}"
    return "default"


def _known(form: str, key: str) -> Timeline:
    d = json.loads(KNOWN.read_text(encoding="utf-8"))
    table = d["forms"].get(form, {})
    base = key.split(":")[0] if form == "i-765" else key
    row = table.get(key) or table.get(base) or table["default"]
    return Timeline(form=form, key=key if (key in table or base in table) else "default", label=row["label"],
                    min_months=row["min_months"], max_months=row["max_months"],
                    as_of=d["as_of"], stale=True, source=d["source"])


_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)\s*months", re.I)
_SINGLE = re.compile(r"\|\s*(\d+(?:\.\d+)?)\s*months?\s*\|", re.I)


def _live(form: str, key: str) -> Optional[Timeline]:
    """Best-effort live read of a monthly-updated compilation. None when Tavily is unavailable or nothing parses."""
    if not os.getenv("TAVILY_API_KEY") or form not in LIVE_SOURCES:
        return None
    url = LIVE_SOURCES[form]
    try:
        from tavily import TavilyClient

        resp = TavilyClient(api_key=os.getenv("TAVILY_API_KEY")).extract(urls=[url], extract_depth="basic", format="text")
        md = " ".join(r.get("raw_content", "") for r in resp.get("results", []))
    except Exception:  # noqa: BLE001
        return None
    if not md:
        return None
    anchor = LIVE_ANCHORS.get((form, key))
    window = md
    label = f"{form.upper()} — headline range"
    if anchor:
        i = md.lower().find(anchor.lower())
        if i >= 0:
            window = md[i : i + 400]
            label = f"{form.upper()} — {anchor.split(' | ')[0]}"
    # take whichever appears first after the anchor: "X to Y months" or a single "| N months |" cell
    m, m1 = _RANGE.search(window), _SINGLE.search(window)
    if m and (not m1 or m.start() <= m1.start()):
        lo, hi = float(m.group(1)), float(m.group(2))
    elif m1:
        lo = hi = float(m1.group(1))
    else:
        return None
    month = re.search(r"As of ([A-Z][a-z]+ \d{4})", md)
    return Timeline(form=form, key=key, label=label, min_months=lo, max_months=hi,
                    as_of=(month.group(1) if month else date.today().isoformat()), stale=False,
                    source=url + "  (third-party compilation of egov.uscis.gov data)")


def _add_months(d: date, months: float) -> date:
    return d + timedelta(days=round(months * 30.44))


def predict(form: str, answers: dict[str, Any], filed_on: str | date | None = None) -> Timeline:
    key = select_key(form, answers)
    t = _live(form, key) or _known(form, key)
    if filed_on:
        f = date.fromisoformat(filed_on) if isinstance(filed_on, str) else filed_on
        t.filed_on = f.isoformat()
        t.earliest = _add_months(f, t.min_months).isoformat()
        t.latest = _add_months(f, t.max_months).isoformat()
        t.inquiry_after = t.latest
    return t
