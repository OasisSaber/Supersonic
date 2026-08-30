#!/usr/bin/env python3
"""Validate local links in tracked Markdown files without third-party parsers.

Adapted from OasisSaber/AgenticWonderwall (MIT), commit
689d4edb8aacc1fc7a277da89efed05199b75edb. See THIRD_PARTY_NOTICES.md.
"""

import html
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


def strip_ignored_regions(markdown):
    output, fence_char, fence_length = [], None, 0
    for line in markdown.splitlines(keepends=True):
        fence = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence_char:
            if fence and fence.group(1)[0] == fence_char and len(fence.group(1)) >= fence_length:
                fence_char, fence_length = None, 0
            output.append("\n" if line.endswith("\n") else "")
            continue
        if fence:
            fence_char, fence_length = fence.group(1)[0], len(fence.group(1))
            output.append("\n" if line.endswith("\n") else "")
            continue
        if line.startswith(("    ", "\t")):
            output.append("\n" if line.endswith("\n") else "")
            continue
        result, index = [], 0
        while index < len(line):
            if line[index] != "`":
                result.append(line[index])
                index += 1
                continue
            end = index
            while end < len(line) and line[end] == "`":
                end += 1
            marker, close = line[index:end], line.find(line[index:end], end)
            if close == -1:
                result.append(marker)
                index = end
            else:
                result.append(" " * (close + len(marker) - index))
                index = close + len(marker)
        output.append("".join(result))
    return re.sub(r"<!--.*?-->", "", "".join(output), flags=re.DOTALL)


def normalize_label(value):
    return " ".join(value.strip().lower().split())


def closing(text, start, opening, close):
    depth, index = 1, start
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == opening:
            depth += 1
        elif text[index] == close:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def destination(content):
    content = content.strip()
    if not content:
        return ""
    if content.startswith("<"):
        end = content.find(">", 1)
        return content[1:end] if end != -1 else None
    depth, escaped, result = 0, False, []
    for character in content:
        if escaped:
            result.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
            result.append(character)
        elif character == "(":
            depth += 1
            result.append(character)
        elif character == ")" and depth:
            depth -= 1
            result.append(character)
        elif character.isspace() and not depth:
            break
        else:
            result.append(character)
    return "".join(result)


def markdown_targets(text):
    definitions = {
        normalize_label(match.group(1)): match.group(2) or match.group(3)
        for match in re.finditer(r"(?m)^ {0,3}\[([^\]]+)\]:\s*(?:<([^>]+)>|(\S+))", text)
    }
    targets, explicit, shortcut, index = [], [], [], 0
    while index < len(text):
        image = text.startswith("![", index)
        if text[index] != "[" and not image:
            index += 1
            continue
        bracket = index + 1 if image else index
        if index and text[index - 1] == "\\":
            index += 1
            continue
        label_end = closing(text, bracket + 1, "[", "]")
        if label_end is None:
            index += 1
            continue
        label, next_index = text[bracket + 1:label_end], label_end + 1
        if next_index < len(text) and text[next_index] == "(":
            target_end = closing(text, next_index + 1, "(", ")")
            if target_end is not None:
                target = destination(text[next_index + 1:target_end])
                if target is not None:
                    targets.append(target)
                index = target_end + 1
                continue
        if next_index < len(text) and text[next_index] == "[":
            reference_end = closing(text, next_index + 1, "[", "]")
            if reference_end is not None:
                explicit.append(normalize_label(text[next_index + 1:reference_end] or label))
                index = reference_end + 1
                continue
        shortcut.append(normalize_label(label))
        index = label_end + 1
    for reference in explicit:
        targets.append(definitions.get(reference, f"__MISSING_REFERENCE__:{reference}"))
    for reference in shortcut:
        if reference in definitions:
            targets.append(definitions[reference])
    targets.extend(match.group(3) for match in re.finditer(r"\b(href|src)\s*=\s*([\"'])(.*?)\2", text, re.I))
    return targets


def validate_paths(root, markdown_files):
    root, broken = Path(root).resolve(), []
    for source in markdown_files:
        source = Path(source)
        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            broken.append((source, "", "not valid UTF-8"))
            continue
        for raw_target in markdown_targets(strip_ignored_regions(text)):
            if raw_target.startswith("__MISSING_REFERENCE__:"):
                broken.append((source, raw_target.split(":", 1)[1], "missing reference definition"))
                continue
            target = html.unescape(raw_target.strip())
            if not target or target.startswith(("#", "//")) or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                continue
            path = unquote(urlsplit(target.replace("\\ ", " ")).path)
            if not path:
                continue
            candidate = root / path.lstrip("/") if path.startswith("/") else source.parent / path
            try:
                candidate.resolve().relative_to(root)
            except ValueError:
                broken.append((source, raw_target, "target escapes repository"))
            else:
                if not candidate.exists():
                    broken.append((source, raw_target, "target not found"))
    return broken


def tracked_markdown(root):
    files = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z", "--", "*.md"])
    return [Path(root) / value.decode() for value in files.split(b"\0") if value]


def main():
    root = Path(sys.argv[1] if len(sys.argv) == 2 else ".").resolve()
    broken = validate_paths(root, tracked_markdown(root))
    if broken:
        for source, target, reason in broken:
            print(f"BROKEN LINK: {source.relative_to(root)} -> {target} ({reason})", file=sys.stderr)
        return 1
    print("All tracked Markdown local links resolve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
