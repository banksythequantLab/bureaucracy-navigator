"""Interview answers → N-400 (edition 01/20/25) AcroForm field values.

Field names from `python -m packages.forms.inspect packages/forms/pdf/n-400.pdf`.
Quirks worth knowing (all verified against the tooltips dump):
  - The A-Number repeats on every page: #subform[N].#area[k].Line1_AlienNumber[N]
  - Trip row 1's countries box is misnamed P9_Line1_Countries1 (rows 2-6 are P8_Line1_CountriesN)
  - Mailing-address state values carry a leading space: " NY"
  - Three applicant signature widgets share the name P12_SignatureApplicant[0..2];
    [2] is the Part 12 applicant signature — none are ever filled.
"""
from __future__ import annotations

from typing import Any

from packages.forms.maps.i_765 import _date  # same MM/DD/YYYY convention

S = [f"form1[0].#subform[{i}]." for i in range(14)]

NEVER_FILL = {
    S[10] + "P12_SignatureApplicant[0]",
    S[11] + "P12_SignatureApplicant[1]",
    S[11] + "P12_SignatureApplicant[2]",
    S[13] + "Part15ApplicantsSignature[0]",
    S[13] + "ApplicantsSignature[0]",
}

# A-Number widgets: (subform index, area index, widget index) discovered in the dump
_ANUM = [(0, 0, 0), (1, 1, 1), (2, 2, 2), (5, 6, 5)]

_BASIS = {  # option → Part1_Eligibility widget index (see tooltips: A..G)
    "general_5yr": (2, "/A"), "spouse_3yr": (1, "/B"), "vawa": (0, "/C"),
    "spouse_abroad": (6, "/D"), "military_wartime": (3, "/E"), "military_1yr": (4, "/F"), "other": (5, "/G"),
}
_UNIT = {"flr": (0, "/FLR"), "ste": (1, "/STE"), "apt": (2, "/APT")}


def _yn(prefix: str, val: Any, *, yes_idx: int, no_idx: int, yes="/Y", no="/N") -> dict[str, str]:
    if val is True:
        return {f"{prefix}[{yes_idx}]": yes}
    if val is False:
        return {f"{prefix}[{no_idx}]": no}
    return {}


def _mailing(a: dict | None) -> dict[str, str]:
    if not a:
        return {}
    p = S[2] + "P4_Line1_"
    out = {
        p + "InCareOfName[0]": a.get("in_care_of", ""),
        p + "StreetName[0]": a.get("street", ""),
        p + "Number[0]": a.get("unit", ""),
        p + "City[0]": a.get("city", ""),
        p + "State[0]": f" {a['state']}" if a.get("state") else "",
        p + "ZipCode[0]": a.get("zip", ""),
        p + "Country[0]": a.get("country", ""),
    }
    ut = (a.get("unit_type") or "").lower()
    if ut in _UNIT and a.get("unit"):
        i, v = _UNIT[ut]
        out[p + f"Unit[{i}]"] = v
    return out


