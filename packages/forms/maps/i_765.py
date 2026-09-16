"""Interview answers → I-765 (edition 08/21/25) AcroForm field values.

Field names come from `python -m packages.forms.inspect packages/forms/pdf/i-765.pdf`.
Checkbox values are the widget's "on" state name (e.g. "/Y"); text is plain str.

Deliberately NOT mapped:
  Pt3Line7a_Signature  — the PDF says "This form can not be signed electronically.
                         The name of the applicant can not be typewritten into this
                         space." Filling it would create the exact denial trigger the
                         adjudicator warns about.
"""
from __future__ import annotations

from typing import Any

P1 = "form1[0].Page1[0]."
P2 = "form1[0].Page2[0]."
P3 = "form1[0].Page3[0]."
P4 = "form1[0].Page4[0]."

NEVER_FILL = {P4 + "Pt3Line7a_Signature[0]"}

_UNIT_STATES = {"apt": "/ APT ", "ste": "/ STE ", "flr": "/ FLR "}
_UNIT_INDEX = {"ste": 0, "flr": 1, "apt": 2}  # widget order in the PDF


def _name(prefix: str, n: dict | None, idx: int = 0) -> dict[str, str]:
    if not n:
        return {}
    return {
        f"{prefix}a_FamilyName[{idx}]": n.get("family", ""),
        f"{prefix}b_GivenName[{idx}]": n.get("given", ""),
        f"{prefix}c_MiddleName[{idx}]": n.get("middle", ""),
    }


def _address(a: dict | None, *, street: str, unit_base: str, unit_num: str, city: str,
             state: str, zip_: str, in_care_of: str | None = None) -> dict[str, str]:
    if not a:
        return {}
    out = {
        street: a.get("street", ""),
        unit_num: a.get("unit", ""),
        city: a.get("city", ""),
        state: a.get("state", ""),
        zip_: a.get("zip", ""),
    }
    if in_care_of is not None:
        out[in_care_of] = a.get("in_care_of", "")
    ut = (a.get("unit_type") or "").lower()
    if ut in _UNIT_STATES and a.get("unit"):
        out[f"{unit_base}[{_UNIT_INDEX[ut]}]"] = _UNIT_STATES[ut]
    return out


def _date(d: str | None) -> str:
    """Accept YYYY-MM-DD or MM/DD/YYYY; emit MM/DD/YYYY as the form asks."""
    if not d:
        return ""
    if "-" in d and len(d) == 10:
        y, m, dd = d.split("-")
        return f"{m}/{dd}/{y}"
    return d


def _category_chunks(cat: str | None) -> dict[str, str]:
    """'(c)(8)' → '(c)(', '8)', ''   ;  '(c)(17)(iii)' → '(c)(', '17)', '(iii)'."""
    s = (cat or "").replace(" ", "")
    return {
        P3 + "#area[1].section_1[0]": s[0:4],
        P3 + "#area[1].section_2[0]": s[4:7],
        P3 + "#area[1].section_3[0]": s[7:10],
    }


