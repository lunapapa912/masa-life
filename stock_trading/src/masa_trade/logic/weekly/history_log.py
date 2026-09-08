"""週次スコアリング結果の振り返り用ログ。

logic/weekly/store.py の WeeklyRecord(score: FutureMfeScore、items がネストした
リスト)とは別に、①〜⑦の各得点を独立フィールドとして持つ軽量な記録
(HistoricalScoreLogEntry)を追記していく。将来 score_historical_fit() が
「今週のスコアパターンが過去の勝ちパターンにどれだけ近いか」を計算する際に、
このフラットな構造の方が類似度計算をしやすいため分けている。

【LOOK-AHEAD BIAS禁止(v2.1 §26)について】
    このログは振り返り専用であり、当該週の score_future_mfe() 等の判断ロジックは
    このログを一切参照しない設計にしている。将来 score_historical_fit() を
    実データに基づくロジックへ置き換える際も、「当該週より前に書き込まれた」
    レコードだけを参照すること(当該週に書き込んだ自分自身のレコードを
    その週の判断に混ぜてはならない)。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from masa_trade.logic.weekly.schema import FutureMfeScore, HistoricalScoreLogEntry

# FutureMfeScoreItem.name(v1.3原文どおりの日本語表記) ⇔
# HistoricalScoreLogEntryのフィールド名、の対応。
_SCORE_FIELD_BY_ITEM_NAME: dict[str, str] = {
    "ランキング推移": "score_ranking_progression",
    "上昇率加速度": "score_momentum_acceleration",
    "チャート/出来高": "score_chart_volume",
    "CATALYST": "score_catalyst",
    "テーマ/市場資金": "score_theme_market_flow",
    "過熱/下落リスク": "score_overheat_risk",
    "過去統計適合度": "score_historical_fit",
}


def build_log_entry(
    week_start_date: date,
    name: str,
    score: FutureMfeScore,
    symbol: str | None = None,
    final_rank: int | None = None,
    final_pct_change: float | None = None,
    was_model_winner: bool = False,
    was_executable_winner: bool = False,
    notes: list[str] | None = None,
) -> HistoricalScoreLogEntry:
    """FutureMfeScore(ネスト構造)をHistoricalScoreLogEntry(フラット構造)に変換する。"""
    item_points = {item.name: item.points for item in score.items}
    score_fields: dict[str, float | None] = {
        field_name: item_points.get(item_name) for item_name, field_name in _SCORE_FIELD_BY_ITEM_NAME.items()
    }

    return HistoricalScoreLogEntry(
        week_start_date=week_start_date,
        name=name,
        symbol=symbol,
        total_score=score.total,
        final_rank=final_rank,
        final_pct_change=final_pct_change,
        was_model_winner=was_model_winner,
        was_executable_winner=was_executable_winner,
        notes=notes or [],
        **score_fields,
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"JSON化できない型です: {type(value)!r}")


def append_log_entry(entry: HistoricalScoreLogEntry, path: Path) -> None:
    """1レコードをJSONLファイルに追記する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(entry), ensure_ascii=False, default=_json_default)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_log_entries(path: Path) -> list[dict[str, Any]]:
    """保存済みのログを辞書のリストとして読み込む(振り返り・将来の類似度計算用)。

    現状はdataclassへの復元は行わず、生の辞書を返す(logic/weekly/store.pyの
    load_weekly_records()と同じ方針)。
    """
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                entries.append(json.loads(stripped))
    return entries
