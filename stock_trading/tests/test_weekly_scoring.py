"""2026-09-07(月)/09-08(火)の実データ(鉄人戦ボード50銘柄・6時点)に基づく回帰テスト。

継続成功銘柄(誠建設工業・オンコリスバイオ)と、前引け後に急落した銘柄
(テラドローン・エプリー)を、score_future_mfe() が正しく分離できることを固定する。
"""

from datetime import date

from masa_trade.logic.weekly.engine import (
    score_future_mfe,
    score_momentum_acceleration,
    score_ranking_progression,
    score_stop_high_lock_proxy,
)
from masa_trade.logic.weekly.schema import Checkpoint, RankEntry, RankHistory, WeeklyCandidate

MON = date(2026, 9, 7)
TUE = date(2026, 9, 8)


def _history(name: str, moments: list[tuple[date, Checkpoint, int, float | None]]) -> RankHistory:
    entries = {
        (d, cp): RankEntry(name=name, rank=rank, checkpoint=cp, pct_change=pct)
        for d, cp, rank, pct in moments
    }
    return RankHistory(name=name, entries_by_moment=entries)


SEISETSU = _history(
    "誠建設工業",
    [
        (MON, Checkpoint.OPEN, 10, None),
        (MON, Checkpoint.MID_MORNING, 1, 18.5),
        (MON, Checkpoint.MIDDAY_CLOSE, 1, 18.5),
        (MON, Checkpoint.CLOSE, 1, 18.5),
        (TUE, Checkpoint.OPEN, 2, 18.5),
        (TUE, Checkpoint.MIDDAY_CLOSE, 2, 18.5),
    ],
)

ONCOLYS = _history(
    "オンコリスバイオ",
    [
        (MON, Checkpoint.OPEN, 43, None),
        (MON, Checkpoint.MID_MORNING, 2, 12.7),
        (MON, Checkpoint.MIDDAY_CLOSE, 2, 13.6),
        (MON, Checkpoint.CLOSE, 2, 9.4),
        (TUE, Checkpoint.OPEN, 1, 22.4),
        (TUE, Checkpoint.MIDDAY_CLOSE, 1, 22.0),
    ],
)

TERADRONE = _history(
    "テラドローン",
    [
        (MON, Checkpoint.OPEN, 16, None),
        (MON, Checkpoint.MID_MORNING, 3, 12.3),
        (MON, Checkpoint.MIDDAY_CLOSE, 3, 12.3),
        (MON, Checkpoint.CLOSE, 41, -2.4),
        (TUE, Checkpoint.OPEN, 13, 2.3),
        (TUE, Checkpoint.MIDDAY_CLOSE, 26, 0.6),
    ],
)

EPLI = _history(
    "エプリー",
    [
        (MON, Checkpoint.OPEN, 21, None),
        (MON, Checkpoint.MID_MORNING, 4, 6.5),
        (MON, Checkpoint.MIDDAY_CLOSE, 4, 5.1),
        (MON, Checkpoint.CLOSE, 46, -4.7),
        (TUE, Checkpoint.OPEN, 4, 8.4),
        (TUE, Checkpoint.MIDDAY_CLOSE, 31, -0.4),
    ],
)

# 古林紙工: 誠建設工業と同様に上昇率が5時点とも0.3%で完全凍結しているが、
# 順位はずっと24〜30位台(50銘柄中上位30%=15位以内に入らない)。
# 「ストップ高で強い」のか「単に出来高が枯れて動いていないだけ」なのかを
# 順位で見分けられるかの確認に使う。
KOBAYASHI_SHIKO = _history(
    "古林紙工",
    [
        (MON, Checkpoint.OPEN, 40, None),
        (MON, Checkpoint.MID_MORNING, 27, 0.3),
        (MON, Checkpoint.MIDDAY_CLOSE, 27, 0.3),
        (MON, Checkpoint.CLOSE, 24, 0.3),
        (TUE, Checkpoint.OPEN, 30, 0.3),
        (TUE, Checkpoint.MIDDAY_CLOSE, 29, 0.3),
    ],
)


def _score_by_name(score, name: str) -> float:
    return next(item.points for item in score.items if item.name == name)


def test_continuation_winners_score_near_full_on_implemented_items():
    for history in (SEISETSU, ONCOLYS):
        candidate = WeeklyCandidate(name=history.name, rank_history=history)
        score = score_future_mfe(candidate)
        assert _score_by_name(score, "ランキング推移") == 20
        assert _score_by_name(score, "上昇率加速度") >= 12
        assert _score_by_name(score, "過熱/下落リスク") == 10


