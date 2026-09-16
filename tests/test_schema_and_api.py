"""Schema loads, API boots, and keyless behaviour is explicit (503/502, not a crash)."""
import os

from fastapi.testclient import TestClient

from apps.api.app.main import app
from packages.schemas.loader import load_schema

client = TestClient(app)


def test_i765_schema_loads():
    s = load_schema("i-765")
    ids = [f.id for f in s.all_fields()]
    assert "category" in ids and "signature_type" in ids
    sev = {r.severity for r in s.all_risks()}
    assert sev <= {"reject", "rfe", "deny"}
    assert any(r.severity == "deny" for r in s.all_risks())  # signature rule present


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert "i-765" in r.json()["forms"]


def test_form_endpoint():
    r = client.get("/forms/i-765")
    assert r.status_code == 200
    assert r.json()["form"] == "i-765"


def test_explain_without_key_is_503():
    os.environ.pop("NEBIUS_API_KEY", None)
    from packages.agents import nebius

    nebius.client.cache_clear()
    r = client.post("/explain/i-765/category", json={"lang": "es"})
    assert r.status_code == 503
    assert "NEBIUS_API_KEY" in r.json()["detail"]
