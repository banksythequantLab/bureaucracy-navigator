import os
from fastapi.testclient import TestClient

os.environ.pop("NEBIUS_API_KEY", None)
from apps.api.app.main import app  # noqa: E402

c = TestClient(app)


def test_demo_seeds_complete_session_for_every_form():
    for form in ("i-765", "n-400", "i-130"):
        r = c.post(f"/interview/demo/{form}?lang=es")
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["done"] is True and st["progress"]["answered"] == st["progress"]["total"]
        chk = c.post(f"/interview/{st['session_id']}/check?live=false").json()
        assert chk["counts"]  # the fixtures are deliberately flawed
