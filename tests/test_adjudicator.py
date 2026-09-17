import os

from packages.agents import adjudicator
from packages.rules.checks import Finding
from packages.schemas.loader import load_schema


def test_offline_returns_nothing():
    os.environ.pop("NEBIUS_API_KEY", None)
    f, note = adjudicator.review(load_schema("i-765"), {}, [], None)
    assert f == [] and note == {}


def test_merge_keeps_deterministic_severity():
    det = [Finding(id="invalid_signature", severity="deny", text_en="x")]
    model = [Finding(id="invalid_signature", severity="info", text_en="model says meh", source="model"),
             Finding(id="dates_conflict", severity="rfe", text_en="y", source="model")]
    out = adjudicator.merge(det, model)
    assert [f.id for f in out] == ["invalid_signature", "dates_conflict"]
    assert out[0].severity == "deny" and out[0].text_en == "x"
