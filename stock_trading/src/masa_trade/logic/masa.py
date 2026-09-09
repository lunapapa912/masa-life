"""まー式 統合運用プロンプト v1.3 に沿った判定ロジック(6ゲート + 3スコア + CIO決裁書)。

役割分担の整理(ユーザー指示に基づく。詳細は両プロンプトの原文を参照):
    - v2.19(ZERO-BASE DISCOVERY / ANCHORING CONTROL / BARON DISCOVERY LAYER /
      EXECUTION CONSTRAINT LAYER / EXECUTABLE EV PRINCIPLE):
      日次スクリーニングで新規候補を発掘するロジック。
      全市場をゼロベースでスクリーニングし、NEW DISCOVERY(新規候補)を抽出・
      仮ランキングしたあとで初めて EXISTING WATCH(既存WATCH・保有・過去相談銘柄)を
      合流させ、FINAL RANKING を作る。候補は100点満点
      (材料・カタリスト25 / 需給20 / チャート・ENTRY位置20 / BARON SCORE15 /
      新規性・材料鮮度10 / EXECUTION適性10)でスコアリングされ、
      「①今夜PTS ②事前注文 ③12:30以降 ④WATCHのみ ⑤時間制約で除外」の5分類から
      MAIN ACTION(+必要ならSUB ACTION)を決定する。
      このファイルでは v2.19 に一切手を入れない。watchlist(=v2.19のFINAL RANKING
      で選ばれた候補)を受け取るところから始まる。
    - v1.3(まー式AI投資会社・統合運用プロンプト): 発掘済みの候補を、
      モードA(全市場発掘)/B(候補比較)/C(個別精査)で深掘りし、
      3スコア・6ゲート・CIO決裁書に落とし込む本体ロジック。
      この `judge()` が担当するのはここ。

現時点のステータス:
    【6ゲート】【スコア】【CIO決裁書を冒頭に表示】の項目名・配点は
    v1.3原文どおりに `logic/schema.py` へ反映済み。
    一方で、各ゲートの合否判定条件・各スコア項目の配点式・CIO決裁書の
    企業判定/売買判定を導く最終ロジックは v1.3 の詳細ルール確定待ちのため、
    このファイルでは「保守的なプレースホルダー判定」+「配点前の生データ集計」までを
    実装している。各関数の TODO を参照。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from masa_trade.config import Settings
from masa_trade.logic import indicators
from masa_trade.logic.schema import (
    ChartData,
    CIODecisionMemo,
    CorporateJudgment,
    Gate,
    GateResult,
    GateStatus,
    JudgeInput,
    OrderProposal,
    RatingSet,
    ScoreResult,
    TradeDecision,
    empty_corporate_value_score,
    empty_entry_score,
    empty_feasibility_score,
)

# ---------------------------------------------------------------------------
# チャートデータの組み立て(v1.3の短期ENTRYスコアの材料)
# ---------------------------------------------------------------------------


def build_chart_data(ohlcv: pd.DataFrame, settings: Settings) -> ChartData:
    """OHLCVからテクニカル指標を計算し ChartData を組み立てる。"""
    params = settings.masa_logic
    close = ohlcv["Close"]
    volume = ohlcv["Volume"]

    sma_short = indicators.sma(close, params["moving_averages"]["short"]).iloc[-1]
    sma_medium = indicators.sma(close, params["moving_averages"]["medium"]).iloc[-1]
    sma_long = indicators.sma(close, params["moving_averages"]["long"]).iloc[-1]
    rsi_value = indicators.rsi(close, params["rsi_period"]).iloc[-1]
    vol_ratio = indicators.volume_ratio(volume, params["volume_average_window"]).iloc[-1]

    if sma_short > sma_medium > sma_long:
        trend = "up"
    elif sma_short < sma_medium < sma_long:
        trend = "down"
    else:
        trend = "range"

    recent = close.tail(20)
    return ChartData(
        ohlcv=ohlcv,
        sma_short=float(sma_short),
        sma_medium=float(sma_medium),
        sma_long=float(sma_long),
        rsi=float(rsi_value),
        volume_ratio=float(vol_ratio),
        trend=trend,
        support_price=float(recent.min()),
        resistance_price=float(recent.max()),
        # TODO: ブレイクアウト・ギャップアップ・VWAPの正式な判定条件はv1.3確定後に実装する。
        breakout=None,
        gap_up_pct=None,
    )


# ---------------------------------------------------------------------------
# cio_review設定(ゲートの閾値など)の読み取りヘルパー
# ---------------------------------------------------------------------------


def _cio_review_get(settings: Settings, dotted_key: str, default: Any) -> Any:
    """settings.yaml の cio_review セクションをドット区切りキーで読む。

    例: _cio_review_get(settings, "gates.dilution.max_acceptable_ratio_pct", 10.0)
    """
    node: Any = settings.raw.get("cio_review", {})
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


# ---------------------------------------------------------------------------
# 【6ゲート】判定
#
# 各関数は「合否を出すのに十分なデータがあるか」を最初に見て、なければ UNKNOWN を返す。
# 具体的な合否の閾値は v1.3 の詳細ルールが確定してから調整すること
# (settings.yaml の cio_review セクションに仮値を置いている)。
# CAUTION(重大ではないが注意を要する状態)の判定条件は未実装(TODO)。
# ---------------------------------------------------------------------------


def _check_g3_material_existence(data: JudgeInput, settings: Settings) -> GateResult:
    material = data.material
    missing = [
        field_name
        for field_name, value in (
            ("headline", material.headline),
            ("source", material.source),
            ("published_at", material.published_at),
        )
        if value is None
    ]
    if missing:
        return GateResult(
            gate=Gate.G3_MATERIAL_EXISTENCE,
            status=GateStatus.UNKNOWN,
            reason="材料の基本情報が不足している。",
            missing_data=missing,
        )

    if material.is_primary_source is False and not material.verified:
        return GateResult(
            gate=Gate.G3_MATERIAL_EXISTENCE,
            status=GateStatus.FAIL,
            reason="一次情報ではなく、裏取りも取れていない材料。",
            critical=True,
        )

    return GateResult(
        gate=Gate.G3_MATERIAL_EXISTENCE,
        status=GateStatus.PASS,
        reason="材料の実在性を確認できる情報が揃っている。",
        evidence=[material.headline or ""],
    )


def _check_g1_accounting(data: JudgeInput, settings: Settings) -> GateResult:
    accounting = data.accounting
    if accounting.going_concern_doubt is None and accounting.auditor_opinion is None:
        return GateResult(
            gate=Gate.G1_ACCOUNTING,
            status=GateStatus.UNKNOWN,
            reason="会計面のリスク情報(継続前提・監査意見)が未取得。",
            missing_data=["going_concern_doubt", "auditor_opinion"],
        )

    bad_opinions = {"不適正", "意見不表明"}
    if (
        accounting.going_concern_doubt
        or accounting.auditor_opinion in bad_opinions
        or accounting.delisting_criteria_risk
    ):
        return GateResult(
            gate=Gate.G1_ACCOUNTING,
            status=GateStatus.FAIL,
            reason="継続前提・監査意見・上場維持基準のいずれかに重大な問題がある。",
            critical=True,
        )

    if accounting.restatement_flag or accounting.earnings_delay_flag:
        return GateResult(
            gate=Gate.G1_ACCOUNTING,
            status=GateStatus.CAUTION,
            reason="過年度訂正または決算延期の履歴があり、注意を要する。",
        )

    return GateResult(
        gate=Gate.G1_ACCOUNTING,
        status=GateStatus.PASS,
        reason="現時点で会計面の重大な危険信号は確認されていない。",
    )


def _check_g2_dilution(data: JudgeInput, settings: Settings) -> GateResult:
    dilution = data.dilution
    max_ratio = _cio_review_get(settings, "gates.dilution.max_acceptable_ratio_pct", 10.0)

    if (
        dilution.dilution_ratio_estimate_pct is None
        and dilution.warrant_overhang is None
        and not dilution.recent_issuances_12m
        and not dilution.pending_dilution_events
    ):
        return GateResult(
            gate=Gate.G2_DILUTION,
            status=GateStatus.UNKNOWN,
            reason="希薄化リスクを判定する情報が未取得。",
            missing_data=["dilution_ratio_estimate_pct", "warrant_overhang"],
        )

    if dilution.dilution_ratio_estimate_pct is not None and dilution.dilution_ratio_estimate_pct > max_ratio:
        return GateResult(
            gate=Gate.G2_DILUTION,
            status=GateStatus.FAIL,
            reason=f"想定希薄化率({dilution.dilution_ratio_estimate_pct}%)が許容値({max_ratio}%)を超える。",
            critical=True,
        )

    if dilution.warrant_overhang:
        return GateResult(
            gate=Gate.G2_DILUTION,
            status=GateStatus.CAUTION,
            reason="行使価格の低いワラントの残存など、希薄化の懸念材料がある。",
        )

    return GateResult(
        gate=Gate.G2_DILUTION,
        status=GateStatus.PASS,
        reason="希薄化リスクは許容範囲内。",
    )


def _check_g4_earnings_linkage(data: JudgeInput, settings: Settings) -> GateResult:
    linkage = data.earnings_linkage
    if linkage.estimated_revenue_impact is None and linkage.estimated_impact_timing is None:
        return GateResult(
            gate=Gate.G4_EARNINGS_LINKAGE,
            status=GateStatus.UNKNOWN,
            reason="材料が業績にどう繋がるかの情報が未取得。",
            missing_data=["estimated_revenue_impact", "estimated_impact_timing"],
        )

    if linkage.estimated_revenue_impact == 0:
        return GateResult(
            gate=Gate.G4_EARNINGS_LINKAGE,
            status=GateStatus.FAIL,
            reason="材料はあるが、業績への影響が見込めない。",
            critical=True,
        )

    return GateResult(
        gate=Gate.G4_EARNINGS_LINKAGE,
        status=GateStatus.PASS,
        reason="材料が業績インパクトに繋がる見立てがある。",
    )


def _check_g5_priced_in(data: JudgeInput, settings: Settings) -> GateResult:
    pricing = data.pricing_in
    if pricing.price_change_since_material_pct is None or pricing.days_since_material is None:
        return GateResult(
            gate=Gate.G5_PRICED_IN,
            status=GateStatus.UNKNOWN,
            reason="材料発表後の株価反応(材料の賞味期限)を判定する情報が未取得。",
            missing_data=["price_change_since_material_pct", "days_since_material"],
        )

    priced_in_threshold = _cio_review_get(settings, "gates.pricing_in.already_priced_in_pct", 15.0)
    lookback_days = _cio_review_get(settings, "gates.pricing_in.lookback_days", 5)

    if (
        pricing.days_since_material <= lookback_days
        and abs(pricing.price_change_since_material_pct) >= priced_in_threshold
    ):
        return GateResult(
            gate=Gate.G5_PRICED_IN,
            status=GateStatus.FAIL,
            reason="材料発表直後に想定以上に株価が反応済みで、織り込み度が高い。",
        )

    return GateResult(
        gate=Gate.G5_PRICED_IN,
        status=GateStatus.PASS,
        reason="材料はまだ十分に織り込まれていないと見られる。",
    )


def _check_g6_short_term_catalyst(data: JudgeInput, settings: Settings) -> GateResult:
    catalyst = data.catalyst_timing
    if catalyst.next_catalyst_date is None:
        return GateResult(
            gate=Gate.G6_SHORT_TERM_CATALYST,
            status=GateStatus.UNKNOWN,
            reason="短期(1〜3営業日)で控える次のカタリストの情報が未取得。",
            missing_data=["next_catalyst_date"],
        )

    max_days_ahead = _cio_review_get(settings, "gates.short_term_catalyst.max_days_ahead", 3)
    days_ahead = (catalyst.next_catalyst_date - settings.now().date()).days

    if days_ahead < 0 or days_ahead > max_days_ahead:
        return GateResult(
            gate=Gate.G6_SHORT_TERM_CATALYST,
            status=GateStatus.FAIL,
            reason=f"次のカタリストが短期(~{max_days_ahead}営業日)の想定期間外。",
        )

    return GateResult(
        gate=Gate.G6_SHORT_TERM_CATALYST,
        status=GateStatus.PASS,
        reason="短期の想定期間内にカタリストが控えている。",
    )


_GATE_CHECKS = (
    _check_g1_accounting,
    _check_g2_dilution,
    _check_g3_material_existence,
    _check_g4_earnings_linkage,
    _check_g5_priced_in,
    _check_g6_short_term_catalyst,
)


def run_gates(data: JudgeInput, settings: Settings) -> list[GateResult]:
    return [check(data, settings) for check in _GATE_CHECKS]


# ---------------------------------------------------------------------------
# 【スコア】企業価値100 / 短期ENTRY100 / 実行可能性100
#
# 項目名・配点は logic/schema.py の *_ITEM_DEFINITIONS に v1.3原文どおり定義済み。
# TODO: 各項目の配点式(points)はv1.3の詳細ルール確定待ちのため、
#       ここでは全項目 points=None のまま返す(＝合計スコアも算出不可)。
# ---------------------------------------------------------------------------


def score_corporate_value(data: JudgeInput) -> ScoreResult:
    score = empty_corporate_value_score()
    return ScoreResult(
        name=score.name,
        items=score.items,
        max_score=score.max_score,
        notes=["各項目の配点式はv1.3の詳細ルール確定待ち"],
    )


def score_entry(data: JudgeInput) -> ScoreResult:
    score = empty_entry_score()
    return ScoreResult(
        name=score.name,
        items=score.items,
        max_score=score.max_score,
        notes=["各項目の配点式はv1.3の詳細ルール確定待ち"],
    )


def score_feasibility(data: JudgeInput) -> ScoreResult:
    score = empty_feasibility_score()
    return ScoreResult(
        name=score.name,
        items=score.items,
        max_score=score.max_score,
        notes=["各項目の配点式はv1.3の詳細ルール確定待ち"],
    )


# ---------------------------------------------------------------------------
# 【CIO決裁書を冒頭に表示】の組み立て
# ---------------------------------------------------------------------------


def _decide_trade(
    gates: list[GateResult],
    corporate_value: ScoreResult,
    entry: ScoreResult,
    feasibility: ScoreResult,
    settings: Settings,
) -> tuple[TradeDecision, str]:
    """売買判定(ENTRY/TEST ENTRY/WAIT/WATCH/AVOID/EXIT)を決める。

    TODO: v1.3原文はENTRY/TEST ENTRY/WATCH/AVOIDの具体的な数値境界を明記していない
    (期待値・執行条件など定性的な判断が必要)。ここでは保守的に
    「重大FAIL→AVOID」「情報不足→WAIT」「スコア閾値超過→ENTRY/WATCH」の
    プレースホルダーのみ実装する。
    """
    critical_failed = [g for g in gates if g.status == GateStatus.FAIL and g.critical]
    if critical_failed:
        names = ", ".join(g.gate.value for g in critical_failed)
        return TradeDecision.AVOID, f"重大ゲートFAIL: {names}"

    failed = [g for g in gates if g.status == GateStatus.FAIL]
    if failed:
        names = ", ".join(g.gate.value for g in failed)
        return TradeDecision.AVOID, f"以下のゲートがFAIL: {names}"

    unknown = [g for g in gates if g.status == GateStatus.UNKNOWN]
    if unknown:
        names = ", ".join(g.gate.value for g in unknown)
        return TradeDecision.WAIT, f"以下のゲート判定に必要なデータが不足: {names}"

    totals = [corporate_value.total, entry.total, feasibility.total]
    if any(t is None for t in totals):
        return (
            TradeDecision.WAIT,
            "3スコアの配点式が未確定、またはスコア算出に必要なデータが不足している。",
        )

    entry_min = _cio_review_get(settings, "decision_thresholds.entry_min_total_score", 210)
    watch_min = _cio_review_get(settings, "decision_thresholds.watch_min_total_score", 150)
    total_score = sum(totals)

    if total_score >= entry_min:
        return TradeDecision.ENTRY, f"3スコア合計 {total_score:.1f} がENTRY基準を超過。"
    if total_score >= watch_min:
        return TradeDecision.WATCH, f"3スコア合計 {total_score:.1f} はWATCH継続ライン。"
    return TradeDecision.AVOID, f"3スコア合計 {total_score:.1f} は基準未達。"


def judge(data: JudgeInput, settings: Settings) -> CIODecisionMemo:
    """1銘柄・1回精査分の入力から CIO決裁書 を組み立てる。"""
    gates = run_gates(data, settings)
    corporate_value = score_corporate_value(data)
    entry = score_entry(data)
    feasibility = score_feasibility(data)

    trade_decision, recommended_action = _decide_trade(gates, corporate_value, entry, feasibility, settings)

    missing_info = sorted({item for g in gates for item in g.missing_data})

    return CIODecisionMemo(
        symbol=data.symbol,
        name=data.name,
        mode=data.mode,
        research_timestamp=data.research_timestamp or settings.now(),
        information_cutoff=data.information_cutoff,
        current_price=data.current_price,
        # TODO: 企業判定(優良/標準/脆弱/不明)は企業価値スコア確定後に導出するロジックが必要。
        corporate_judgment=CorporateJudgment.UNKNOWN,
        trade_decision=trade_decision,
        # TODO: 総合・短期・中期・長期・テンバガー評価(各10点)の算出ロジックは未実装。
        ratings=RatingSet(),
        corporate_value_score=corporate_value,
        entry_score=entry,
        feasibility_score=feasibility,
        gates=gates,
        # TODO: 根拠3・反対3は独立分析(強気/弱気チーム)の統合結果が必要なため未実装。
        supporting_points=[],
        opposing_points=[],
        recommended_action=recommended_action,
        # TODO: 注文案(区分・指値・株数・逆指値・利確・RRなど)の算出ロジックは未実装。
        order_proposal=OrderProposal(),
        priority_reason_over_others=None,
        missing_info=missing_info,
        confidence=None,
    )
