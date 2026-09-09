#!/usr/bin/env bash
# 日次実行用スクリプト。cron やサーバー上のタスクスケジューラから呼び出す想定。
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python -m masa_trade.main
