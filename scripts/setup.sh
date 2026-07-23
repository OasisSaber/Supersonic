#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
export UV_CACHE_DIR="$ROOT/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$ROOT/.uv-python"
command -v uv >/dev/null 2>&1 || { echo "未找到 uv"; exit 1; }
command -v pnpm >/dev/null 2>&1 || { echo "未找到 pnpm"; exit 1; }
uv sync --project apps/backend --python 3.11
pnpm install --store-dir .pnpm-store
echo "环境准备完成。运行 pnpm dev 启动前后端。"
