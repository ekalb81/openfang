#!/usr/bin/env python3
"""Guard dashboard page wiring invariants in static/index_body.html.

This catches four lightweight but high-churn regression families:
1. Route page components from static/js/pages/*.js (plain factories or Alpine.data registrations)
   must be mounted by a matching x-data binding in static/index_body.html.
2. Route-root and route-scoped event/init handlers must only call methods that the page
   component actually defines.
3. Route-scoped state bindings (x-show/x-if/x-text/:disabled/etc.) must only reference
   Loading/Error members that the page component actually defines.
4. Pages that expose route-leave cleanup hooks must wire those hooks on the matching route root.
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
GETTER_DEF_RE = re.compile(r'^\s*get\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(', re.MULTILINE)
STATE_DEF_RE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?!\s*(?:async\s+)?function\b)', re.MULTILINE)
METHOD_CALL_RE = re.compile(r'(?<![.\w$])([A-Za-z_][A-Za-z0-9_]*)\s*\(')
BUTTON_CLICK_RE = re.compile(r'<button\b[^>]*@click\s*=\s*"([^"]+)"[^>]*>(.*?)</button>', re.DOTALL)
EVENT_ATTR_RE = re.compile(r'@[A-Za-z0-9_.:-]+\s*=\s*"([^"]+)"')
STRING_LITERAL_RE = re.compile(r"('(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")")
IGNORED_CALLEES = {"if", "Number", "String", "Boolean", "Object", "Array", "Date", "Math", "JSON", "parseInt", "parseFloat", "encodeURIComponent", "decodeURIComponent"}
ROUTE_TEMPLATE_RE = re.compile(r'<template\b[^>]*x-if\s*=\s*"page === \'([^\']+)\'"')
ROUTE_EXPR_RE = re.compile(r'(?:x-(?:show|if|text)|(?:x-bind:|:)[A-Za-z0-9_.:-]+)\s*=\s*"([^"]+)"')
XMODEL_RE = re.compile(r'x-model\s*=\s*"([^"]+)"')
XFOR_RE = re.compile(r'x-for\s*=\s*"([^"]+)"')
STATE_LIKE_IDENTIFIER_RE = re.compile(r'(?<![.\w$])([A-Za-z_][A-Za-z0-9_]*(?:Loading|Error))\b')
SIMPLE_MEMBER_EXPR_RE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\b(?:\s*(?:[.[(]|$))')
HTML_TAG_RE = re.compile(r'<(/?)([A-Za-z0-9:-]+)\b[^>]*?>')
TAG_RE = re.compile(r'<[^>]+>')
VOID_HTML_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def page_leave_hook_re(hook_name: str) -> re.Pattern[str]:
    return re.compile(rf'@page-leave\.window\s*=\s*"{re.escape(hook_name)}\(\)"')


def defined_methods_in(js: str) -> set[str]:
    methods: set[str] = set()
    for match in METHOD_DEF_RE.finditer(js):
        methods.update(group for group in match.groups() if group)
    return methods


def direct_method_calls(expr: str) -> list[str]:
    scrubbed = STRING_LITERAL_RE.sub("", expr)
    return [method for method in METHOD_CALL_RE.findall(scrubbed) if method not in IGNORED_CALLEES]


def undefined_method_calls(expr: str, defined_methods: set[str]) -> list[str]:
    return [method for method in direct_method_calls(expr) if method not in defined_methods]


def defined_members_in(js: str) -> set[str]:
    return defined_methods_in(js) | set(GETTER_DEF_RE.findall(js)) | set(STATE_DEF_RE.findall(js))


def undefined_state_like_identifiers(expr: str, defined_members: set[str]) -> set[str]:
    return {
        identifier
        for identifier in STATE_LIKE_IDENTIFIER_RE.findall(expr)
        if identifier not in defined_members
    }


def simple_member_root(expr: str) -> str | None:
    expr = expr.strip()
    if not expr or expr[0] in "([{" or "." in expr or "[" in expr or "?" in expr:
        return None
    match = SIMPLE_MEMBER_EXPR_RE.match(expr)
    if not match:
        return None
    return match.group(1)


def model_member_root(expr: str) -> str | None:
    match = SIMPLE_MEMBER_EXPR_RE.match(expr.strip())
    if not match:
        return None
    return match.group(1)


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


def html_tag_depth_delta(line: str) -> int:
    depth_delta = 0
    for match in HTML_TAG_RE.finditer(line):
        closing, tag_name = match.groups()
        tag_name = tag_name.lower()
        tag_text = match.group(0)
        if closing:
            depth_delta -= 1
        elif tag_name not in VOID_HTML_TAGS and not tag_text.rstrip().endswith('/>'):
            depth_delta += 1
    return depth_delta


def normalize_button_label(label_html: str) -> str:
    label_text = TAG_RE.sub(" ", label_html)
    return " ".join(label_text.split())


def is_retry_or_refresh_label(label_html: str) -> bool:
    normalized = normalize_button_label(label_html)
    return normalized.startswith("Retry") or normalized.startswith("Refresh")


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
        defined_members = defined_members_in(js)

        for _, attrs, line_number in matching_tags:
            xinit = XINIT_RE.search(attrs)
            if not xinit:
                continue

            for method_name in undefined_method_calls(xinit.group(1), defined_methods):
                errors.append(
                    f"{page_file.relative_to(REPO_ROOT)}:{line_number}: x-init references {method_name}() but {component_name} does not define it"
                )

        route_name = page_file.stem
        route_line_entries = route_lines.get(route_name, [])
        route_root_lines = {line_number for _, _, line_number in matching_tags}
        nested_xdata_depth = 0

        for line_number, line in route_line_entries:
            line_starts_nested_scope = 'x-data' in line and line_number not in route_root_lines
            if line_starts_nested_scope:
                nested_xdata_depth += max(1, html_tag_depth_delta(line))
                continue

            if nested_xdata_depth > 0:
                nested_xdata_depth += html_tag_depth_delta(line)
                continue

            xinit = XINIT_RE.search(line)
            if xinit and line_number not in route_root_lines:
                for method_name in undefined_method_calls(xinit.group(1), defined_methods):
                    errors.append(
                        f"{page_file.relative_to(REPO_ROOT)}:{line_number}: route x-init references {method_name}() but {component_name} does not define it"
                    )

            for event_match in EVENT_ATTR_RE.finditer(line):
                for method_name in undefined_method_calls(event_match.group(1), defined_methods):
                    errors.append(
                        f"{page_file.relative_to(REPO_ROOT)}:{line_number}: route event handler references {method_name}() but {component_name} does not define it"
                    )

            for expr_match in ROUTE_EXPR_RE.finditer(line):
                expr = expr_match.group(1)
                undefined_identifiers = sorted(undefined_state_like_identifiers(expr, defined_members))
                for identifier in undefined_identifiers:
                    errors.append(
                        f"{page_file.relative_to(REPO_ROOT)}:{line_number}: route expression references {identifier} but {component_name} does not define it"
                    )

            for model_match in XMODEL_RE.finditer(line):
                root = model_member_root(model_match.group(1))
                if root and root not in defined_members:
                    errors.append(
                        f"{page_file.relative_to(REPO_ROOT)}:{line_number}: x-model references {root} but {component_name} does not define it"
                    )

            for for_match in XFOR_RE.finditer(line):
                _, _, source_expr = for_match.group(1).partition(" in ")
                root = simple_member_root(source_expr)
                if root and root not in defined_members:
                    errors.append(
                        f"{page_file.relative_to(REPO_ROOT)}:{line_number}: x-for references {root} but {component_name} does not define it"
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
