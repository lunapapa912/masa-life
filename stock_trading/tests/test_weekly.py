from datetime import date
from pathlib import Path

from masa_trade.logic.common.order import MarketRegime
from masa_trade.logic.weekly.engine import (
    applies_continuation_override,
    build_mfe_mae,
    classify_market_regime,
    compute_capture_rate,
    is_peak_out_warning,
)
from masa_trade.logic.weekly.schema import (
    FUTURE_MFE_SCORE_ITEM_DEFINITIONS,
    ContinuationOverrideFlag,
    MarketRegimeInput,
    PeakOutAssessment,
    PeakOutFlag,
    StockType,
    WeeklyRecord,
    empty_future_mfe_score,
)
from masa_trade.logic.weekly.store import load_weekly_records, save_weekly_record


def test_future_mfe_score_items_sum_to_100():
    assert sum(points for _, points in FUTURE_MFE_SCORE_ITEM_DEFINITIONS) == 100
    assert sum(item.max_points for item in empty_future_mfe_score().items) == 100


def test_market_regime_defense_needs_two_conditions():
    both = MarketRegimeInput(nikkei_change_pct=-2.5, topix_change_pct=-2.1)
    assert classify_market_regime(both) == MarketRegime.DEFENSE

    only_one = MarketRegimeInput(nikkei_change_pct=-2.5)
    assert classify_market_regime(only_one) == MarketRegime.CAUTION

    none_met = MarketRegimeInput(nikkei_change_pct=-0.5, topix_change_pct=-0.3)
    assert classify_market_regime(none_met) == MarketRegime.NORMAL


def test_continuation_override_needs_three_flags():
    two_flags = [
        ContinuationOverrideFlag.RANK_MAINTAINED_OR_UP,
        ContinuationOverrideFlag.NEW_HIGH,
    ]
    assert not applies_continuation_override(two_flags)

    three_flags = [*two_flags, ContinuationOverrideFlag.VOLUME_EXPANDING]
    assert applies_continuation_override(three_flags)


def test_peak_out_warning_needs_two_flags():
    one_flag = PeakOutAssessment(flags=[PeakOutFlag.LONG_UPPER_WICK])
    assert not is_peak_out_warning(one_flag)

    two_flags = PeakOutAssessment(flags=[PeakOutFlag.LONG_UPPER_WICK, PeakOutFlag.VWAP_BREAK])
    assert is_peak_out_warning(two_flags)


def test_mfe_mae_percentages():
    result = build_mfe_mae(baseline_price=1000, highest_price_within_5d=1200, lowest_price_within_5d=900)
    assert round(result.mfe_pct, 4) == 20.0
    assert round(result.mae_pct, 4) == -10.0


def test_capture_rate():
    assert compute_capture_rate(realized_return_pct=14, mfe_pct=20) == 70.0
    assert compute_capture_rate(realized_return_pct=5, mfe_pct=0) is None
    assert compute_capture_rate(realized_return_pct=5, mfe_pct=-3) is None


def test_weekly_record_store_roundtrip(tmp_path: Path):
    record = WeeklyRecord(
        week_start_date=date(2026, 9, 7),
        role="MODEL WINNER",
        name="テスト銘柄",
        symbol="0000.T",
        stock_type=StockType.A_CONTINUATION,
    )
    path = tmp_path / "weekly_records" / "2026-09-07.jsonl"
    save_weekly_record(record, path)

    loaded = load_weekly_records(path)
    assert len(loaded) == 1
    assert loaded[0]["name"] == "テスト銘柄"
    assert loaded[0]["stock_type"] == "A:CONTINUATION"
    assert loaded[0]["week_start_date"] == "2026-09-07"
