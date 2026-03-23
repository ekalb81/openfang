#!/usr/bin/env python3
"""Guard dashboard page wiring invariants in static/index_body.html.

This catches two lightweight but high-churn regression families:
1. Plain page factories from static/js/pages/*.js must be invoked as x-data="...Page()".
2. Pages that expose route-leave cleanup hooks must wire the matching @page-leave.window="...()" handler on their route root.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = REPO_ROOT / "crates/openfang-api/static/js/pages"
INDEX_BODY = REPO_ROOT / "crates/openfang-api/static/index_body.html"

FACTORY_RE = re.compile(r"function\s+([A-Za-z0-9_]+Page)\s*\(")
ROUTE_LEAVE_HOOKS = {
    "destroy": re.compile(r"\bdestroy\s*(?:\(|:)"),
    "stopSSE": re.compile(r"\bstopSSE\s*(?:\(|:)"),
    "stopAutoRefresh": re.compile(r"\bstopAutoRefresh\s*(?:\(|:)"),
}
XDATA_RE = re.compile(r'x-data\s*=\s*"([^"]+)"')


def page_leave_hook_re(hook_name: str) -> re.Pattern[str]:
    return re.compile(rf'@page-leave\.window\s*=\s*"{re.escape(hook_name)}\(\)"')


def main() -> int:
    index_html = INDEX_BODY.read_text(encoding="utf-8")
    route_tags = []
    for line_number, line in enumerate(index_html.splitlines(), start=1):
        xdata = XDATA_RE.search(line)
        if xdata:
            route_tags.append((xdata.group(1), line, line_number))

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

        for hook_name, hook_re in ROUTE_LEAVE_HOOKS.items():
            if hook_re.search(js):
                page_leave_re = page_leave_hook_re(hook_name)
                if not any(page_leave_re.search(attrs) for _, attrs, _ in matching_tags):
                    errors.append(
                        f"{page_file.relative_to(REPO_ROOT)}: defines {hook_name}() but no matching x-data=\"{expected_xdata}\" tag wires @page-leave.window=\"{hook_name}()\""
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
