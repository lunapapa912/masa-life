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

from datetime import date

from masa_trade.logic.common.order import MarketRegime
from masa_trade.logic.weekly.schema import (
    Checkpoint,
    ContinuationOverrideFlag,
    DisclosureRecord,
    FutureMfeScore,
    FutureMfeScoreItem,
    MarketRegimeInput,
    MfeMaeResult,
    PeakOutAssessment,
    RankEntry,
    RankHistory,
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
# 【10.FUTURE MFE SCORE】
#
# 2026-09-07(月)〜09-08(火)の実データ(50銘柄・6時点、rank + 上昇率)から
# 逆算した配点式。実装できたのは「ランキング推移」「上昇率加速度」
# 「過熱/下落リスク」の3項目(計45点)のみ。
# 残り4項目(チャート/出来高・CATALYST・テーマ/市場資金・過去統計適合度)は
# 出来高・材料・テーマ・複数週の統計データが未取得のため points=None のまま。
#
# 月曜_始まり値(OPEN)は全50銘柄が意味を持たない基準(-100%)から始まるため、
# 以下のスコア計算は OPEN のチェックポイントを除外して行う。
# ---------------------------------------------------------------------------


def _real_moments(rank_history: RankHistory) -> list[tuple[date, Checkpoint, RankEntry]]:
    """上昇率が実際に入っている時点だけを時系列で返す。

    月曜始まり値(週の最初のOPEN)は全50銘柄が-100%の無意味な基準になるため
    pct_change=Noneで記録される想定であり、その1点だけが自然に除外される。
    火曜以降のOPEN(始まり値)には実際の上昇率が入るため除外しない
    (Checkpointは曜日非依存なので、Checkpoint自体では月曜と火曜のOPENを区別できない)。
    """
    return [(d, cp, entry) for d, cp, entry in rank_history.ordered_entries if entry.pct_change is not None]


def score_ranking_progression(rank_history: RankHistory | None) -> FutureMfeScoreItem:
    """①ランキング推移(20点) = 最高到達順位(10点) + 順位安定性(10点)。

    2026-09-07/08の実データでの根拠:
        誠建設工業・オンコリスバイオ(継続成功)は最高到達順位1位・ドローダウン1で
        満点20点になる一方、テラドローン・エプリー(前引け後に急落)は最高到達順位
        3〜4位まで行きながらドローダウンが38〜42に達し、大きく減点される。
    """
    name = "ランキング推移"
    if rank_history is None:
        return FutureMfeScoreItem(name=name, max_points=20)

    moments = _real_moments(rank_history)
    if not moments:
        return FutureMfeScoreItem(name=name, max_points=20)

    ranks = [entry.rank for _, _, entry in moments]
    best_rank, worst_rank = min(ranks), max(ranks)
    drawdown = worst_rank - best_rank

    if best_rank <= 3:
        best_rank_score = 10.0
    elif best_rank <= 10:
        best_rank_score = 7.0
    elif best_rank <= 20:
        best_rank_score = 4.0
    else:
        best_rank_score = 0.0

    if drawdown <= 2:
        stability_score = 10.0
    elif drawdown <= 9:
        stability_score = 6.0
    elif drawdown <= 19:
        stability_score = 3.0
    else:
        stability_score = 0.0

    return FutureMfeScoreItem(
        name=name,
        max_points=20,
        points=best_rank_score + stability_score,
        evidence=[
            f"最高到達順位={best_rank}位",
            f"ドローダウン={drawdown}位(最高{best_rank}位→最悪{worst_rank}位、OPEN除く)",
        ],
        confidence="中(2026-09-07/08の6時点データのみで導出。出来高等は未反映)",
    )


def score_momentum_acceleration(rank_history: RankHistory | None) -> FutureMfeScoreItem:
    """②上昇率加速度(15点) = 直近時点の符号(8点) + セッション内最大下落幅(7点)。

    2026-09-07/08の実データでの根拠:
        テラドローン・エプリーは前引け→終値で上昇率がプラスからマイナスへ転落し
        (それぞれ-14.7pt, -9.8ptの下落)、この項目が0点になる。オンコリスバイオは
        同区間で-4.2ptの押しはあったがマイナス転落はしておらず、大きく減点されない。
    """
    name = "上昇率加速度"
    if rank_history is None:
        return FutureMfeScoreItem(name=name, max_points=15)

    moments = _real_moments(rank_history)
    if len(moments) < 2:
        return FutureMfeScoreItem(name=name, max_points=15)

    pcts = [entry.pct_change for _, _, entry in moments]
    latest_pct = pcts[-1]
    sign_score = 8.0 if latest_pct is not None and latest_pct >= 0 else 0.0

    max_drop = max(0.0, max(pcts[i - 1] - pcts[i] for i in range(1, len(pcts))))
    if max_drop <= 3:
        drop_score = 7.0
    elif max_drop <= 8:
        drop_score = 4.0
    else:
        drop_score = 0.0

    return FutureMfeScoreItem(
        name=name,
        max_points=15,
        points=sign_score + drop_score,
        evidence=[
            f"直近上昇率={latest_pct}%",
            f"セッション内最大下落幅={max_drop:.1f}pt",
        ],
        confidence="中(2026-09-07/08の6時点データのみで導出)",
    )


def score_overheat_risk(rank_history: RankHistory | None) -> FutureMfeScoreItem:
    """⑥過熱/下落リスク(10点) = 満点から以下2条件それぞれで-5点。

        (a) 上昇率がプラスからマイナスへ転落した時点がある
        (b) 順位が10位以上悪化したあと10位以上回復し、その後また10位以上悪化する
            (=一度戻したのに再び崩れる「往って来い」パターン)

    2026-09-07/08の実データでの根拠:
        テラドローン(順位 3→41→13→26)・エプリー(4→46→4→31)は(a)(b)両方に該当し0点。
        誠建設工業・オンコリスバイオはどちらにも該当せず満点10点。

    (b)は上昇率の反発幅ではなく順位の回復幅で判定する。テラドローンの実際の反発は
    上昇率ベースだと+4.7pt(小さめの閾値だと拾えない)だが、順位ベースでは41位→13位
    という明確な回復のため、こちらの方が実データに対して頑健。

    注意: このロジックは「一度プラスだったのに崩れた」パターンのみを検出する。
    ビーエイブル・チャットプラスのように最初から一貫して弱い銘柄は(a)(b)に
    該当せずこの項目では減点されない(①ランキング推移側で低評価される設計)。
    """
    name = "過熱/下落リスク"
    if rank_history is None:
        return FutureMfeScoreItem(name=name, max_points=10)

    moments = _real_moments(rank_history)
    if len(moments) < 2:
        return FutureMfeScoreItem(name=name, max_points=10)

    pcts = [entry.pct_change for _, _, entry in moments]
    ranks = [entry.rank for _, _, entry in moments]
    points = 10.0
    reasons: list[str] = []

    if any(pcts[i - 1] > 0 and pcts[i] < 0 for i in range(1, len(pcts))):
        points -= 5.0
        reasons.append("上昇率がプラスからマイナスへ転落した時点がある")

    rebound_then_fail = False
    for i in range(1, len(ranks)):
        improvement = ranks[i - 1] - ranks[i]  # 正なら順位が良くなった(数字が小さくなった)
        if improvement < 10:
            continue
        recovered_rank = ranks[i]
        if any(ranks[j] - recovered_rank >= 10 for j in range(i, len(ranks))):
            rebound_then_fail = True
            break
    if rebound_then_fail:
        points -= 5.0
        reasons.append("順位が一度大きく回復したあと、再び大きく悪化した時点がある")

    return FutureMfeScoreItem(
        name=name,
        max_points=10,
        points=max(points, 0.0),
        evidence=reasons or ["急落・反落パターンは検出されず"],
        confidence="低(「一度プラスだった銘柄の崩れ」のみ検出する簡易ロジック)",
    )


# ---------------------------------------------------------------------------
# 【10.FUTURE MFE SCORE】③チャート/出来高(15点)の一部: ストップ高固定検出
#
# データソース確認結果: 週間値幅ランキング画像は順位と上昇率(%)のみを提供し、
# 絶対株価・基準値段(直前営業日終値)を一切含まない(RankEntry.priceはスキーマ上
# 存在するが、loader.py/実データとも常にNone)。そのため、JPX制限値幅表を使った
# 正式なストップ高判定(score_stop_high_lock, get_price_limit_width)は実装せず、
# 「上昇率の連続凍結」をストップ高の代理シグナルとして扱う score_stop_high_lock_proxy
# のみを実装する。絶対株価データが手に入った場合の移行手順はREADMEのTODOを参照。
# ---------------------------------------------------------------------------


def score_stop_high_lock_proxy(rank_history: RankHistory | None, total_stocks: int = 50) -> FutureMfeScoreItem:
    """ストップ高固定のプロキシ検出(15点満点、「チャート/出来高」項目に対応)。

    TODO: 絶対株価・基準値段(直前営業日終値)が取得できるデータソースに切り替わり
    次第、JPX制限値幅表ベースの正式な判定(get_price_limit_width + score_stop_high_lock)
    に置き換えること。必要なデータ: 銘柄コード(symbol)・当該日の基準値段・
    各チェックポイントの終値。README「今後実装が必要な部分」参照。

    プロキシ判定: 直近時点まで上昇率が3時点以上連続で完全一致(誤差0.01pt以内)
    していることを「値幅制限で売買が成立していない」ことの代理シグナルとする。
    ただし出来高が単に枯れているだけの銘柄(古林紙工のような順位下位の凍結)と
    区別できないため、直近順位が上位30%(50銘柄なら15位以内)かどうかで
    強気シグナルか出来高枯渇の疑いかを分ける。

    このスコアは「上振れボーナス」として設計しており、該当なしを減点しない(0点)。
    v1.3同様、各チェックポイント時点で入手可能な情報だけを使う
    (LOOK-AHEAD BIAS禁止, v2.1原文§26): 凍結の連続数は「直近時点で終わる」
    トレイリングの連続数のみを見る。
    """
    name = "チャート/出来高"
    if rank_history is None:
        return FutureMfeScoreItem(name=name, max_points=15)

    moments = _real_moments(rank_history)
    if not moments:
        return FutureMfeScoreItem(name=name, max_points=15)

    pcts = [entry.pct_change for _, _, entry in moments]
    streak = 1
    for i in range(len(pcts) - 1, 0, -1):
        if abs(pcts[i] - pcts[i - 1]) <= 0.01:
            streak += 1
        else:
            break

    if streak < 3:
        return FutureMfeScoreItem(
            name=name,
            max_points=15,
            points=0.0,
            evidence=[f"直近の上昇率凍結は{streak}時点のみ(3時点未満)"],
            confidence="低(proxy判定。絶対株価データ未取得)",
        )

    latest_rank = moments[-1][2].rank
    top_threshold = round(total_stocks * 0.3)

    if latest_rank <= top_threshold:
        points = 15.0
        reason = (
            f"上昇率が{streak}時点連続で完全一致(凍結)、"
            f"かつ直近順位{latest_rank}位が上位{top_threshold}位以内"
            "→ストップ高で売買不成立の可能性"
        )
    else:
        points = 3.0
        reason = (
            f"上昇率が{streak}時点連続で完全一致(凍結)しているが、"
            f"直近順位{latest_rank}位は上位{top_threshold}位外"
            "→出来高枯渇による凍結の疑い(強気シグナルとしては弱い)"
        )

    return FutureMfeScoreItem(
        name=name,
        max_points=15,
        points=points,
        evidence=[reason],
        confidence="低(proxy判定。絶対株価データ未取得のため正式なストップ高判定ではない)",
    )


# ---------------------------------------------------------------------------
# 【10.FUTURE MFE SCORE】④CATALYST(20点)
#
# 開示タイトルのキーワードだけで強気/中立/弱気を判定する辞書ベースの簡易ロジック。
# LLM呼び出しなし・完全無料。データ取得は logic/weekly/tdnet.py
# (無料・認証不要のやのしんWEB-API)を使う。
#
# キーワードは後から調整しやすいよう定数として分離している。
# CATALYST_NEGATIVE_KEYWORDS は「キーワード: 該当時の点数」の辞書にして、
# 深刻度に応じて0点(重大)〜3点(軽微)の幅を持たせている。
# 「新株予約権」は実データ(2026-09-07のテラドローンの新株予約権大量行使開示、
# 同日の順位急落と時期が一致)を踏まえて追加した。
# ---------------------------------------------------------------------------

CATALYST_POSITIVE_KEYWORDS: tuple[str, ...] = (
    "上方修正",
    "増配",
    "自己株式取得",
    "業務提携",
    "資本業務提携",
    "特別配当",
    "新規事業",
    "大型受注",
)

CATALYST_NEGATIVE_KEYWORDS: dict[str, float] = {
    # 重大(0点): 上場維持・希薄化・特損など、点数で相殺すべきでない問題
    "上場廃止": 0.0,
    "内部統制の不備": 0.0,
    "特別損失": 0.0,
    "新株予約権": 0.0,
    # 軽微(3点): 業績下振れ系だが上記ほど深刻ではないもの
    "下方修正": 3.0,
    "減配": 3.0,
}

CATALYST_NEUTRAL_KEYWORDS: tuple[str, ...] = (
    "決算短信",
    "四半期報告書",
    "半期報告書",
    "有価証券報告書",
    "決算説明資料",
)


def score_catalyst_strength(disclosures: list[DisclosureRecord]) -> FutureMfeScoreItem:
    """④CATALYST(20点満点)。開示タイトルのキーワードで強気/中立/弱気を判定する。

    disclosuresは呼び出し側が「スコアリング対象の時点までに出た開示だけ」に
    絞り込んで渡すこと(LOOK-AHEAD BIAS禁止, v2.1原文§26)。
    tdnet.filter_up_to() で絞り込んでから渡す想定。

    優先順位: 弱気キーワードが1つでもあれば(最も深刻なものの点数を採用)、
    好材料キーワードやその他の開示より優先してリスクを反映する。
    弱気キーワードがなければ好材料キーワードを見る。どちらもなければ、
    決算短信等の定型開示かどうかで中立の強さを分ける。

    注意: キーワード辞書ベースの単純な判定であり、皮肉な言い回し・複合的な
    開示文脈(例: 好材料と弱気材料が同じタイトルに混在する場合など)は
    誤判定しうる。README「今後実装が必要な部分」参照。
    """
    name = "CATALYST"
    if not disclosures:
        return FutureMfeScoreItem(
            name=name,
            max_points=20,
            points=10.0,
            evidence=["対象期間に適時開示なし(判断材料なしのニュートラル基準点)"],
            confidence="低(キーワード辞書ベース)",
        )

    worst_negative: tuple[float, str] | None = None
    for record in disclosures:
        for keyword, deduction_points in CATALYST_NEGATIVE_KEYWORDS.items():
            if keyword in record.title:
                reason = f"「{record.title}」に弱気キーワード「{keyword}」"
                if worst_negative is None or deduction_points < worst_negative[0]:
                    worst_negative = (deduction_points, reason)
    if worst_negative is not None:
        points, reason = worst_negative
        return FutureMfeScoreItem(
            name=name, max_points=20, points=points, evidence=[reason], confidence="低(キーワード辞書ベース)"
        )

    positive_matches = [
        (record, keyword)
        for record in disclosures
        for keyword in CATALYST_POSITIVE_KEYWORDS
        if keyword in record.title
    ]
    if positive_matches:
        matched_keywords = {keyword for _, keyword in positive_matches}
        points = 20.0 if len(matched_keywords) >= 2 else 15.0
        record, keyword = positive_matches[0]
        return FutureMfeScoreItem(
            name=name,
            max_points=20,
            points=points,
            evidence=[f"「{record.title}」に好材料キーワード「{keyword}」"],
            confidence="低(キーワード辞書ベース)",
        )

    neutral_matches = [record for record in disclosures for keyword in CATALYST_NEUTRAL_KEYWORDS if keyword in record.title]
    if neutral_matches:
        return FutureMfeScoreItem(
            name=name,
            max_points=20,
            points=8.0,
            evidence=[f"「{neutral_matches[0].title}」は定型開示(材料性は薄い)"],
            confidence="低(キーワード辞書ベース)",
        )

    return FutureMfeScoreItem(
        name=name,
        max_points=20,
        points=5.0,
        evidence=[f"開示はあるがキーワード辞書に該当なし: 「{disclosures[0].title}」"],
        confidence="低(キーワード辞書ベース、未分類の開示)",
    )


# ---------------------------------------------------------------------------
# 【10.FUTURE MFE SCORE】⑤テーマ/市場資金(10点) = 「業種集中度スコア」
#
# みんかぶ・株探は利用規約で情報の「加工・再利用」を明示的に禁じているため
# (logic/weekly/sector.pyのモジュールdocstring参照)不採用。個別テーマ
# (AI関連・半導体関連等の思惑ベースの括り)は今回のデータソースでは判定できない。
#
# 代わりに、JPX公式の33業種区分マスタ(logic/weekly/sector.py)と自前で収集した
# 週間ランキングデータだけで完結する「業種集中度」を見る: その週の上位ランキングに
# 対象銘柄と同じ33業種の銘柄が複数ランクインしていれば、セクター全体への
# 資金流入とみなす。
# ---------------------------------------------------------------------------


def score_theme_market_flow(target_sector: str | None, peer_sectors: list[str | None]) -> FutureMfeScoreItem:
    """⑤テーマ/市場資金(10点)。target_sectorは対象銘柄のJPX 33業種区分、
    peer_sectorsは対象銘柄を除く、その週の上位N位以内の他銘柄の33業種区分一覧。

    配点(ユーザー指示どおり): 同業種の他銘柄が3社以上→8点、1〜2社→4点、
    対象銘柄のみ(0社)または業種が特定できない→中立基準点5点。
    """
    name = "テーマ/市場資金"
    if target_sector is None:
        return FutureMfeScoreItem(
            name=name,
            max_points=10,
            points=5.0,
            evidence=["対象銘柄の業種が特定できないため中立基準点"],
            confidence="低(JPX業種マスタでの名寄せに失敗)",
        )

    peer_count = sum(1 for sector in peer_sectors if sector == target_sector)

    if peer_count >= 3:
        points = 8.0
        reason = f"上位ランキングに同業種「{target_sector}」の銘柄が他に{peer_count}社→セクター全体への資金流入の可能性"
    elif peer_count >= 1:
        points = 4.0
        reason = f"上位ランキングに同業種「{target_sector}」の銘柄は他に{peer_count}社のみ"
    else:
        points = 5.0
        reason = f"上位ランキングに同業種「{target_sector}」の銘柄は対象銘柄のみ"

    return FutureMfeScoreItem(
        name=name,
        max_points=10,
        points=points,
        evidence=[reason],
        confidence="低(業種集中度のみを見る簡易ロジック。個別テーマは未対応)",
    )


# ---------------------------------------------------------------------------
# 【3.3タイプ分類】【11.MODEL/EXECUTABLE WINNER】
#
# TODO: 以下は原文に厳密な数値式がないため、A/B/C分類・WINNER選定の自動化は
# 実データでの検証を経てから実装する。
# ---------------------------------------------------------------------------


def score_future_mfe(candidate: WeeklyCandidate) -> FutureMfeScore:
    base = empty_future_mfe_score()
    computed = {
        item.name: item
        for item in (
            score_ranking_progression(candidate.rank_history),
            score_momentum_acceleration(candidate.rank_history),
            score_overheat_risk(candidate.rank_history),
            score_stop_high_lock_proxy(candidate.rank_history),
            score_catalyst_strength(candidate.disclosures),
            score_theme_market_flow(candidate.sector, candidate.top20_sector_peers),
        )
    }
    items = [computed.get(item.name, item) for item in base.items]

    return FutureMfeScore(
        items=items,
        max_score=base.max_score,
        notes=[
            (
                "「ランキング推移」「上昇率加速度」「過熱/下落リスク」の3項目(計45点)は"
                "2026-09-07/08の実データから導いた配点式で算出。"
            ),
            (
                "「チャート/出来高」はストップ高固定のプロキシ検出(score_stop_high_lock_proxy)"
                "のみで暫定算出。絶対株価データが未取得のため正式な制限値幅判定ではない。"
            ),
            (
                "「CATALYST」はTDnet開示タイトルのキーワード判定(score_catalyst_strength)で算出。"
                "皮肉な言い回し等は誤判定しうる簡易ロジック。"
            ),
            (
                "「テーマ/市場資金」はJPX 33業種区分による業種集中度スコア(score_theme_market_flow)"
                "で算出。個別テーマ(AI関連等)はみんかぶ・株探の利用規約上の理由により未対応。"
            ),
            (
                "残り1項目(過去統計適合度)は複数週の統計データが未取得のため未算出(points=None)。"
            ),
        ],
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
