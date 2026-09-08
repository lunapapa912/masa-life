from datetime import date

from masa_trade.logic.weekly.loader import (
    build_rank_histories,
    load_market_regime_input,
    load_ranking_snapshot,
)
from masa_trade.logic.weekly.schema import Checkpoint


def test_load_ranking_snapshot_basic():
    data = {
        "checkpoint": "midday_close",
        "captured_at": "2026-09-08T11:30:00+09:00",
        "entries": [
            {"rank": 1, "name": "テストA", "symbol": "1111.T", "price": 1000.0, "pct_change": 8.5},
            {"rank": 2, "name": "テストB", "price": 500.0, "pct_change": 3.2},
        ],
    }
    snapshot = load_ranking_snapshot(data)
    assert snapshot.checkpoint == Checkpoint.MIDDAY_CLOSE
    assert len(snapshot.entries) == 2
    assert snapshot.entries[0].symbol == "1111.T"
    assert snapshot.entries[1].symbol is None


def test_build_rank_histories_across_days_and_checkpoints():
    monday_open = load_ranking_snapshot(
        {
            "checkpoint": "open",
            "captured_at": "2026-09-07T09:00:00+09:00",
            "entries": [{"rank": 5, "name": "テストA"}],
        }
    )
    monday_midday = load_ranking_snapshot(
        {
            "checkpoint": "midday_close",
            "captured_at": "2026-09-07T11:30:00+09:00",
            "entries": [{"rank": 2, "name": "テストA"}],
        }
    )
    tuesday_open = load_ranking_snapshot(
        {
            "checkpoint": "open",
            "captured_at": "2026-09-08T09:00:00+09:00",
            "entries": [{"rank": 1, "name": "テストA"}],
        }
    )
    histories = build_rank_histories([monday_open, monday_midday, tuesday_open])
    assert histories["テストA"].rank_sequence == [
        (date(2026, 9, 7), Checkpoint.OPEN, 5),
        (date(2026, 9, 7), Checkpoint.MIDDAY_CLOSE, 2),
        (date(2026, 9, 8), Checkpoint.OPEN, 1),
    ]


def test_load_market_regime_input():
    regime_input = load_market_regime_input({"nikkei_change_pct": -1.2, "topix_change_pct": -0.8})
    assert regime_input.nikkei_change_pct == -1.2
    assert regime_input.prime_decliner_pct is None
