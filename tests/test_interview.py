import json
import os
from pathlib import Path

os.environ["BN_SESSION_DIR"] = ".cache/test-sessions"
os.environ.pop("NEBIUS_API_KEY", None)

from packages.agents import interview as iv  # noqa: E402
from packages.schemas.loader import load_schema  # noqa: E402

ANSWERS = json.loads(Path("tests/fixtures/i765_answers.json").read_text())
SCHEMA = load_schema("i-765")


def test_walkthrough_offline_reaches_done():
    s = iv.start("i-765", "es")
    q = iv.question_for(SCHEMA, s)
    assert q and q.field_id == "reason" and "¿" in q.text  # Spanish label fallback
    steps = 0
    while (q := iv.question_for(SCHEMA, s)) is not None:
        steps += 1
        assert steps < 60
        raw = ANSWERS.get(q.field_id)
        if raw is None or raw == "" or raw == []:
            iv.answer(SCHEMA, s, q.field_id, None, skip=True)
        else:
            iv.answer(SCHEMA, s, q.field_id, raw)
    p = iv.progress(SCHEMA, s)
    assert p["answered"] == p["total"]
    # required_when: physical_address never asked because mailing_same_as_physical is True
    assert "physical_address" not in s.answers and "physical_address" not in s.skipped
    # c8_arrested WAS asked because category == (c)(8)
    assert "c8_arrested" in s.answers
    assert iv.Session.load(s.id).answers["category"] == "(c)(8)"


def test_parse_free_text():
    f = {x.id: x for x in SCHEMA.all_fields()}
    assert iv.parse(f["prior_i765"], "Sí", "es") is True
    assert iv.parse(f["reason"], "Renewal", "en") == "renewal"
    assert iv.parse(f["dob"], "4/17/1991", "en") == "1991-04-17"
    assert iv.parse(f["category"], "c 8", "en") == "(c)(8)"
    assert iv.parse(f["category"], "(c)(17)(iii)", "en") == "(c)(17)(iii)"


def test_required_skip_rejected():
    s = iv.start("i-765")
    try:
        iv.answer(SCHEMA, s, "reason", None, skip=True)
        assert False, "should raise"
    except ValueError:
        pass
