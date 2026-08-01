#!/usr/bin/env python3
"""Validate the repository pull request template without third-party parsers.

Adapted from OasisSaber/AgenticWonderwall (MIT), commits
689d4edb8aacc1fc7a277da89efed05199b75edb and
794b083e816e84f271e991aed84a5a5f4e9c74fc. See THIRD_PARTY_NOTICES.md.
"""

import os
import re
import sys
from pathlib import Path

PLACEHOLDERS = ("<number>", "<source>", "<goal>", "<scope>")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
ISSUE = re.compile(
    r"(?:close(?:s|d)?|fix(?:es|ed)?|resolve(?:s|d)?)\s+#\d+",
    re.IGNORECASE,
)
HEADERS = (
    "What changed / Result",
    "Why",
    "Screens / evidence",
    "Verification",
    "Scope and risks",
    "Agent self-review",
)
REQUIRED_REVIEW_ITEMS = (
    "满足 Issue 或明确人类授权",
    "没有扩大任务范围",
    "已阅读完整 diff",
    "必要验证已通过",
    "没有遗留调试代码、临时文件、缓存或失效引用",
    "已记录未验证项和已知限制",
)


def section(body, heading):
    match = re.search(rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", body)
    return match.group(1).strip() if match else None


def validate(body):
    errors = []
    visible_body = HTML_COMMENT.sub("", body)
    related = section(visible_body, "Related task")
    if related is None:
        errors.append("Related task must not be empty.")
        related = ""
    issue_lines = re.findall(r"(?m)^- Issue:[ \t]*(.*)$", related)
    authorization_parents = re.findall(r"(?m)^- Explicit human authorization:[ \t]*$", related)
    fields = {
        label: re.findall(rf"(?m)^  - {label}:[ \t]*(.*)$", related)
        for label in ("Authorization source", "Goal", "Scope")
    }
    issue_path_present = bool(issue_lines)
    authorization_path_present = bool(authorization_parents) or any(fields.values())

    if issue_path_present == authorization_path_present:
        errors.append("Fill exactly one of Issue or explicit human authorization.")
    if len(issue_lines) > 1:
        errors.append("Issue path must appear exactly once.")
    if issue_path_present:
        issue_value = issue_lines[0].strip()
        if not issue_value:
            errors.append("Issue path must not be empty.")
        elif any(placeholder in issue_value for placeholder in PLACEHOLDERS):
            errors.append("Remove template placeholder text from the Issue field.")
        elif not ISSUE.fullmatch(issue_value):
            errors.append("Issue must be exactly one closing reference such as Closes #123.")
    if len(authorization_parents) > 1:
        errors.append("Explicit human authorization path must appear exactly once.")
    if authorization_path_present:
        if len(authorization_parents) != 1:
            errors.append("Explicit human authorization fields require one parent line.")
        for label, matches in fields.items():
            if len(matches) != 1:
                errors.append(f"Explicit human authorization requires exactly one {label}.")
            elif not matches[0].strip():
                errors.append(f"Explicit human authorization requires {label}.")
            elif any(placeholder in matches[0] for placeholder in PLACEHOLDERS):
                errors.append(f"Remove template placeholder text from {label}.")
    global_task_lines = re.findall(
        r"(?m)^\s*- (?:Issue:|Explicit human authorization:|Authorization source:|Goal:|Scope:)", visible_body
    )
    related_task_lines = re.findall(
        r"(?m)^\s*- (?:Issue:|Explicit human authorization:|Authorization source:|Goal:|Scope:)", related
    )
    if len(global_task_lines) != len(related_task_lines):
        errors.append("Task-source structure must appear only under Related task at the required level.")

    for heading in HEADERS[:-1]:
        if not section(visible_body, heading):
            errors.append(f"{heading} must not be empty.")
    review = section(visible_body, "Agent self-review") or ""
    for item in REQUIRED_REVIEW_ITEMS:
        checked = re.search(rf"(?m)^- \[[xX]\] {re.escape(item)}$", review)
        present = re.search(rf"(?m)^- \[[ xX]\] {re.escape(item)}$", review)
        if not checked:
            errors.append(
                f"Agent self-review item must be checked: {item}."
                if present else f"Agent self-review item is missing: {item}."
            )
    return errors


def main():
    body = Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) == 2 else os.environ.get("PR_BODY", sys.stdin.read())
    errors = validate(body)
    if errors:
        print("Pull Request body validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Pull Request body is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
