"""まー式・鉄人戦週間ランキング戦略 v2.1 の判定ロジック本体。

v1.3(logic/masa.py)と同じ「でっち上げない」方針を取る:
    - 原文に数値・計算式が明記されている箇所(FUTURE MFE SCOREの配点、
      MARKET REGIME DEFENSEの閾値、CONTINUATION OVERRIDEの「3項目以上」、
      MFE/MAE/CAPTURE RATEの定義式)はそのまま実装する。
    - 明記されていない箇所(A/B/C分類の厳密な境界、MODEL WINNER/EXECUTABLE
      WINNERの選定式、PEAK-OUT WARNINGの「複数成立」の具体的な組み合わせなど)は
      TODOのプレースホルダーとし、実データでの検証(10〜20〜30回)を経てから
      ユーザーと一緒に数値化する。

v2.1はv1.3のjudge()を呼ばない(ユーザー指示により今回は完全に独立させる)。
"""

from __future__ import annotations

from masa_trade.logic.common.order import MarketRegime
from masa_trade.logic.weekly.schema import (
    ContinuationOverrideFlag,
    FutureMfeScore,
    MarketRegimeInput,
    MfeMaeResult,
    PeakOutAssessment,
    StockType,
    WeeklyCandidate,
    WinnerSelection,
    empty_future_mfe_score,
)

# ---------------------------------------------------------------------------
# 【15.MARKET REGIME】
# DEFENSE目安(原文どおり): 日経-2%以上/TOPIX-2%以上/プライム値下がり80%以上/
# グロース値下がり70%以上のうち2項目以上。
# NORMAL/CAUTIONの境界は原文に数値の明記がないため、1項目該当でCAUTIONとする
# 保守的なプレースホルダー(TODO: 実データで調整)。
# ---------------------------------------------------------------------------


def classify_market_regime(data: MarketRegimeInput) -> MarketRegime:
    conditions = [
        data.nikkei_change_pct is not None and data.nikkei_change_pct <= -2.0,
        data.topix_change_pct is not None and data.topix_change_pct <= -2.0,
        data.prime_decliner_pct is not None and data.prime_decliner_pct >= 80.0,
        data.growth_decliner_pct is not None and data.growth_decliner_pct >= 70.0,
    ]
    met = sum(conditions)

    if met >= 2:
        return MarketRegime.DEFENSE
    if met == 1:
        # TODO: CAUTIONの正式な条件はv2.1に数値の明記がないため暫定(1項目該当)。
        return MarketRegime.CAUTION
    return MarketRegime.NORMAL


# ---------------------------------------------------------------------------
# 【4.CONTINUATION OVERRIDE】7項目のうち3項目以上で過熱ペナルティを弱める。
# ---------------------------------------------------------------------------


def applies_continuation_override(flags: list[ContinuationOverrideFlag]) -> bool:
    return len(set(flags)) >= 3


# ---------------------------------------------------------------------------
# 【17.PEAK-OUT WARNING】原文は「複数成立したら」とあるのみで具体的な件数の
# 明記がない。ここでは保守的に2件以上を暫定閾値とする(TODO: 実データで調整)。
# ---------------------------------------------------------------------------


def is_peak_out_warning(assessment: PeakOutAssessment) -> bool:
    return len(set(assessment.flags)) >= 2


# ---------------------------------------------------------------------------
# 【20.MFE/MAE】【21.MFE CAPTURE RATE】定義式そのまま。
# ---------------------------------------------------------------------------


def build_mfe_mae(
    baseline_price: float,
    highest_price_within_5d: float | None,
    lowest_price_within_5d: float | None,
) -> MfeMaeResult:
    return MfeMaeResult(
        baseline_price=baseline_price,
        highest_price_within_5d=highest_price_within_5d,
        lowest_price_within_5d=lowest_price_within_5d,
    )


def compute_capture_rate(realized_return_pct: float, mfe_pct: float) -> float | None:
    """MFE CAPTURE RATE(%) = 実現利益率 ÷ MFE × 100(§21)。

    MFEが0以下の場合は「残っていた上昇余地がない」ため算出不可としてNoneを返す。
    """
    if mfe_pct <= 0:
        return None
    return (realized_return_pct / mfe_pct) * 100


# ---------------------------------------------------------------------------
# 【3.3タイプ分類】【10.FUTURE MFE SCORE】【11.MODEL/EXECUTABLE WINNER】
#
# TODO: 以下は原文に厳密な数値式がないため、スコア項目の器だけ用意し
# points は算出しない(v1.3のscore_*()と同じ方針)。
# A/B/C分類・WINNER選定の自動化は、実データでの検証を経てから実装する。
# ---------------------------------------------------------------------------


def score_future_mfe(candidate: WeeklyCandidate) -> FutureMfeScore:
    score = empty_future_mfe_score()
    return FutureMfeScore(
        items=score.items,
        max_score=score.max_score,
        notes=["各項目の配点式はv2.1の実データ検証(10〜20〜30回)を経て確定する"],
    )


def classify_stock_type(candidate: WeeklyCandidate) -> StockType | None:
    """A(CONTINUATION)/B(MAIN EARLY)/C(CATALYST EARLY)の分類。

    原文の「6〜20位」「+0.5〜+3%」等は目安であり厳密な境界式ではないため、
    誤判定を招く決め打ちルールは実装しない。現状は常にNone(未分類)を返す。
    """
    return None


def select_winners(candidates: list[WeeklyCandidate]) -> WinnerSelection:
    """MODEL WINNER/EXECUTABLE WINNER/次点2枠を選ぶ。

    TODO: FUTURE MFE SCOREの配点式(score_future_mfe)が未実装のため、
    現状はスコアに基づく自動選定ができない。空のWinnerSelectionを返す。
    """
    return WinnerSelection()
