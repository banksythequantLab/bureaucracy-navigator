"""Offline tests: uscis.gov parsers against fixtures shaped like the real extracts
(captured from Tavily Extract on 2026-09-16)."""
from packages.rules.snapshot import (
    parse_biometrics,
    parse_edition_alert,
    parse_edition_dates,
    parse_fee_row,
    parse_where_to_file,
)

FORM_PAGE = """
**ALERT:** We published a new edition of Form I-765, Application for Employment
Authorization (edition date: 09/15/26). The form has been revised to align with the
[rule](https://www.federalregister.gov/documents/2026/07/17/2026-14439/establishing).
|  | Edition Date |  | 08/21/25. You can find the edition date at the bottom of the page
on the form and instructions. |  | Dates are listed in mm/dd/yy format. |
|  | Where to File |  | Please check the [filing locations for Form I-765](/i-765-addresses)
for a list of addresses. |
|  | Filing Fee |  | You can find the filing fee for Form I-765 by visiting our
[Fee Schedule](/g-1055) page. |
"""

G1055 = """
Page 22 of 58 Form G-1055 Edition 09/09/26 Form Number and Title Filing Category Fee(s)
I-130 Petition for Alien Relative (uscis.gov/i-130) General filing Paper Filing: $675 Online Filing: $625
I-765 Application for Employment Authorization (uscis.gov/i-765) General filing for initial,
replacement, or renewal Employment Authorization Document (EAD), unless noted below.
Fee determined based on how form is submitted. | Paper Filing: $520 Online Filing: $470
If you are filing under category (c)(33) ... Paper Filing: $520 Online Filing: $470
N-400 Application for Naturalization (uscis.gov/n-400) General filing, unless noted below.
You cannot file online if you are requesting a fee waiver. | Paper Filing: $760 Online Filing: $710
If your documented annual household income is not more than 400 percent ... | Paper Filing: $380
"""


def test_edition_dates_ignores_url_dates():
    val, _ = parse_edition_dates(FORM_PAGE)
    assert val == "08/21/25"


def test_edition_alert():
    val, _ = parse_edition_alert(FORM_PAGE)
    assert val == "09/15/26"


def test_where_to_file():
    assert parse_where_to_file(FORM_PAGE) == "https://www.uscis.gov/i-765-addresses"


def test_fee_rows():
    r = parse_fee_row(G1055, "I-765 Application for Employment Authorization")
    assert (r["paper"], r["online"], r["schedule_edition"]) == ("$520", "$470", "09/09/26")
    r = parse_fee_row(G1055, "I-130 Petition for Alien Relative")
    assert (r["paper"], r["online"]) == ("$675", "$625")
    r = parse_fee_row(G1055, "N-400 Application for Naturalization")
    assert (r["paper"], r["online"]) == ("$760", "$710")


def test_missing_returns_empty():
    assert parse_edition_dates("nothing here") is None
    assert parse_fee_row("nothing here", "I-765 Application for Employment Authorization") == {}
    assert parse_biometrics("no such note") is None
