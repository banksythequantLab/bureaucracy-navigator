"""Dump AcroForm field names from an official USCIS PDF so schema pdf_field
values can be mapped (Week 2). Usage:

    python -m packages.forms.inspect packages/forms/i-765.pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader


def main(path: str) -> None:
    reader = PdfReader(path)
    fields = reader.get_fields() or {}
    print(f"{Path(path).name}: {len(fields)} fields, {len(reader.pages)} pages")
    for name, f in fields.items():
        ft = f.get("/FT")
        print(f"{ft!s:8} {name}")


if __name__ == "__main__":
    main(sys.argv[1])
