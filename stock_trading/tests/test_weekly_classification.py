"""classify_stock_type() / continuation_override() / trap_control() / select_winners()
のユニットテスト(【3.3タイプ分類】【4.CONTINUATION OVERRIDE】
【5.CONTINUATION TRAP CONTROL】【11.MODEL/EXECUTABLE WINNER】)。

2026-09-07(月)/09-08(火)の実データ(誠建設工業・オンコリスバイオ・
テラドローン・エプリー[改めエブリー]・古林紙工)を使い、継続成功パターンと
急落パターンをcontinuation_override()/trap_control()が分離できるかを確認する。
タイプB/CはFUTURE MFE SCOREを狙って満たす合成データが対象5銘柄の実データに
存在しないため、合成データで単体テストする。
"""

from datetime import UTC, date, datetime

from masa_trade.logic.weekly.engine import (
    classify_stock_type,
    continuation_override,
    is_suspected_trap,
    select_winners,
    trap_control,
)
from masa_trade.logic.weekly.schema import (
    Checkpoint,
    ContinuationOverrideFlag,
    ContinuationTrapFlag,
    DisclosureRecord,
    RankHistory,
    StockType,
    WeeklyCandidate,
)
from tests.test_weekly_scoring import (
    EPLI,
    KOBAYASHI_SHIKO,
    ONCOLYS,
    SEISETSU,
    TERADRONE,
    TERADRONE_WARRANT_DISCLOSURE,
    _history,
)

MON = date(2026, 9, 7)
TUE = date(2026, 9, 8)


def _candidate(name: str, rank_history: RankHistory, **kwargs) -> WeeklyCandidate:
    return WeeklyCandidate(name=name, rank_history=rank_history, **kwargs)


SEISETSU_CANDIDATE = _candidate("誠建設工業", SEISETSU)
ONCOLYS_CANDIDATE = _candidate("オンコリスバイオ", ONCOLYS, sector="医薬品", top20_sector_peers=["医薬品", "医薬品"])
TERADRONE_CANDIDATE = _candidate("テラドローン", TERADRONE, disclosures=[TERADRONE_WARRANT_DISCLOSURE])
EPLI_CANDIDATE = _candidate("エプリー", EPLI, sector="サービス業", top20_sector_peers=["サービス業", "サービス業"])
KOBAYASHI_CANDIDATE = _candidate("古林紙工", KOBAYASHI_SHIKO)


# ---------------------------------------------------------------------------
# classify_stock_type()
# ---------------------------------------------------------------------------


def test_continuation_winners_classify_as_type_a():
    # 誠建設工業・オンコリスバイオは直近も上位を維持し、上昇率も加速方向のまま
    # → タイプA(CONTINUATION)。
    assert classify_stock_type(SEISETSU_CANDIDATE) == StockType.A_CONTINUATION
    assert classify_stock_type(ONCOLYS_CANDIDATE) == StockType.A_CONTINUATION


def test_reversal_and_stagnant_stocks_do_not_fit_any_type():
    # テラドローン・エプリーは前引け後に崩落し順位も上昇率も低評価、
    # 古林紙工は上昇率凍結だが順位が低すぎるため、いずれもA/B/Cの
    # どの型にも綺麗には当てはまらない(正直な結果として記録する)。
    assert classify_stock_type(TERADRONE_CANDIDATE) is None
    assert classify_stock_type(EPLI_CANDIDATE) is None
    assert classify_stock_type(KOBAYASHI_CANDIDATE) is None


def test_classify_type_b_main_early_with_synthetic_data():
    # 対象5銘柄の実データにタイプB(6〜20位・緩やかな上昇・過熱なし)に
    # 綺麗に一致する例がないため、合成データで単体テストする。
    history = _history(
        "B_TEST",
        [
            (MON, Checkpoint.OPEN, 15, None),
            (MON, Checkpoint.MID_MORNING, 15, 2.0),
            (MON, Checkpoint.MIDDAY_CLOSE, 14, 2.5),
            (TUE, Checkpoint.OPEN, 13, 3.0),
            (TUE, Checkpoint.MIDDAY_CLOSE, 12, 3.5),
        ],
    )
    candidate = WeeklyCandidate(name="B_TEST", rank_history=history)
    assert classify_stock_type(candidate) == StockType.B_MAIN_EARLY


def test_classify_type_c_catalyst_early_with_synthetic_data():
    # 同様に、タイプC(20位以下・値動き弱いが好材料あり)も合成データで確認する。
    history = _history(
        "C_TEST",
        [
            (MON, Checkpoint.OPEN, 38, None),
            (MON, Checkpoint.MID_MORNING, 36, 1.0),
            (MON, Checkpoint.MIDDAY_CLOSE, 35, 1.0),
        ],
    )
    disclosure = DisclosureRecord(
        company_name="C_TEST",
        title="業務提携に関するお知らせ",
        pubdate=datetime(2026, 9, 7, 10, 0, tzinfo=UTC),
    )
    candidate = WeeklyCandidate(name="C_TEST", rank_history=history, disclosures=[disclosure])
    assert classify_stock_type(candidate) == StockType.C_CATALYST_EARLY


def test_classify_stock_type_without_rank_history_is_none():
    candidate = WeeklyCandidate(name="データなし銘柄")
    assert classify_stock_type(candidate) is None


