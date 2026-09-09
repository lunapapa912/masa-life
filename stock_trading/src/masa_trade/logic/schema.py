"""まー式 統合運用プロンプト v1.3(まー式AI投資会社)向けデータスキーマ。

まー式 v2.19(ZERO-BASE DISCOVERY / ANCHORING CONTROL / BARON DISCOVERY LAYER /
EXECUTION CONSTRAINT LAYER / EXECUTABLE EV PRINCIPLE)による日次スクリーニングには
一切手を入れない。v2.19は、既存の保有・WATCH・過去銘柄を見ずに全市場から
NEW DISCOVERY(新規候補)を抽出・仮ランキングし、そのあとで初めて
EXISTING WATCH(既存WATCH・保有・過去相談銘柄)を合流させて FINAL RANKING を作る。
候補は100点満点(材料・カタリスト25 / 需給20 / チャート・ENTRY位置20 /
BARON SCORE15 / 新規性・材料鮮度10 / EXECUTION適性10)でスコアリングされ、
「①今夜PTSで入れる ②事前注文なら入れる ③12:30以降から狙える ④WATCHのみ
⑤時間制約により除外」の5分類から MAIN ACTION(必要なら SUB ACTION も)を決定する。

このファイルは、v2.19のFINAL RANKINGで選ばれた候補(=watchlist)を受け取った
あとの「深掘り精査」フェーズのための入出力データ構造だけを定義する。

【スコア】【6ゲート】【CIO決裁書を冒頭に表示】の3セクションは、
ユーザーから提供された v1.3 原文の項目名・配点をそのまま反映している。
他のセクション(材料進捗・賞味期限・将来イベント・評価と逆算・期待値・執行・
検証・禁止 など)は今回のスコープ外で、必要になった時点で追加する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from masa_trade.logic.common.order import OrderProposal, PriceTiers  # noqa: F401 (re-exported)

if TYPE_CHECKING:
    import pandas as pd


class ReviewMode(str, Enum):
    """v1.3の3モード。"""

    FULL_MARKET = "A"  # モードA: 全市場発掘
    COMPARE = "B"  # モードB: 候補比較
    DEEP_DIVE = "C"  # モードC: 個別精査


# ---------------------------------------------------------------------------
# 【6ゲート】
# G1 会計・監査・上場維持 / G2 大規模希薄化 / G3 材料の実在 /
# G4 売上・利益への接続 / G5 株価への織込み / G6 今後1〜3営業日の短期カタリスト
# 各PASS/CAUTION/FAIL/UNKNOWN。重大FAILは点数で相殺せず評価を下げる。
# ---------------------------------------------------------------------------


class Gate(str, Enum):
    G1_ACCOUNTING = "G1 会計・監査・上場維持"
    G2_DILUTION = "G2 大規模希薄化"
    G3_MATERIAL_EXISTENCE = "G3 材料の実在"
    G4_EARNINGS_LINKAGE = "G4 売上・利益への接続"
    G5_PRICED_IN = "G5 株価への織込み"
    G6_SHORT_TERM_CATALYST = "G6 今後1〜3営業日の短期カタリスト"


class GateStatus(str, Enum):
    PASS = "PASS"
    CAUTION = "CAUTION"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class GateResult:
    gate: Gate
    status: GateStatus
    reason: str
    evidence: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    # 「重大FAIL」かどうか。重大FAILは点数で相殺せず評価そのものを下げる特別扱いにする。
    critical: bool = False


# ---------------------------------------------------------------------------
# 【スコア】
# 企業価値100 / 短期ENTRY100 / 実行可能性100。各項目に配点が定義されている。
# 「スコアには根拠と確信度を付す」ため、ScoreItemResult は evidence / confidence を持つ。
# ---------------------------------------------------------------------------


class ScoreName(str, Enum):
    CORPORATE_VALUE = "企業価値"
    SHORT_TERM_ENTRY = "短期ENTRY"
    FEASIBILITY = "実行可能性"


@dataclass(frozen=True)
class ScoreItemResult:
    """スコアを構成する個別項目。1項目=v1.3原文の1配点項目に対応する。"""

    name: str
    max_points: float
    points: float | None = None  # 未算出(データ不足・未実装)は None
    evidence: list[str] = field(default_factory=list)
    confidence: str | None = None  # 例: "高" / "中" / "低"
    note: str | None = None


@dataclass(frozen=True)
class ScoreResult:
    name: ScoreName
    items: list[ScoreItemResult]
    max_score: float = 100.0
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> float | None:
        """全項目にpointsが入っていれば合計、1つでも未算出ならNone。"""
        points = [item.points for item in self.items]
        if any(p is None for p in points):
            return None
        return sum(points)


# v1.3原文の配点定義そのまま。ここを変えるとスコアの意味がv1.3からズレるので注意。
CORPORATE_VALUE_ITEM_DEFINITIONS: tuple[tuple[str, float], ...] = (
    ("成長", 15),
    ("技術", 10),
    ("将来材料", 15),
    ("業績KPI", 10),
    ("評価", 10),
    ("国策市場", 10),
    ("財務", 5),
    ("経営", 5),
    ("需給", 5),
    ("株価位置", 5),
    ("実現確率", 5),
    ("安全性", 5),
)

SHORT_TERM_ENTRY_ITEM_DEFINITIONS: tuple[tuple[str, float], ...] = (
    ("鮮度", 15),
    ("強度", 15),
    ("出来高・相対強度", 15),
    ("チャート", 15),
    ("需給", 10),
    ("上値", 10),
    ("損切明確性", 10),
    ("RR", 10),
)

FEASIBILITY_ITEM_DEFINITIONS: tuple[tuple[str, float], ...] = (
    ("12:30適合", 25),
    ("指値逆指値", 20),
    ("約定", 15),
    ("予算単位", 15),
    ("監視不要", 15),
    ("ギャップ許容", 10),
)


def _build_score(name: ScoreName, definitions: tuple[tuple[str, float], ...]) -> ScoreResult:
    items = [ScoreItemResult(name=item_name, max_points=max_points) for item_name, max_points in definitions]
    return ScoreResult(name=name, items=items)


def empty_corporate_value_score() -> ScoreResult:
    """企業価値100点の空スコア(全項目 points=None)を生成する。"""
    return _build_score(ScoreName.CORPORATE_VALUE, CORPORATE_VALUE_ITEM_DEFINITIONS)


def empty_entry_score() -> ScoreResult:
    """短期ENTRY100点の空スコアを生成する。"""
    return _build_score(ScoreName.SHORT_TERM_ENTRY, SHORT_TERM_ENTRY_ITEM_DEFINITIONS)


def empty_feasibility_score() -> ScoreResult:
    """実行可能性100点の空スコアを生成する。"""
    return _build_score(ScoreName.FEASIBILITY, FEASIBILITY_ITEM_DEFINITIONS)


# ---------------------------------------------------------------------------
# 【判定】ENTRY / TEST ENTRY / WAIT / WATCH / AVOID / EXIT
# CIO決裁書の「売買判定」フィールドに使う。
# ---------------------------------------------------------------------------


class TradeDecision(str, Enum):
    ENTRY = "ENTRY"
    TEST_ENTRY = "TEST ENTRY"
    WAIT = "WAIT"
    WATCH = "WATCH"
    AVOID = "AVOID"
    EXIT = "EXIT"


class CorporateJudgment(str, Enum):
    """企業判定(CIO決裁書の項目)。"""

    EXCELLENT = "優良"
    STANDARD = "標準"
    FRAGILE = "脆弱"
    UNKNOWN = "不明"


# ---------------------------------------------------------------------------
# 入力データ: 6ゲート判定・3スコア算出に必要な材料をカテゴリごとに分割する。
# 未取得の項目は None のままにしておき、ゲート側で UNKNOWN として扱う。
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MaterialInfo:
    """G3 材料の実在 用: 株価材料となるニュース・IRそのものの実在性・一次情報性。"""

    headline: str | None = None
    source: str | None = None  # 適時開示 / 自社IR / 官公庁発表 / 報道 など
    source_url: str | None = None
    published_at: datetime | None = None
    category: str | None = None  # 決算 / 業務提携 / 増資 / 新製品 / 規制対応 など
    is_primary_source: bool | None = None  # 一次情報(適時開示・IR)かどうか
    verified: bool | None = None  # 一次情報での裏取りが取れているか
    verification_note: str | None = None


@dataclass(frozen=True)
class SupplyDemandData:
    """需給データ: G2大規模希薄化・実行可能性スコア(出来高で実際に取れる玉か)に使う。"""

    shares_outstanding: float | None = None
    float_shares: float | None = None
    market_cap: float | None = None
    avg_volume_20d: float | None = None
    avg_volume_60d: float | None = None
    latest_volume: float | None = None
    turnover_value_latest: float | None = None  # 売買代金(概算約定可能額の目安)
    margin_buy_balance: float | None = None  # 信用買い残
    margin_sell_balance: float | None = None  # 信用売り残(空売り)
    short_interest_ratio: float | None = None  # 信用倍率
    foreign_ownership_pct: float | None = None
    major_shareholder_changes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChartData:
    """チャートデータ: 短期ENTRYスコアに使う値動き・テクニカル指標。"""

    ohlcv: pd.DataFrame | None = None
    sma_short: float | None = None
    sma_medium: float | None = None
    sma_long: float | None = None
    rsi: float | None = None
    volume_ratio: float | None = None
    vwap: float | None = None
    trend: str | None = None  # "up" / "down" / "range"
    support_price: float | None = None
    resistance_price: float | None = None
    breakout: bool | None = None
    gap_up_pct: float | None = None


@dataclass(frozen=True)
class AccountingData:
    """G1 会計・監査・上場維持 用: 粉飾・継続前提・監査意見など会計的な危険信号の有無。"""

    latest_fiscal_period: str | None = None
    going_concern_doubt: bool | None = None
    auditor_opinion: str | None = None  # 適正 / 限定付き適正 / 不適正 / 意見不表明
    internal_control_issue: bool | None = None
    restatement_flag: bool | None = None  # 過年度決算の訂正歴
    delisting_criteria_risk: bool | None = None  # 上場維持基準抵触リスク
    auditor_changed_recently: bool | None = None
    earnings_delay_flag: bool | None = None  # 決算延期
    cash_and_equivalents: float | None = None
    monthly_burn_rate: float | None = None
    cash_runway_months: float | None = None
    debt_to_equity: float | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DilutionData:
    """G2 大規模希薄化 用: 増資・新株予約権・CBなど株数増加要因。"""

    shares_outstanding: float | None = None
    fully_diluted_shares: float | None = None  # 完全希薄化後株数
    recent_issuances_12m: list[str] = field(default_factory=list)
    pending_dilution_events: list[str] = field(default_factory=list)
    dilution_ratio_estimate_pct: float | None = None  # 想定希薄化率(既発行株数比)
    warrant_overhang: bool | None = None  # 行使価格の低いワラントの残存など
    lockup_status: str | None = None
    use_of_proceeds: str | None = None  # 資金使途
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EarningsLinkageData:
    """G4 売上・利益への接続 用: 材料が実際の業績にどう・いつ効くか。"""

    estimated_revenue_impact: float | None = None
    estimated_impact_timing: str | None = None  # 今期 / 来期 / 複数期にわたる など
    guidance_revised: bool | None = None
    analyst_estimate_revision_pct: float | None = None
    progress_stage: str | None = None  # 研究/PoC/顧客評価/サンプル/SPEC/認証/採用/量産準備/量産/大型受注/売上/利益
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PricingInData:
    """G5 株価への織込み 用: 材料発表後、株価に既にどれだけ織り込まれたか(材料の賞味期限)。"""

    material_announced_at: datetime | None = None
    price_before_announcement: float | None = None
    high_after_announcement: float | None = None
    price_change_since_material_pct: float | None = None
    volume_spike_since_material: float | None = None
    days_since_material: int | None = None
    phase: str | None = None  # 初動 / 継続 / 過熱 / 出尽くし
    similar_past_case_reaction_pct: float | None = None  # 類似材料の過去反応幅
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CatalystTimingData:
    """G6 今後1〜3営業日の短期カタリスト 用。"""

    next_catalyst_date: date | None = None
    catalyst_type: str | None = None  # 決算発表 / 株主総会 / 商品発表 など
    catalyst_confidence: str | None = None  # 確定 / 濃厚 / 観測
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class JudgeInput:
    """judge() に渡す、1銘柄・1回精査分の入力データ一式。"""

    symbol: str
    name: str
    mode: ReviewMode
    current_price: float | None = None
    research_timestamp: datetime | None = None  # 調査・株価取得日時
    information_cutoff: datetime | None = None  # 情報カットオフ
    holding_quantity: int | None = None  # 保有数(既存保有の場合)
    holding_cost: float | None = None  # 取得値
    investable_amount: float | None = None  # 投資可能額
    material: MaterialInfo = field(default_factory=MaterialInfo)
    supply_demand: SupplyDemandData = field(default_factory=SupplyDemandData)
    chart: ChartData = field(default_factory=ChartData)
    accounting: AccountingData = field(default_factory=AccountingData)
    dilution: DilutionData = field(default_factory=DilutionData)
    earnings_linkage: EarningsLinkageData = field(default_factory=EarningsLinkageData)
    pricing_in: PricingInData = field(default_factory=PricingInData)
    catalyst_timing: CatalystTimingData = field(default_factory=CatalystTimingData)


# ---------------------------------------------------------------------------
# CIO決裁書の付帯構造(注文案・価格ティア・総合評価)
#
# OrderProposal / PriceTiers は v2.1(週間ランキング戦略)のENTRY/STOP/TARGETと
# 同じ形のため logic/common/order.py に切り出し、ここでは再エクスポートするだけにする
# (ファイル冒頭でimport済み)。
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RatingSet:
    """総合・短期・中期・長期・テンバガー、各10点。"""

    overall: float | None = None  # 総合
    short_term: float | None = None  # 短期
    mid_term: float | None = None  # 中期
    long_term: float | None = None  # 長期
    ten_bagger: float | None = None  # テンバガー
    max_points: float = 10.0


@dataclass(frozen=True)
class CIODecisionMemo:
    """CIO決裁書形式の最終出力。フィールド順はv1.3原文の冒頭表示順に合わせている。"""

    symbol: str
    name: str
    mode: ReviewMode

    research_timestamp: datetime  # 調査・株価時刻
    information_cutoff: datetime | None  # 情報カットオフ
    current_price: float | None  # 現在値

    corporate_judgment: CorporateJudgment  # 企業判定(優良/標準/脆弱/不明)
    trade_decision: TradeDecision  # 売買判定(ENTRY/TEST ENTRY/WAIT/WATCH/AVOID/EXIT)

    ratings: RatingSet  # 総合・短中長・テンバガー各10点

    corporate_value_score: ScoreResult  # 企業価値100
    entry_score: ScoreResult  # 短期ENTRY100
    feasibility_score: ScoreResult  # 実行可能性100

    gates: list[GateResult]  # 6ゲート

    supporting_points: list[str] = field(default_factory=list)  # 根拠3
    opposing_points: list[str] = field(default_factory=list)  # 反対3

    recommended_action: str | None = None  # 推奨行動
    order_proposal: OrderProposal = field(default_factory=OrderProposal)  # 注文案

    priority_reason_over_others: str | None = None  # 他候補より優先する理由
    missing_info: list[str] = field(default_factory=list)  # 不足情報
    confidence: str | None = None  # 確信度

    @property
    def failed_gates(self) -> list[GateResult]:
        return [g for g in self.gates if g.status == GateStatus.FAIL]

    @property
    def unknown_gates(self) -> list[GateResult]:
        return [g for g in self.gates if g.status == GateStatus.UNKNOWN]

    @property
    def caution_gates(self) -> list[GateResult]:
        return [g for g in self.gates if g.status == GateStatus.CAUTION]

    @property
    def total_score(self) -> float | None:
        totals = [self.corporate_value_score.total, self.entry_score.total, self.feasibility_score.total]
        if any(t is None for t in totals):
            return None
        return sum(totals)

    def to_memo_text(self) -> str:
        """CIO決裁書形式のプレーンテキストを生成する(通知・ログ表示用)。"""

        def fmt(value: object, unit: str = "") -> str:
            return "不明" if value is None else f"{value}{unit}"

        def fmt_score(score: ScoreResult) -> str:
            total = "算出不可" if score.total is None else f"{score.total:.1f}"
            return f"{score.name.value} {total} / {score.max_score:.0f}"

        lines = [
            f"【CIO決裁書】{self.name} ({self.symbol}) - モード{self.mode.value}",
            f"調査・株価時刻: {self.research_timestamp.isoformat()}",
            f"情報カットオフ: {fmt(self.information_cutoff)}",
            f"現在値: {fmt(self.current_price)}",
            f"企業判定: {self.corporate_judgment.value}",
            f"売買判定: {self.trade_decision.value}",
            "",
            "◆総合評価(各10点)",
            (
                f"  総合={fmt(self.ratings.overall)} 短期={fmt(self.ratings.short_term)} "
                f"中期={fmt(self.ratings.mid_term)} 長期={fmt(self.ratings.long_term)} "
                f"テンバガー={fmt(self.ratings.ten_bagger)}"
            ),
            "",
            "◆3スコア",
            f"  {fmt_score(self.corporate_value_score)}",
            f"  {fmt_score(self.entry_score)}",
            f"  {fmt_score(self.feasibility_score)}",
            f"  合計: {self.total_score if self.total_score is not None else '算出不可'}",
            "",
            "◆6ゲート",
        ]
        lines += [f"  - {g.gate.value}: {g.status.value} … {g.reason}" for g in self.gates]

        lines += [
            "",
            "◆根拠",
            *[f"  - {p}" for p in self.supporting_points],
            "◆反対",
            *[f"  - {p}" for p in self.opposing_points],
            "",
            f"推奨行動: {fmt(self.recommended_action)}",
            f"他候補より優先する理由: {fmt(self.priority_reason_over_others)}",
        ]
        if self.missing_info:
            lines.append("不足情報:")
            lines += [f"  - {m}" for m in self.missing_info]
        lines.append(f"確信度: {fmt(self.confidence)}")
        return "\n".join(lines)
