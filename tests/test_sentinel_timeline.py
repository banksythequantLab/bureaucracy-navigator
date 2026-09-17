import os
from datetime import date

os.environ["BN_CASE_DIR"] = ".cache/test-cases"
os.environ.pop("NEBIUS_API_KEY", None)
os.environ.pop("TAVILY_API_KEY", None)

from packages.agents import sentinel  # noqa: E402
from packages.rules.timeline import predict, select_key  # noqa: E402


def test_timeline_keys_and_fallback():
    t = predict("i-130", {"petitioner_status": "lpr", "relationship": "spouse"}, "2026-09-20")
    assert t.key == "lpr:spouse" and t.stale is True and t.min_months == 45
    assert t.earliest == "2030-06-21" or t.earliest.startswith("2030")
    assert select_key("i-765", {"category": "(c)(8)"}) == "(c)(8)"
    assert predict("i-765", {"category": "(c)(99)"}).key == "default"


def test_deadlines_i765_renewal():
    today = date(2026, 9, 17)
    c = sentinel.new_case("i-765", "es", email="x@example.com", filed_on="2026-09-10",
                          ead_expires="2026-10-25", answers={"category": "(c)(8)"})
    ids = {d.id: d for d in sentinel.compute_deadlines(c, today)}
    assert ids["ead_renewal_window_opens"].urgency == "overdue"       # window opened Apr 28
    assert ids["ead_expires"].days_left == 38 and ids["ead_expires"].urgency == "soon"
    assert "outside_normal_processing" in ids
    due = sentinel.due_now(c, today)
    assert {d.id for d in due} >= {"ead_expires", "ead_renewal_window_opens"}
    subject, body = sentinel.render_nudge(c, due)
    assert "fecha(s)" in subject and "8 CFR 274a.13(d)" in body
    c.delete()


def test_n400_window_and_rfe_default():
    today = date(2026, 9, 17)
    c = sentinel.new_case("n-400", "en", lpr_since="2021-12-15", basis="general_5yr", rfe_received_on="2026-08-01")
    ids = {d.id: d for d in sentinel.compute_deadlines(c, today)}
    assert ids["n400_early_filing_window"].due == "2026-09-16"          # Dec 15 2026 minus 90 days
    assert ids["rfe_response"].due == "2026-10-27"                      # Aug 1 + 87 days
    c.delete()


def test_run_once_dry_run_and_throttle():
    today = date(2026, 9, 17)
    c = sentinel.new_case("i-765", "en", email="y@example.com", ead_expires="2026-09-30")
    r = sentinel.run_once(today, dry_run=True)
    assert any(x["case"] == c.id and not x["sent"] for x in r)
    r2 = sentinel.run_once(today)            # no SMTP → sent False, but notified recorded
    c2 = sentinel.Case.load(c.id)
    assert c2.notified.get("ead_expires") == "2026-09-17"
    assert sentinel.due_now(c2, today) == []  # throttled for 7 days
    c.delete()
