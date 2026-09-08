"""週間ランキング画像から読み取ったデータ(JSON/dict)をスキーマへ変換するローダー。

Checkpointなどのenumは内部的に日本語ラベルを値に持たせているため、
外部入力(ユーザーがチャットに貼るJSON)にそれをそのまま要求すると
入力ミスが起きやすい。ここで短い英字キーとの対応を吸収する。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from masa_trade.logic.weekly.schema import (
    Checkpoint,
    MarketRegimeInput,
    RankEntry,
    RankHistory,
    RankingSnapshot,
)

# JSON側で使う短いcheckpointキー ⇔ Checkpoint enum の対応。
# 曜日は含めない(時間帯のみ)。どの日かはcaptured_atの日付側で表す。
CHECKPOINT_ALIASES: dict[str, Checkpoint] = {
    "open": Checkpoint.OPEN,
    "mid_morning": Checkpoint.MID_MORNING,
    "midday_close": Checkpoint.MIDDAY_CLOSE,
    "afternoon_1400": Checkpoint.AFTERNOON,
    "close": Checkpoint.CLOSE,
}


def parse_checkpoint(value: str) -> Checkpoint:
    try:
        return CHECKPOINT_ALIASES[value]
    except KeyError as exc:
        valid = ", ".join(CHECKPOINT_ALIASES)
        raise ValueError(f"未知のcheckpointです: {value!r}(有効な値: {valid})") from exc


def load_rank_entry(data: dict[str, Any], checkpoint: Checkpoint, captured_at: datetime | None) -> RankEntry:
    return RankEntry(
        name=data["name"],
        rank=int(data["rank"]),
        symbol=data.get("symbol"),
        price=data.get("price"),
        pct_change=data.get("pct_change"),
        volume=data.get("volume"),
        checkpoint=checkpoint,
        captured_at=captured_at,
    )


def load_ranking_snapshot(data: dict[str, Any]) -> RankingSnapshot:
    """{"checkpoint": "...", "captured_at": "...", "entries": [...]} 形式のdictから組み立てる。"""
    checkpoint = parse_checkpoint(data["checkpoint"])
    captured_at_raw = data.get("captured_at")
    captured_at = datetime.fromisoformat(captured_at_raw) if captured_at_raw else datetime.now().astimezone()
    entries = [load_rank_entry(e, checkpoint, captured_at) for e in data["entries"]]
    return RankingSnapshot(checkpoint=checkpoint, captured_at=captured_at, entries=entries)


def build_rank_histories(snapshots: list[RankingSnapshot]) -> dict[str, RankHistory]:
    """複数時点のRankingSnapshotを、銘柄名をキーにしたRankHistoryへまとめる(RANK VELOCITY用)。

    同じcheckpoint(例: "前引け")でも日付が違えば別の時点として記録する。
    """
    histories: dict[str, RankHistory] = {}
    for snapshot in snapshots:
        moment_date = snapshot.captured_at.date()
        for entry in snapshot.entries:
            history = histories.get(entry.name)
            if history is None:
                history = RankHistory(name=entry.name, symbol=entry.symbol)
                histories[entry.name] = history
            history.entries_by_moment[(moment_date, snapshot.checkpoint)] = entry
    return histories


def load_market_regime_input(data: dict[str, Any]) -> MarketRegimeInput:
    return MarketRegimeInput(
        nikkei_change_pct=data.get("nikkei_change_pct"),
        topix_change_pct=data.get("topix_change_pct"),
        prime_decliner_pct=data.get("prime_decliner_pct"),
        growth_decliner_pct=data.get("growth_decliner_pct"),
    )
