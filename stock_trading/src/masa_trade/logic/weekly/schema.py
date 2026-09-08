"""まー式・鉄人戦週間ランキング戦略 v2.1 向けデータスキーマ。

v2.1はv1.3・v2.19を補完する「週間」戦略であり、性質が大きく異なるため
v1.3(logic/schema.py)とは独立したモジュールにしている。

    - 周期: 月曜日の3時点(始まり値・10:30・前引け)を起点に週単位で回る
      (v1.3は都度精査、v2.19は日次)。
    - 入力: ユーザーから送られる「週間値幅ランキング画像」(全50銘柄)。
      現時点ではこのセッション(Claude)が画像を読んで構造化データに変換し、
      本スキーマに詰める運用とする(自動OCR/専用パーサーは今回のスコープ外)。
    - 状態: 月曜に決めたMODEL WINNER/EXECUTABLE WINNERは週内固定し、
      火〜金のMFE/MAE追跡、金曜のWEEKLY AUDIT、10→20→30→50回の統計蓄積という
      「週をまたぐ状態」を持つ(v1.3・v2.19はステートレス)。
      永続化は logic/weekly/store.py で行うローカルJSONLファイルを使う。

v1.3との関係(ユーザー指示に基づく): 今回はv2.1を完全に独立させる。
v2.1のEXECUTABLE WINNERをv1.3のjudge()(6ゲート)に通す連携は作らない。
必要になれば後日、EXECUTABLE WINNER→JudgeInput変換ロジックを別途追加する。

配点・数値閾値のうち原文に明記されているものだけをそのまま実装し、
明記されていないもの(A/B/C分類の厳密な境界、MODEL/EXECUTABLE WINNERの
選定式など)は `logic/weekly/engine.py` 側でTODOのプレースホルダーとする。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from masa_trade.logic.common.order import MarketRegime, OrderProposal

__all__ = [
    "FUTURE_MFE_SCORE_ITEM_DEFINITIONS",
    "CatalystInfo",
    "CatalystTiming",
    "Checkpoint",
    "ContinuationOverrideFlag",
    "ContinuationTrapFlag",
    "EntryMethod",
    "ErrorClass",
    "ExitReason",
    "FutureMfeScore",
    "FutureMfeScoreItem",
    "LostWinnerJudgment",
    "MarketRegime",
    "MarketRegimeInput",
    "MfeMaeResult",
    "PeakOutAssessment",
    "PeakOutFlag",
    "RankEntry",
    "RankHistory",
    "RankingSnapshot",
    "StockType",
    "WeeklyAudit",
    "WeeklyCandidate",
    "WeeklyEntryPlan",
    "WeeklyRecord",
    "WinnerSelection",
    "empty_future_mfe_score",
]


# ---------------------------------------------------------------------------
# 【29.画像受領時の自動動作】のタイミング区分。
#
# 曜日は含めない(時間帯のみ)。実際にどの日のスナップショットかは
# RankingSnapshot.captured_at の日付側で区別する。これにより月曜だけでなく
# 火〜金の同じ時間帯のスナップショットも同じCheckpointで表せる。
# ---------------------------------------------------------------------------


class Checkpoint(str, Enum):
    OPEN = "始まり値"
    MID_MORNING = "寄り後(10:30目安)"
    MIDDAY_CLOSE = "前引け"
    AFTERNOON = "14:00"
    CLOSE = "終値"


# RankHistory.rank_sequence等を時系列で並べるための順序。
_CHECKPOINT_ORDER: dict[Checkpoint, int] = {
    Checkpoint.OPEN: 0,
    Checkpoint.MID_MORNING: 1,
    Checkpoint.MIDDAY_CLOSE: 2,
    Checkpoint.AFTERNOON: 3,
    Checkpoint.CLOSE: 4,
}


# ---------------------------------------------------------------------------
# 【3.3タイプ分類】
# ---------------------------------------------------------------------------


class StockType(str, Enum):
    A_CONTINUATION = "A:CONTINUATION"
    B_MAIN_EARLY = "B:MAIN EARLY"
    C_CATALYST_EARLY = "C:CATALYST EARLY"


# ---------------------------------------------------------------------------
# 【8.CATALYST TIMING】
# ---------------------------------------------------------------------------


class CatalystTiming(str, Enum):
    IMMEDIATE = "IMMEDIATE"  # 当日〜翌営業日
    SHORT = "SHORT"  # 2〜5営業日
    MEDIUM = "MEDIUM"  # 1〜4週間
    LONG = "LONG"  # それ以上


# ---------------------------------------------------------------------------
# 【12.ENTRY】3系統
# ---------------------------------------------------------------------------


class EntryMethod(str, Enum):
    PULLBACK = "PULLBACK"
    BREAKOUT = "BREAKOUT"
    BREAKOUT_RETEST = "BREAKOUT-RETEST"


# ---------------------------------------------------------------------------
# 【4.CONTINUATION OVERRIDE】の7項目。3項目以上で過熱ペナルティを弱める。
# ---------------------------------------------------------------------------


class ContinuationOverrideFlag(str, Enum):
    RANK_MAINTAINED_OR_UP = "順位維持/上昇"
    MOMENTUM_ACCELERATING = "上昇率加速"
    VOLUME_EXPANDING = "出来高拡大"
    STRONG_MATERIAL_THEME = "強い材料/テーマ"
    NEW_HIGH = "高値更新"
    RELATIVE_STRENGTH_UP = "相対強度上昇"
    HOLDS_ON_DIPS = "押しても崩れない"


# ---------------------------------------------------------------------------
# 【5.CONTINUATION TRAP CONTROL】偽Continuationを疑う10項目。
# ---------------------------------------------------------------------------


class ContinuationTrapFlag(str, Enum):
    VOLUME_PEAK_OUT = "出来高ピークアウト"
    GAP_UP_FAILURE = "大幅GU後の失速"
    LONG_UPPER_WICK = "長い上ヒゲ"
    VWAP_LARGE_DEVIATION = "VWAP大幅乖離"
    NEW_HIGH_FAILURE = "高値更新失敗"
    MATERIAL_EXHAUSTED = "材料出尽くし"
    RANK_DECLINE = "ランキング順位低下"
    MOMENTUM_DECELERATION = "上昇率減速"
    THIN_ORDER_BOOK = "板が薄すぎる"
    POOR_RISK_REWARD = "R/R不足"


# ---------------------------------------------------------------------------
# 【17.MFE CAPTURE MODE】PEAK-OUT WARNINGの8項目。
# ---------------------------------------------------------------------------


class PeakOutFlag(str, Enum):
    RANK_SHARP_DECLINE = "ランキング急低下"
    MOMENTUM_SHARP_DECLINE = "上昇率急減"
    LONG_UPPER_WICK = "長い上ヒゲ"
    VOLUME_SPIKE_THEN_DROP = "出来高急増後の反落"
    VWAP_BREAK = "VWAP割れ"
    HIGHER_HIGH_FAILURE = "Higher High失敗"
    LOWER_HIGH = "Lower High"
    SUPPORT_BREAK = "支持線割れ"


# ---------------------------------------------------------------------------
# 【19.EXIT】候補11項目。複数成立でEXIT優先。
# ---------------------------------------------------------------------------


class ExitReason(str, Enum):
    RANK_SHARP_DECLINE = "①ランキング急低下"
    MOMENTUM_PEAK_OUT = "②上昇率ピークアウト"
    VWAP_CLEAR_BREAK = "③VWAP明確割れ"
    SUPPORT_BREAK = "④支持線割れ"
    VOLUME_BACKED_PULLBACK = "⑤出来高付き反落"
    NEW_HIGH_FAILURE = "⑥高値更新失敗"
    LOWER_HIGH = "⑦Lower High"
    MATERIAL_EXHAUSTED = "⑧材料出尽くし"
    THEME_FADING = "⑨テーマ失速"
    CATALYST_PASSED = "⑩CATALYST通過"
    HIGHER_EV_ALTERNATIVE_APPEARED = "⑪より高EV銘柄出現"


# ---------------------------------------------------------------------------
# 【23.エラー分類】【24.LOST-WINNER AUDIT】
# ---------------------------------------------------------------------------


class ErrorClass(str, Enum):
    SELECTION_ERROR = "SELECTION ERROR"
    ENTRY_ERROR = "ENTRY ERROR"
    EXIT_ERROR = "EXIT ERROR"
    CAPITAL_CONSTRAINT = "CAPITAL CONSTRAINT"
    LIQUIDITY_ERROR = "LIQUIDITY ERROR"
    CATALYST_MISS = "CATALYST MISS"
    CONTINUATION_MISS = "CONTINUATION MISS"
    RE_ENTRY_MISS = "RE-ENTRY MISS"
    UNAVOIDABLE = "UNAVOIDABLE"


class LostWinnerJudgment(str, Enum):
    TRUE_LOST_WINNER = "TRUE LOST-WINNER"
    VALID_PASS = "VALID PASS"
    GOOD_PASS = "GOOD PASS"


# ---------------------------------------------------------------------------
# 【1.使用する画像】【2.全50銘柄ZERO-BASE DISCOVERY】【6.RANK VELOCITY】
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RankEntry:
    """ランキング画像1銘柄・1時点分の読み取り結果。"""

    name: str
    rank: int
    symbol: str | None = None  # 画像上は銘柄名のみでコードが読めないことがある
    price: float | None = None
    pct_change: float | None = None
    volume: float | None = None
    checkpoint: Checkpoint = Checkpoint.OPEN
    captured_at: datetime | None = None


@dataclass(frozen=True)
class RankingSnapshot:
    """1時点分の全50銘柄ランキング。"""

    checkpoint: Checkpoint
    captured_at: datetime
    entries: list[RankEntry] = field(default_factory=list)


@dataclass(frozen=True)
class RankHistory:
    """1銘柄について、複数時点(日付×Checkpoint)のRankEntryをまとめたもの(RANK VELOCITY計算用)。"""

    name: str
    symbol: str | None = None
    entries_by_moment: dict[tuple[date, Checkpoint], RankEntry] = field(default_factory=dict)

    def _ordered_moments(self) -> list[tuple[date, Checkpoint]]:
        return sorted(self.entries_by_moment, key=lambda moment: (moment[0], _CHECKPOINT_ORDER[moment[1]]))

    @property
    def rank_sequence(self) -> list[tuple[date, Checkpoint, int]]:
        return [(d, cp, self.entries_by_moment[(d, cp)].rank) for d, cp in self._ordered_moments()]

    @property
    def pct_change_sequence(self) -> list[tuple[date, Checkpoint, float | None]]:
        return [
            (d, cp, self.entries_by_moment[(d, cp)].pct_change) for d, cp in self._ordered_moments()
        ]


# ---------------------------------------------------------------------------
# 【7.CATALYST RADAR】【8.CATALYST TIMING】【9.GLOBAL INTELLIGENCE】
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CatalystInfo:
    description: str | None = None
    category: str | None = None  # 決算/提携/採択/承認/政策 など
    timing: CatalystTiming | None = None
    source: str | None = None
    # FACT/INFERENCE/SPECULATIONの分離(未公表IRの予測はSPECULATION扱い)
    is_speculative: bool = False
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 【10.FUTURE MFE SCORE】原文どおりの項目名・配点。
# ---------------------------------------------------------------------------

FUTURE_MFE_SCORE_ITEM_DEFINITIONS: tuple[tuple[str, float], ...] = (
    ("ランキング推移", 20),
    ("上昇率加速度", 15),
    ("チャート/出来高", 15),
    ("CATALYST", 20),
    ("テーマ/市場資金", 10),
    ("過熱/下落リスク", 10),
    ("過去統計適合度", 10),
)


@dataclass(frozen=True)
class FutureMfeScoreItem:
    name: str
    max_points: float
    points: float | None = None  # 未算出(配点式未確定・データ不足)は None
    evidence: list[str] = field(default_factory=list)
    confidence: str | None = None


@dataclass(frozen=True)
class FutureMfeScore:
    items: list[FutureMfeScoreItem]
    max_score: float = 100.0
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> float | None:
        points = [item.points for item in self.items]
        if any(p is None for p in points):
            return None
        return sum(points)

    @property
    def grade(self) -> str | None:
        """S(85-100)/A(75-84)/B(65-74)/C(64以下)。totalが出ていなければNone。"""
        total = self.total
        if total is None:
            return None
        if total >= 85:
            return "S"
        if total >= 75:
            return "A"
        if total >= 65:
            return "B"
        return "C"


def empty_future_mfe_score() -> FutureMfeScore:
    """FUTURE MFE SCORE(100点)の空スコア(全項目 points=None)を生成する。"""
    items = [
        FutureMfeScoreItem(name=name, max_points=max_points)
        for name, max_points in FUTURE_MFE_SCORE_ITEM_DEFINITIONS
    ]
    return FutureMfeScore(items=items)


# ---------------------------------------------------------------------------
# 【11.MODEL WINNER / EXECUTABLE WINNER】【12〜14.ENTRY】
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeeklyEntryPlan:
    """ENTRY/STOP/TARGET/100株必要資金/最大損失/RRの計画(【12】〜【14】)。"""

    method: EntryMethod | None = None
    order: OrderProposal = field(default_factory=OrderProposal)


@dataclass(frozen=True)
class WeeklyCandidate:
    """1銘柄分の週間精査結果(タイプ分類・順位推移・材料・スコア・ENTRY計画)。"""

    name: str
    symbol: str | None = None
    stock_type: StockType | None = None
    rank_history: RankHistory | None = None
    catalyst: CatalystInfo = field(default_factory=CatalystInfo)
    continuation_override_flags: list[ContinuationOverrideFlag] = field(default_factory=list)
    continuation_trap_flags: list[ContinuationTrapFlag] = field(default_factory=list)
    score: FutureMfeScore = field(default_factory=empty_future_mfe_score)
    entry_plan: WeeklyEntryPlan = field(default_factory=WeeklyEntryPlan)


@dataclass(frozen=True)
class WinnerSelection:
    """月曜前引け時点で確定させるMODEL WINNER/EXECUTABLE WINNER/次点2枠。"""

    model_winner: WeeklyCandidate | None = None
    executable_winner: WeeklyCandidate | None = None
    runner_up_1: WeeklyCandidate | None = None
    runner_up_2: WeeklyCandidate | None = None

    @property
    def is_unified(self) -> bool:
        """MODEL WINNERとEXECUTABLE WINNERが同一銘柄かどうか。"""
        if self.model_winner is None or self.executable_winner is None:
            return False
        return (self.model_winner.symbol, self.model_winner.name) == (
            self.executable_winner.symbol,
            self.executable_winner.name,
        )


# ---------------------------------------------------------------------------
# 【15.MARKET REGIME】DEFENSE判定は原文に数値閾値が明記されている。
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarketRegimeInput:
    nikkei_change_pct: float | None = None
    topix_change_pct: float | None = None
    prime_decliner_pct: float | None = None  # プライム市場 値下がり銘柄比率
    growth_decliner_pct: float | None = None  # グロース市場 値下がり銘柄比率


# ---------------------------------------------------------------------------
# 【17.MFE CAPTURE MODE】PEAK-OUT WARNING
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PeakOutAssessment:
    flags: list[PeakOutFlag] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 【20.MFE/MAE】【21.MFE CAPTURE RATE】
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MfeMaeResult:
    """5営業日MFE/MAE。基準価格は月曜前引け値。"""

    baseline_price: float
    highest_price_within_5d: float | None = None
    lowest_price_within_5d: float | None = None

    @property
    def mfe_pct(self) -> float | None:
        if self.highest_price_within_5d is None or self.baseline_price == 0:
            return None
        return (self.highest_price_within_5d / self.baseline_price - 1) * 100

    @property
    def mae_pct(self) -> float | None:
        if self.lowest_price_within_5d is None or self.baseline_price == 0:
            return None
        return (self.lowest_price_within_5d / self.baseline_price - 1) * 100


# ---------------------------------------------------------------------------
# 【22.週間記録】【27.週末AUDIT】
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeeklyRecord:
    """1銘柄・1週分の記録(MODEL WINNER/EXECUTABLE WINNER/次点いずれか)。"""

    week_start_date: date
    role: str  # "MODEL WINNER" / "EXECUTABLE WINNER" / "次点1" / "次点2"
    name: str
    symbol: str | None = None

    monday_midday_rank: int | None = None
    monday_pct_change: float | None = None
    monday_price: float | None = None
    stock_type: StockType | None = None
    score: FutureMfeScore = field(default_factory=empty_future_mfe_score)

    entry_plan: WeeklyEntryPlan = field(default_factory=WeeklyEntryPlan)
    actual_entry_price: float | None = None

    monday_close: float | None = None
    tuesday_high: float | None = None
    wednesday_high: float | None = None
    thursday_high: float | None = None
    friday_high: float | None = None

    mfe_mae: MfeMaeResult | None = None
    ideal_exit_price: float | None = None
    actual_exit_price: float | None = None
    realized_return_pct: float | None = None
    realized_r: float | None = None
    capture_rate_pct: float | None = None

    error_class: ErrorClass | None = None
    lost_winner_judgment: LostWinnerJudgment | None = None

    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WeeklyAudit:
    """金曜終了時点の週次監査結果(【27】)。"""

    week_start_date: date
    actual_max_mfe_name: str | None = None
    was_selectable_at_monday: bool | None = None
    model_winner_rank_by_mfe: int | None = None
    notes: list[str] = field(default_factory=list)
    records: list[WeeklyRecord] = field(default_factory=list)
