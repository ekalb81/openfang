#!/usr/bin/env python3
"""Guard dashboard page wiring invariants in static/index_body.html.

This catches two lightweight but high-churn regression families:
1. Plain page factories from static/js/pages/*.js must be invoked as x-data="...Page()".
2. Pages that expose destroy() must wire @page-leave.window="destroy()" on their route root.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = REPO_ROOT / "crates/openfang-api/static/js/pages"
INDEX_BODY = REPO_ROOT / "crates/openfang-api/static/index_body.html"

FACTORY_RE = re.compile(r"function\s+([A-Za-z0-9_]+Page)\s*\(")
DESTROY_RE = re.compile(r"\bdestroy\s*(?:\(|:)")
TAG_RE = re.compile(r"<(?P<tag>[a-zA-Z0-9:-]+)\b(?P<attrs>[^>]*)>", re.DOTALL)
XDATA_RE = re.compile(r'x-data\s*=\s*"([^"]+)"')
PAGE_LEAVE_DESTROY_RE = re.compile(r'@page-leave\.window\s*=\s*"destroy\(\)"')


def main() -> int:
    index_html = INDEX_BODY.read_text(encoding="utf-8")
    route_tags = []
    for match in TAG_RE.finditer(index_html):
        attrs = match.group("attrs")
        xdata = XDATA_RE.search(attrs)
        if xdata:
            route_tags.append((xdata.group(1), attrs, match.start()))

    errors: list[str] = []

    for page_file in sorted(PAGES_DIR.glob("*.js")):
        js = page_file.read_text(encoding="utf-8")
        factory_match = FACTORY_RE.search(js)
        if not factory_match:
            continue

        factory_name = factory_match.group(1)
        expected_xdata = f"{factory_name}()"
        matching_tags = [tag for tag in route_tags if tag[0] == expected_xdata]
        if not matching_tags:
            errors.append(
                f"{page_file.relative_to(REPO_ROOT)}: missing x-data=\"{expected_xdata}\" route binding in {INDEX_BODY.relative_to(REPO_ROOT)}"
            )
            continue

        if DESTROY_RE.search(js):
            if not any(PAGE_LEAVE_DESTROY_RE.search(attrs) for _, attrs, _ in matching_tags):
                errors.append(
                    f"{page_file.relative_to(REPO_ROOT)}: defines destroy() but no matching x-data=\"{expected_xdata}\" tag wires @page-leave.window=\"destroy()\""
                )

    if errors:
        print("Dashboard page wiring check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Dashboard page wiring check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