def map_answers(a: dict[str, Any]) -> dict[str, str]:
    f: dict[str, str] = {}

    reason = {"initial": 0, "replacement": 1, "renewal": 2}.get(a.get("reason") or "")
    if reason is not None:
        f[P1 + f"Part1_Checkbox[{reason}]"] = f"/{reason + 1}"

    f.update(_name(P1 + "Line1", a.get("full_name")))
    others = a.get("other_names") or []
    slots = [(P1 + "Line2", 0), (P1 + "Line3", 0), (P1 + "Line3", 1)]
    for n, (pfx, idx) in zip(others[:3], slots):
        f.update(_name(pfx, n, idx))

    f.update(_address(a.get("mailing_address"),
                      street=P2 + "Line4b_StreetNumberName[0]", unit_base=P2 + "Pt2Line5_Unit",
                      unit_num=P2 + "Pt2Line5_AptSteFlrNumber[0]", city=P2 + "Pt2Line5_CityOrTown[0]",
                      state=P2 + "Pt2Line5_State[0]", zip_=P2 + "Pt2Line5_ZipCode[0]",
                      in_care_of=P2 + "Line4a_InCareofName[0]"))
    same = a.get("mailing_same_as_physical")
    if same is True:
        f[P2 + "Part2Line5_Checkbox[1]"] = "/Y"
    elif same is False:
        f[P2 + "Part2Line5_Checkbox[0]"] = "/N"
        f.update(_address(a.get("physical_address"),
                          street=P2 + "Pt2Line7_StreetNumberName[0]", unit_base=P2 + "Pt2Line7_Unit",
                          unit_num=P2 + "Pt2Line7_AptSteFlrNumber[0]", city=P2 + "Pt2Line7_CityOrTown[0]",
                          state=P2 + "Pt2Line7_State[0]", zip_=P2 + "Pt2Line7_ZipCode[0]"))

    f[P2 + "Line7_AlienNumber[0]"] = (a.get("a_number") or "").lstrip("Aa")
    f[P2 + "Line8_ElisAccountNumber[0]"] = a.get("uscis_online_account") or ""
    if a.get("sex") == "female":
        f[P2 + "Line9_Checkbox[0]"] = "/N"
    elif a.get("sex") == "male":
        f[P2 + "Line9_Checkbox[1]"] = "/Y"
    ms = {"widowed": (0, "/Widowed"), "divorced": (1, "/Divorced"), "single": (2, "/Single"), "married": (3, "/Married")}
    if a.get("marital_status") in ms:
        i, v = ms[a["marital_status"]]
        f[P2 + f"Line10_Checkbox[{i}]"] = v
    if a.get("prior_i765") is True:
        f[P2 + "Line19_Checkbox[1]"] = "/Y"
    elif a.get("prior_i765") is False:
        f[P2 + "Line19_Checkbox[0]"] = "/N"
    f[P2 + "Line12b_SSN[0]"] = a.get("ssn") or ""
    cits = a.get("citizenship_countries") or []
    f[P2 + "Line17a_CountryOfBirth[0]"] = cits[0] if len(cits) > 0 else ""
    f[P2 + "Line17b_CountryOfBirth[0]"] = cits[1] if len(cits) > 1 else ""

    pob = a.get("place_of_birth") or {}
    f[P3 + "Line18a_CityTownOfBirth[0]"] = pob.get("city", "")
    f[P3 + "Line18b_CityTownOfBirth[0]"] = pob.get("state", "")
    f[P3 + "Line18c_CountryOfBirth[0]"] = pob.get("country", "")
    f[P3 + "Line19_DOB[0]"] = _date(a.get("dob"))

    f[P3 + "Line20a_I94Number[0]"] = a.get("i94_number") or ""
    pp = a.get("passport") or {}
    f[P3 + "Line20b_Passport[0]"] = pp.get("number", "")
    f[P3 + "Line20c_TravelDoc[0]"] = pp.get("travel_doc_number", "")
    f[P3 + "Line20d_CountryOfIssuance[0]"] = pp.get("country", "")
    f[P3 + "Line20e_ExpDate[0]"] = _date(pp.get("expires"))
    f[P3 + "Line21_DateOfLastEntry[0]"] = _date(a.get("last_entry_date"))
    f[P3 + "place_entry[0]"] = a.get("last_entry_place") or ""
    f[P3 + "Line23_StatusLastEntry[0]"] = a.get("status_at_entry") or ""
    f[P3 + "Line24_CurrentStatus[0]"] = a.get("current_status") or ""

    f.update(_category_chunks(a.get("category")))
    if a.get("c8_arrested") is True:
        f[P3 + "PtLine29_YesNo[0]"] = "/Y"
    elif a.get("c8_arrested") is False:
        f[P3 + "PtLine29_YesNo[1]"] = "/N"

    if a.get("read_language") == "english":
        f[P4 + "Pt3Line1Checkbox[1]"] = "/A"
    elif a.get("read_language") == "interpreter":
        f[P4 + "Pt3Line1Checkbox[0]"] = "/B"
        f[P4 + "Pt3Line1b_Language[0]"] = a.get("interpreter_language") or ""
    if a.get("used_preparer") is True:
        f[P4 + "Part3_Checkbox[0]"] = "/C"
    f[P4 + "Pt3Line3_DaytimePhoneNumber1[0]"] = a.get("daytime_phone") or ""
    f[P4 + "Pt3Line4_MobileNumber1[0]"] = a.get("mobile_phone") or ""
    f[P4 + "Pt3Line5_Email[0]"] = a.get("email") or ""
    # Signature date is fine to prefill; the signature itself is never filled.
    f[P4 + "Pt3Line7b_DateofSignature[0]"] = _date(a.get("signature_date"))

    assert not (set(f) & NEVER_FILL), "refusing to fill the signature field"
    return {k: v for k, v in f.items() if v != ""}
