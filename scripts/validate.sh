#!/usr/bin/env bash
# Repository validation for intelligent-cockpit-hmi.
# Validates tracked Markdown links, YAML, shell syntax/modes, then pnpm check.

set -euo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_dir"

python_bin=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    python_bin="$candidate"
    break
  fi
done

if [[ -z "$python_bin" ]]; then
  echo "Python is required for Markdown and YAML validation." >&2
  exit 1
fi

echo '--- Markdown local links ---'
"$python_bin" scripts/test_validate_markdown_links.py
"$python_bin" scripts/validate_markdown_links.py

echo '--- YAML syntax ---'
"$python_bin" - <<'PY'
import subprocess
import sys
from pathlib import Path
try:
    import yaml
except ImportError as error:
    raise SystemExit("PyYAML is required for YAML validation.") from error

files = subprocess.check_output(["git", "ls-files", "-z", "--", "*.yml", "*.yaml"], text=False).split(b"\0")
for raw_file in files:
    if raw_file:
        path = Path(raw_file.decode())
        yaml.safe_load(path.read_text(encoding="utf-8"))
print("All tracked YAML files parse correctly.")
PY

echo '--- Shell syntax and committed modes ---'
check_rev='HEAD'
if command -v jj >/dev/null 2>&1; then
  jj_revision="$(jj log -r '@' --no-graph -T 'commit_id' 2>/dev/null || true)"
  if [[ -n "$jj_revision" ]] && git cat-file -e "${jj_revision}^{commit}" 2>/dev/null; then
    check_rev="$jj_revision"
  fi
fi
while IFS= read -r -d '' shell_file; do
  bash -n "$shell_file"
  mode="$(git ls-tree "$check_rev" -- "$shell_file" | awk '{print $1}')"
  if [[ "$mode" != '100755' ]]; then
    echo "Shell script must be committed as executable: $shell_file (found ${mode:-untracked})" >&2
    exit 1
  fi
done < <(git ls-files -z -- '*.sh')
echo 'All tracked Shell scripts have valid syntax and executable modes.'

echo '--- Project check ---'
pnpm check
