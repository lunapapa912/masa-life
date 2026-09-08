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
CHECKPOINT_ALIASES: dict[str, Checkpoint] = {
    "monday_open": Checkpoint.MONDAY_OPEN,
    "monday_1030": Checkpoint.MONDAY_1030,
    "monday_midday_close": Checkpoint.MONDAY_MIDDAY_CLOSE,
    "afternoon_1400": Checkpoint.AFTERNOON_1400,
    "close": Checkpoint.CLOSE,
    "tue_to_fri": Checkpoint.TUE_TO_FRI_DAILY,
    "friday_audit": Checkpoint.FRIDAY_AUDIT,
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
    """複数時点のRankingSnapshotを、銘柄名をキーにしたRankHistoryへまとめる(RANK VELOCITY用)。"""
    histories: dict[str, RankHistory] = {}
    for snapshot in snapshots:
        for entry in snapshot.entries:
            history = histories.get(entry.name)
            if history is None:
                history = RankHistory(name=entry.name, symbol=entry.symbol)
                histories[entry.name] = history
            history.entries_by_checkpoint[snapshot.checkpoint] = entry
    return histories


def load_market_regime_input(data: dict[str, Any]) -> MarketRegimeInput:
    return MarketRegimeInput(
        nikkei_change_pct=data.get("nikkei_change_pct"),
        topix_change_pct=data.get("topix_change_pct"),
        prime_decliner_pct=data.get("prime_decliner_pct"),
        growth_decliner_pct=data.get("growth_decliner_pct"),
    )
