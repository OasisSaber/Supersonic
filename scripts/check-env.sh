#!/usr/bin/env sh
set -eu
for tool in node pnpm uv git ffmpeg nvidia-smi; do
  if command -v "$tool" >/dev/null 2>&1; then echo "[OK] $tool -> $(command -v "$tool")"
  else echo "[--] $tool 未安装或未加入 PATH"; fi
done
uname -a

