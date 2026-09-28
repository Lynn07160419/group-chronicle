#!/bin/zsh
cd "${0:A:h}"
PYTHON="/Users/lynn/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
if [[ ! -x "$PYTHON" ]]; then PYTHON="$(command -v python3)"; fi
if [[ -z "$PYTHON" ]]; then
  echo "未找到 Python 3，请先安装 Python 3。"
  read -k 1
  exit 1
fi
if curl -fsS http://127.0.0.1:8765/api/records >/dev/null 2>&1; then
  open "http://127.0.0.1:8765/"
  exit 0
fi
echo "网页正在启动。使用期间请保留这个窗口，按 Control+C 可停止。"
(sleep 1; open "http://127.0.0.1:8765/") &
"$PYTHON" server.py