def test_reversal_stocks_score_low_on_ranking_and_overheat():
    # 「上昇率加速度」は直近時点の符号を見るため、火曜前引けまでにプラス圏へ
    # 戻したテラドローンは加点され得る(8点=符号のみ。下落幅は0点のまま)。
    # ランキング推移(前引け後の崩落で大きく減点)と過熱/下落リスク(転落+反落パターン
    # を検知)の2項目は、どちらの銘柄も低いままになる。
    for history in (TERADRONE, EPLI):
        candidate = WeeklyCandidate(name=history.name, rank_history=history)
        score = score_future_mfe(candidate)
        assert _score_by_name(score, "ランキング推移") <= 10
        assert _score_by_name(score, "過熱/下落リスク") == 0

    teradrone_score = score_future_mfe(WeeklyCandidate(name=TERADRONE.name, rank_history=TERADRONE))
    epli_score = score_future_mfe(WeeklyCandidate(name=EPLI.name, rank_history=EPLI))
    # テラドローンは火曜前引け時点で上昇率+0.6%(符号スコアのみ加点)、
    # エプリーは-0.4%のまま(符号スコアも0点)。
    assert _score_by_name(teradrone_score, "上昇率加速度") == 8
    assert _score_by_name(epli_score, "上昇率加速度") == 0


def test_unimplemented_items_stay_unset():
    candidate = WeeklyCandidate(name=SEISETSU.name, rank_history=SEISETSU)
    score = score_future_mfe(candidate)
    for name in ("CATALYST", "テーマ/市場資金", "過去統計適合度"):
        assert _score_by_name(score, name) is None
    assert score.total is None


def test_stop_high_lock_proxy_flags_frozen_top_rank_stock():
    # 誠建設工業: 5時点連続で上昇率18.5%が凍結、かつ直近順位2位(上位15位以内)
    # → ストップ高で売買不成立の可能性として満点15点。
    item = score_stop_high_lock_proxy(SEISETSU)
    assert item.points == 15


def test_stop_high_lock_proxy_downgrades_frozen_low_rank_stock():
    # 古林紙工: 同様に凍結しているが、順位は24〜30位台(上位15位以内に入らない)
    # → 出来高枯渇の疑いとして3点にとどまる。
    item = score_stop_high_lock_proxy(KOBAYASHI_SHIKO)
    assert item.points == 3


def test_stop_high_lock_proxy_scores_zero_when_not_frozen():
    for history in (ONCOLYS, TERADRONE, EPLI):
        item = score_stop_high_lock_proxy(history)
        assert item.points == 0


def test_stop_high_lock_proxy_uses_trailing_streak_only():
    """凍結が過去にあっても直近が動いていれば加点しない(直近状態のみを見る)。"""
    unfroze_recently = _history(
        "テスト銘柄",
        [
            (MON, Checkpoint.MID_MORNING, 5, 10.0),
            (MON, Checkpoint.MIDDAY_CLOSE, 5, 10.0),
            (MON, Checkpoint.CLOSE, 5, 10.0),
            (TUE, Checkpoint.OPEN, 5, 12.0),
        ],
    )
    item = score_stop_high_lock_proxy(unfroze_recently)
    assert item.points == 0


def test_score_future_mfe_without_rank_history_stays_unset():
    candidate = WeeklyCandidate(name="データなし銘柄")
    score = score_future_mfe(candidate)
    assert all(item.points is None for item in score.items)


def _history_up_to_monday_midday_close(history: RankHistory) -> RankHistory:
    """月曜前引けまでのデータだけに絞ったRankHistory(その時点で実際に使えた情報のみ)。"""
    trimmed = {
        (d, cp): entry
        for (d, cp), entry in history.entries_by_moment.items()
        if d == MON and cp in (Checkpoint.OPEN, Checkpoint.MID_MORNING, Checkpoint.MIDDAY_CLOSE)
    }
    return RankHistory(name=history.name, entries_by_moment=trimmed)


def test_ranking_and_momentum_cannot_distinguish_reversal_risk_at_monday_midday_close():
    """LOOK-AHEAD BIAS禁止(v2.1 §26)の確認: 月曜前引け時点で入手可能なデータだけでは、
    その後急落するテラドローンを、継続に成功する誠建設工業から区別できない
    (両方とも前引けまでは順位・上昇率とも「安定」に見えていた)。

    このため「ランキング推移」「上昇率加速度」「過熱/下落リスク」の3項目は、
    月曜前引け一発のFUTURE MFE SCOREとしてではなく、新しいチェックポイントが
    来るたびに再評価するHOLDスコア的な用途で使うべき、という設計上の結論を裏付ける。
    """
    seisetsu_at_midday = _history_up_to_monday_midday_close(SEISETSU)
    teradrone_at_midday = _history_up_to_monday_midday_close(TERADRONE)

    seisetsu_rank_score = score_ranking_progression(seisetsu_at_midday)
    teradrone_rank_score = score_ranking_progression(teradrone_at_midday)
    assert seisetsu_rank_score.points == teradrone_rank_score.points == 20

    seisetsu_momentum = score_momentum_acceleration(seisetsu_at_midday)
    teradrone_momentum = score_momentum_acceleration(teradrone_at_midday)
    assert seisetsu_momentum.points == teradrone_momentum.points == 15
