"""複数の判定ロジック(v1.3・v2.1)で共通の注文・地合いスキーマ。

v1.3の【執行】節の注文案(区分・指値・株数・逆指値・利確・最大損失・RR等)と、
v2.1の【12.ENTRY】(ENTRY/STOP/TARGET/100株必要資金/最大損失/R:R)は
同じ形の情報なので、二重定義を避けてここにまとめる。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MarketRegime(str, Enum):
    """地合い判定。v2.19・v1.3・v2.1で共通して使われる3値。"""

    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    DEFENSE = "DEFENSE"


@dataclass(frozen=True)
class PriceTiers:
    """打診/通常/強気価格。"""

    tentative: float | None = None  # 打診価格
    normal: float | None = None  # 通常価格
    aggressive: float | None = None  # 強気価格


@dataclass(frozen=True)
class OrderProposal:
    """注文案。区分・指値・株数・有効期限・逆指値・利確・最大損失・RR・取消条件などを持つ。"""

    order_category: str | None = None  # 区分(現物買い/信用買い等)
    price_tiers: PriceTiers = field(default_factory=PriceTiers)
    quantity: int | None = None  # 株数(原則100株単位)
    validity_period: str | None = None  # 有効期限
    stop_trigger_price: float | None = None  # 逆指値発動値(STOP)
    stop_method: str | None = None  # 発動方法
    expected_fill_price: float | None = None  # 想定約定
    take_profit_price: float | None = None  # 利確(TARGET)
    max_loss: float | None = None  # 最大損失(100株あたり等)
    risk_reward: float | None = None  # RR
    invalidation_condition: str | None = None  # 無効条件
    cancel_condition: str | None = None  # 取消条件
    reconfirm_at_1230_condition: str | None = None  # 12:30再判定条件(v1.3固有。v2.1では未使用)
