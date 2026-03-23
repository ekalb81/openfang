#!/usr/bin/env python3
"""Guard dashboard page wiring invariants in static/index_body.html.

This catches four lightweight but high-churn regression families:
1. Route page components from static/js/pages/*.js (plain factories or Alpine.data registrations)
   must be mounted by a matching x-data binding in static/index_body.html.
2. Route-root x-init handlers must only call methods that the page component actually defines.
3. Pages that expose route-leave cleanup hooks must wire the matching
   @page-leave.window="...()" handler on their route root.
4. Route-scoped Retry/Refresh buttons must only call methods that the page component actually defines.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = REPO_ROOT / "crates/openfang-api/static/js/pages"
INDEX_BODY = REPO_ROOT / "crates/openfang-api/static/index_body.html"

FACTORY_RE = re.compile(r"function\s+([A-Za-z0-9_]+Page)\s*\(")
ALPINE_DATA_RE = re.compile(r"Alpine\.data\(\s*['\"]([A-Za-z0-9_]+Page)['\"]")
ROUTE_LEAVE_HOOKS = {
    "destroy": re.compile(r"\bdestroy\s*(?:\(|:)"),
    "stopSSE": re.compile(r"\bstopSSE\s*(?:\(|:)"),
    "stopAutoRefresh": re.compile(r"\bstopAutoRefresh\s*(?:\(|:)"),
}
XDATA_RE = re.compile(r'x-data\s*=\s*"([^"]+)"')
XINIT_RE = re.compile(r'x-init\s*=\s*"([^"]+)"')
METHOD_DEF_RE = re.compile(
    r'^\s*(?:async\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(|^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?:async\s+)?function\s*\(',
    re.MULTILINE,
)
METHOD_CALL_RE = re.compile(r'(?<![.\w$])([A-Za-z_][A-Za-z0-9_]*)\s*\(')
BUTTON_CLICK_RE = re.compile(r'<button\b[^>]*@click\s*=\s*"([^"]+)"[^>]*>([^<]*)</button>')
ROUTE_TEMPLATE_RE = re.compile(r'<template\b[^>]*x-if\s*=\s*"page === \'([^\']+)\'"')


def page_leave_hook_re(hook_name: str) -> re.Pattern[str]:
    return re.compile(rf'@page-leave\.window\s*=\s*"{re.escape(hook_name)}\(\)"')


def defined_methods_in(js: str) -> set[str]:
    methods: set[str] = set()
    for match in METHOD_DEF_RE.finditer(js):
        methods.update(group for group in match.groups() if group)
    return methods


def direct_method_calls(expr: str) -> list[str]:
    return [method for method in METHOD_CALL_RE.findall(expr) if method not in {"if"}]


def collect_route_lines(index_lines: list[str]) -> dict[str, list[tuple[int, str]]]:
    route_lines: dict[str, list[tuple[int, str]]] = {}
    current_route: str | None = None
    template_depth = 0

    for line_number, line in enumerate(index_lines, start=1):
        if current_route is None:
            route_match = ROUTE_TEMPLATE_RE.search(line)
            if route_match:
                current_route = route_match.group(1)
                route_lines.setdefault(current_route, []).append((line_number, line))
                template_depth = line.count("<template") - line.count("</template>")
            continue

        route_lines[current_route].append((line_number, line))
        template_depth += line.count("<template") - line.count("</template>")
        if template_depth <= 0:
            current_route = None
            template_depth = 0

    return route_lines


def main() -> int:
    index_html = INDEX_BODY.read_text(encoding="utf-8")
    index_lines = index_html.splitlines()
    route_tags = []
    for line_number, line in enumerate(index_lines, start=1):
        xdata = XDATA_RE.search(line)
        if xdata:
            route_tags.append((xdata.group(1), line, line_number))
    route_lines = collect_route_lines(index_lines)

    errors: list[str] = []

    for page_file in sorted(PAGES_DIR.glob("*.js")):
        js = page_file.read_text(encoding="utf-8")
        factory_match = FACTORY_RE.search(js)
        alpine_data_match = ALPINE_DATA_RE.search(js)
        if not factory_match and not alpine_data_match:
            continue

        if factory_match:
            component_name = factory_match.group(1)
            expected_xdata_values = [f"{component_name}()"]
        else:
            component_name = alpine_data_match.group(1)
            expected_xdata_values = [component_name, f"{component_name}()"]

        matching_tags = [tag for tag in route_tags if tag[0] in expected_xdata_values]
        expected_display = " or ".join(f'x-data="{value}"' for value in expected_xdata_values)
        if not matching_tags:
            errors.append(
                f"{page_file.relative_to(REPO_ROOT)}: missing {expected_display} route binding in {INDEX_BODY.relative_to(REPO_ROOT)}"
            )
            continue

        defined_methods = defined_methods_in(js)

        for _, attrs, line_number in matching_tags:
            xinit = XINIT_RE.search(attrs)
            if not xinit:
                continue

            for method_name in direct_method_calls(xinit.group(1)):
                if method_name not in defined_methods:
                    errors.append(
                        f"{page_file.relative_to(REPO_ROOT)}:{line_number}: x-init references {method_name}() but {component_name} does not define it"
                    )

        route_name = page_file.stem
        for line_number, line in route_lines.get(route_name, []):
            for expr, label in BUTTON_CLICK_RE.findall(line):
                if label.strip() not in {"Retry", "Refresh"}:
                    continue

                for method_name in direct_method_calls(expr):
                    if method_name not in defined_methods:
                        errors.append(
                            f"{page_file.relative_to(REPO_ROOT)}:{line_number}: {label.strip()} button references {method_name}() but {component_name} does not define it"
                        )

        for hook_name, hook_re in ROUTE_LEAVE_HOOKS.items():
            if hook_re.search(js):
                page_leave_re = page_leave_hook_re(hook_name)
                if not any(page_leave_re.search(attrs) for _, attrs, _ in matching_tags):
                    errors.append(
                        f"{page_file.relative_to(REPO_ROOT)}: defines {hook_name}() but no matching {expected_display} tag wires @page-leave.window=\"{hook_name}()\""
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
