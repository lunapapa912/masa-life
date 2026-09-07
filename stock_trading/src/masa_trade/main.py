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
from masa_trade.logic.masa import build_chart_data, judge
from masa_trade.logic.schema import CIODecisionMemo, JudgeInput, ReviewMode
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


def build_judge_input(item_symbol: str, item_name: str, settings: Settings) -> JudgeInput:
    """v2.19のFINAL RANKINGで選ばれた1銘柄について、v1.3の精査に必要な入力を組み立てる。

    現状、自動取得できているのは株価データ(チャート)のみ。
    材料・会計・希薄化・業績接続・織込み度・カタリストの各データは
    まだ取得元が未実装のため空のまま渡し、対応するゲートは UNKNOWN になる。
    TODO: 適時開示・決算・需給データの取得元を実装し、ここで埋める。
    """
    ohlcv = fetch_ohlcv(item_symbol, settings)
    chart = build_chart_data(ohlcv, settings)
    default_mode = ReviewMode(settings.raw.get("cio_review", {}).get("default_mode", "C"))
    return JudgeInput(
        symbol=item_symbol,
        name=item_name,
        mode=default_mode,
        current_price=float(ohlcv["Close"].iloc[-1]),
        research_timestamp=settings.now(),
        chart=chart,
    )


def run(config_dir: str | Path | None = None) -> list[CIODecisionMemo]:
    settings = load_settings(config_dir)
    setup_logging(settings)

    results: list[CIODecisionMemo] = []
    for item in settings.watchlist:
        try:
            judge_input = build_judge_input(item.symbol, item.name, settings)
            results.append(judge(judge_input, settings))
        except Exception:
            logger.exception("判定に失敗しました: %s (%s)", item.name, item.symbol)

    notify(results, settings)
    return results


def main() -> None:
    run()


if __name__ == "__main__":
    main()