# ---------------------------------------------------------------------------
# continuation_override() / trap_control()
#
# 実データでの検証結果(これまでの分析と整合するかを確認する狙い):
#   誠建設工業(1位維持・ストップ高疑い): override該当、trap非該当。
#   テラドローン(一度上位→崩落): trap該当(ランキング順位低下+材料出尽くし)。
# ---------------------------------------------------------------------------


def test_seisetsu_override_applies_and_trap_does_not():
    applies, flags = continuation_override(SEISETSU_CANDIDATE)
    assert applies is True
    assert len(set(flags)) >= 3

    suspected, trap_flags = trap_control(SEISETSU_CANDIDATE)
    assert suspected is False
    # 開示がない(材料出尽くし相当)ことだけは検出されるが、単独では非該当。
    assert trap_flags == [ContinuationTrapFlag.MATERIAL_EXHAUSTED]


def test_teradrone_trap_control_detects_suspected_trap():
    suspected, flags = trap_control(TERADRONE_CANDIDATE)
    assert suspected is True
    assert ContinuationTrapFlag.RANK_DECLINE in flags
    assert ContinuationTrapFlag.MATERIAL_EXHAUSTED in flags

    # テラドローンは崩落後の最終状態では順位・上昇率とも低評価になっており、
    # continuation_override自体がそもそも成立していない(overrideするものがない)。
    applies, _ = continuation_override(TERADRONE_CANDIDATE)
    assert applies is False


def test_epli_trap_control_detects_suspected_trap_too():
    # エプリーもテラドローンと同様のパターン(前引け後の崩落)で、
    # trap_controlが複数該当を検出する。
    suspected, flags = trap_control(EPLI_CANDIDATE)
    assert suspected is True
    assert len(set(flags)) >= 2


def test_kobayashi_shiko_override_applies_despite_low_rank():
    # 正直な報告: 古林紙工(順位24〜30位台の低迷銘柄)も、上昇率が完全凍結して
    # いるため「押しても崩れない」「高値更新」等のフラグが偶然成立し、
    # continuation_overrideが該当してしまう。これは近似ロジックの限界であり、
    # 「順位が低い凍結銘柄」と「順位が高い凍結銘柄(誠建設工業)」を
    # continuation_override単体では区別できないことを示す
    # (①ランキング推移スコア側で低評価される設計だが、override自体は
    # 順位の絶対水準を①の点数以外では直接見ていないため)。
    applies, _ = continuation_override(KOBAYASHI_CANDIDATE)
    assert applies is True


def test_is_suspected_trap_threshold():
    one_flag = [ContinuationTrapFlag.RANK_DECLINE]
    assert not is_suspected_trap(one_flag)

    two_flags = [*one_flag, ContinuationTrapFlag.MATERIAL_EXHAUSTED]
    assert is_suspected_trap(two_flags)


def test_continuation_override_without_rank_history_has_no_flags_from_rank_data():
    # rank_historyがなくても、CATALYST/テーマ/市場資金は中立基準点を持つため
    # STRONG_MATERIAL_THEME以外のrank由来フラグは立たない。
    candidate = WeeklyCandidate(name="データなし銘柄")
    applies, flags = continuation_override(candidate)
    assert applies is False
    assert ContinuationOverrideFlag.RANK_MAINTAINED_OR_UP not in flags


# ---------------------------------------------------------------------------
# select_winners()
# ---------------------------------------------------------------------------


def test_select_winners_picks_highest_score_as_model_winner():
    candidates = [SEISETSU_CANDIDATE, ONCOLYS_CANDIDATE, TERADRONE_CANDIDATE, EPLI_CANDIDATE, KOBAYASHI_CANDIDATE]
    selection = select_winners(candidates)
    # 誠建設工業(80点)が最高得点でMODEL WINNER。
    assert selection.model_winner is not None
    assert selection.model_winner.name == "誠建設工業"


def test_select_winners_excludes_stop_high_locked_stock_from_executable_winner():
    candidates = [SEISETSU_CANDIDATE, ONCOLYS_CANDIDATE, TERADRONE_CANDIDATE, EPLI_CANDIDATE, KOBAYASHI_CANDIDATE]
    selection = select_winners(candidates)
    # 誠建設工業はストップ高固着(チャート/出来高=15点満点)で買い注文が
    # 約定しない可能性が高いため除外され、次点のオンコリスバイオが
    # EXECUTABLE WINNERになる。MODEL WINNERとは異なる銘柄なので両方記録される。
    assert selection.executable_winner is not None
    assert selection.executable_winner.name == "オンコリスバイオ"
    assert selection.is_unified is False


def test_select_winners_unifies_when_model_and_executable_match():
    # ストップ高固着していない銘柄だけを候補にすれば、MODEL WINNERが
    # そのままEXECUTABLE WINNERにもなり一本化される。
    candidates = [ONCOLYS_CANDIDATE, TERADRONE_CANDIDATE, EPLI_CANDIDATE, KOBAYASHI_CANDIDATE]
    selection = select_winners(candidates)
    assert selection.model_winner is not None
    assert selection.model_winner.name == "オンコリスバイオ"
    assert selection.executable_winner is not None
    assert selection.executable_winner.name == "オンコリスバイオ"
    assert selection.is_unified is True


def test_select_winners_returns_empty_selection_without_any_computable_candidate():
    candidates = [WeeklyCandidate(name="データなし銘柄1"), WeeklyCandidate(name="データなし銘柄2")]
    selection = select_winners(candidates)
    assert selection.model_winner is None
    assert selection.executable_winner is None
