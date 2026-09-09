from pathlib import Path

from masa_trade.config import Settings
from masa_trade.logic.masa import judge, run_gates
from masa_trade.logic.schema import (
    AccountingData,
    DilutionData,
    GateStatus,
    JudgeInput,
    ReviewMode,
    TradeDecision,
    empty_corporate_value_score,
    empty_entry_score,
    empty_feasibility_score,
)


def _settings() -> Settings:
    return Settings(raw={"cio_review": {}}, watchlist=[], config_dir=Path("."))


def test_score_definitions_sum_to_100():
    assert sum(item.max_points for item in empty_corporate_value_score().items) == 100
    assert sum(item.max_points for item in empty_entry_score().items) == 100
    assert sum(item.max_points for item in empty_feasibility_score().items) == 100


def test_gates_are_unknown_when_no_data_provided():
    data = JudgeInput(symbol="0000.T", name="テスト銘柄", mode=ReviewMode.DEEP_DIVE)
    gates = run_gates(data, _settings())
    assert len(gates) == 6
    assert all(g.status == GateStatus.UNKNOWN for g in gates)


def test_judge_waits_when_gates_are_unknown():
    data = JudgeInput(symbol="0000.T", name="テスト銘柄", mode=ReviewMode.DEEP_DIVE)
    memo = judge(data, _settings())
    assert memo.trade_decision == TradeDecision.WAIT
    assert memo.total_score is None
    assert len(memo.missing_info) > 0


def test_judge_avoids_on_critical_accounting_fail():
    data = JudgeInput(
        symbol="0000.T",
        name="テスト銘柄",
        mode=ReviewMode.DEEP_DIVE,
        accounting=AccountingData(going_concern_doubt=True),
    )
    memo = judge(data, _settings())
    assert memo.trade_decision == TradeDecision.AVOID


def test_judge_avoids_on_excessive_dilution():
    data = JudgeInput(
        symbol="0000.T",
        name="テスト銘柄",
        mode=ReviewMode.DEEP_DIVE,
        dilution=DilutionData(dilution_ratio_estimate_pct=50.0),
    )
    memo = judge(data, _settings())
    assert memo.trade_decision == TradeDecision.AVOID
