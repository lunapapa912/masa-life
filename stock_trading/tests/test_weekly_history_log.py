"""logic/weekly/history_log.py のユニットテスト。

2026-09-07週の実データ(誠建設工業・オンコリスバイオ・テラドローン・
エプリー[改めエブリー]・古林紙工)を使い、週次ログが正しく1週分5レコード
記録・読み込みできることを確認する。
"""

from datetime import date
from pathlib import Path

from masa_trade.logic.weekly.engine import score_future_mfe
from masa_trade.logic.weekly.history_log import append_log_entry, build_log_entry, load_log_entries
from masa_trade.logic.weekly.schema import WeeklyCandidate
from tests.test_weekly_scoring import (
    EPLI,
    KOBAYASHI_SHIKO,
    ONCOLYS,
    SEISETSU,
    TERADRONE,
)

WEEK_START = date(2026, 9, 7)


def test_build_log_entry_flattens_all_seven_score_items():
    candidate = WeeklyCandidate(name=SEISETSU.name, rank_history=SEISETSU)
    score = score_future_mfe(candidate)

    entry = build_log_entry(week_start_date=WEEK_START, name=SEISETSU.name, score=score)

    assert entry.score_ranking_progression == 20
    assert entry.score_momentum_acceleration == 15
    assert entry.score_chart_volume == 15  # ストップ高固定proxy
    assert entry.score_catalyst == 10  # 開示なし(中立)
    assert entry.score_theme_market_flow == 5  # 業種不明(中立)
    assert entry.score_overheat_risk == 10
    assert entry.score_historical_fit == 5  # 常に中立
    assert entry.total_score == 80


def test_append_and_load_one_week_of_five_stocks(tmp_path: Path):
    path = tmp_path / "weekly_records" / "score_history.jsonl"

    candidates = [
        WeeklyCandidate(name="誠建設工業", rank_history=SEISETSU),
        WeeklyCandidate(name="オンコリスバイオ", rank_history=ONCOLYS, sector="医薬品", top20_sector_peers=["医薬品", "医薬品"]),
        WeeklyCandidate(name="テラドローン", rank_history=TERADRONE),
        WeeklyCandidate(name="エプリー", rank_history=EPLI, sector="サービス業", top20_sector_peers=["サービス業", "サービス業"]),
        WeeklyCandidate(name="古林紙工", rank_history=KOBAYASHI_SHIKO),
    ]

    for candidate in candidates:
        score = score_future_mfe(candidate)
        entry = build_log_entry(week_start_date=WEEK_START, name=candidate.name, score=score)
        append_log_entry(entry, path)

    loaded = load_log_entries(path)
    assert len(loaded) == 5
    assert [r["name"] for r in loaded] == [c.name for c in candidates]
    assert all(r["week_start_date"] == "2026-09-07" for r in loaded)
    # 全レコードで7項目すべてに値が入っており、合計が算出できている
    # (rank_historyさえあれば①〜⑦全項目が「データなし→中立点」フォールバックを持つため)。
    assert all(r["total_score"] is not None for r in loaded)

    onclys_record = next(r for r in loaded if r["name"] == "オンコリスバイオ")
    assert onclys_record["score_theme_market_flow"] == 4  # 同業種2社→4点

    seisetsu_record = next(r for r in loaded if r["name"] == "誠建設工業")
    assert seisetsu_record["score_chart_volume"] == 15  # ストップ高固定proxy満点


def test_load_log_entries_returns_empty_list_for_missing_file(tmp_path: Path):
    assert load_log_entries(tmp_path / "does_not_exist.jsonl") == []
