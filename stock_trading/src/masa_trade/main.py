"""日次実行のエントリーポイント。

    python -m masa_trade.main
    または
    masa-trade  (pip install -e . 後にコマンドとして実行)
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from masa_trade.config import Settings, load_settings
from masa_trade.data.fetcher import fetch_ohlcv
from masa_trade.logic.masa import JudgeResult, judge
from masa_trade.notify.notifier import notify

logger = logging.getLogger(__name__)


def setup_logging(settings: Settings) -> None:
    log_conf = settings.logging
    log_dir = settings.resolve_path(log_conf["dir"])
    log_dir.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        log_dir / log_conf["filename"],
        maxBytes=log_conf["max_bytes"],
        backupCount=log_conf["backup_count"],
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(log_conf["level"])
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler())


def run(config_dir: str | Path | None = None) -> list[JudgeResult]:
    settings = load_settings(config_dir)
    setup_logging(settings)

    results: list[JudgeResult] = []
    for item in settings.watchlist:
        try:
            ohlcv = fetch_ohlcv(item.symbol, settings)
            result = judge(item.symbol, ohlcv, settings)
            results.append(result)
        except Exception:
            logger.exception("判定に失敗しました: %s (%s)", item.name, item.symbol)

    notify(results, settings)
    return results


def main() -> None:
    run()


if __name__ == "__main__":
    main()