def map_answers(a: dict[str, Any]) -> dict[str, str]:
    f: dict[str, str] = {}

    if a.get("basis") in _BASIS:
        i, v = _BASIS[a["basis"]]
        f[S[0] + f"Part1_Eligibility[{i}]"] = v
    anum = (a.get("a_number") or "").lstrip("Aa")
    for sub, area, w in _ANUM:
        f[S[sub] + f"#area[{area}].Line1_AlienNumber[{w}]"] = anum

    n = a.get("full_name") or {}
    f[S[0] + "P2_Line1_FamilyName[0]"] = n.get("family", "")
    f[S[0] + "P2_Line1_GivenName[0]"] = n.get("given", "")
    f[S[0] + "P2_Line1_MiddleName[0]"] = n.get("middle", "")
    for idx, on in enumerate((a.get("other_names") or [])[:2], start=1):
        f[S[0] + f"Line2_FamilyName{idx}[0]"] = on.get("family", "")
        f[S[0] + f"Line3_GivenName{idx}[0]"] = on.get("given", "")
        f[S[0] + f"Line3_MiddleName{idx}[0]"] = on.get("middle", "")

    f.update(_yn(S[1] + "P2_Line34_NameChange", a.get("name_change"), yes_idx=1, no_idx=0))
    if a.get("name_change") and a.get("new_name"):
        nn = a["new_name"]
        f[S[1] + "Part2Line3_FamilyName[0]"] = nn.get("family", "")
        f[S[1] + "Part2Line4a_GivenName[0]"] = nn.get("given", "")
        f[S[1] + "Part2Line4a_MiddleName[0]"] = nn.get("middle", "")
    f[S[1] + "P2_Line6_USCISELISAcctNumber[0]"] = a.get("uscis_online_account") or ""
    if a.get("sex") == "male":
        f[S[1] + "P2_Line7_Gender[0]"] = "/M"
    elif a.get("sex") == "female":
        f[S[1] + "P2_Line7_Gender[1]"] = "/F"
    f[S[1] + "P2_Line8_DateOfBirth[0]"] = _date(a.get("dob"))
    f[S[1] + "P2_Line9_DateBecamePermanentResident[0]"] = _date(a.get("lpr_date"))
    f[S[1] + "P2_Line10_CountryOfBirth[0]"] = a.get("country_of_birth") or ""
    f[S[1] + "P2_Line11_CountryOfNationality[0]"] = a.get("nationality") or ""
    f.update(_yn(S[1] + "P2_Line10_claimdisability", a.get("disability_accommodation"), yes_idx=1, no_idx=0))
    f.update(_yn(S[1] + "Line12a_Checkbox", a.get("ssn_apply"), yes_idx=1, no_idx=0))
    f[S[1] + "Line12b_SSN[0]"] = a.get("ssn") or ""
    if a.get("ssn_apply") is True:  # 12.C disclosure consent goes with 12.A
        f[S[1] + "Line12\\.c_Checkbox[1]"] = "/Y"

    pa = a.get("physical_address") or {}
    if pa:
        f[S[2] + "P4_Line3_PhysicalAddress1[0]"] = " ".join(x for x in (pa.get("street"), pa.get("unit")) if x)
        f[S[2] + "P4_Line3_CityTown1[0]"] = pa.get("city", "")
        f[S[2] + "P4_Line3_State1[0]"] = pa.get("state", "")
        f[S[2] + "P4_Line3_ZipCode1[0]"] = pa.get("zip", "")
        f[S[2] + "P4_Line3_Country1[0]"] = pa.get("country", "USA")
        f[S[2] + "P4_Line3_From1[0]"] = _date(a.get("physical_address_since"))
        f[S[2] + "P4_Line3_From1[1]"] = "Present"
    same = a.get("mailing_same_as_physical")
    f.update(_yn(S[2] + "Pt3_Line2a_Checkbox", same, yes_idx=1, no_idx=0))
    if same is False:
        f.update(_mailing(a.get("mailing_address")))

    for i, t in enumerate((a.get("trips") or [])[:6], start=1):
        f[S[5] + f"P8_Line1_DateLeft{i}[0]"] = _date(t.get("left"))
        f[S[5] + f"P8_Line1_DateReturn{i}[0]"] = _date(t.get("returned"))
        cname = "P9_Line1_Countries1[0]" if i == 1 else f"P8_Line1_Countries{i}[0]"
        f[S[5] + cname] = t.get("countries", "")

    f.update(_yn(S[5] + "P9_Line1", a.get("claimed_citizen"), yes_idx=1, no_idx=0))
    f.update(_yn(S[5] + "P9_Line2", a.get("voted"), yes_idx=1, no_idx=0))
    f.update(_yn(S[5] + "P9_Line3", a.get("overdue_taxes"), yes_idx=0, no_idx=1))  # note: [0]=Yes on this item
    f.update(_yn(S[5] + "P9_Line4", a.get("nonresident_tax"), yes_idx=1, no_idx=0))

    f[S[10] + "P12_Line3_Telephone[0]"] = a.get("daytime_phone") or ""
    f[S[10] + "P12_Line3_Mobile[0]"] = a.get("mobile_phone") or ""
    f[S[10] + "P12_Line5_Email[0]"] = a.get("email") or ""
    f[S[10] + "P13_DateofSignature[0]"] = _date(a.get("signature_date"))

    assert not (set(f) & NEVER_FILL), "refusing to fill a signature field"
    return {k: v for k, v in f.items() if v != ""}
