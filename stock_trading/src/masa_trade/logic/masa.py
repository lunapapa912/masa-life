"""MASA式 短期売買判定ロジック。

現時点では土台のみ。移動平均・出来高・RSIなど汎用的な指標の計算関数を用意し、
`judge()` でそれらをスコアリングして BUY/SELL/HOLD を返す骨組みにしている。
実際のMASA式の判定条件(スコアの重み付けや組み合わせ方)は要件確定後にここへ実装する。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from masa_trade.config import Settings


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class JudgeResult:
    symbol: str
    signal: Signal
    score: float
    details: dict[str, float]


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


def rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    result = 100 - (100 / (1 + avg_gain / avg_loss))
    result[(avg_loss == 0) & (avg_gain > 0)] = 100
    result[(avg_loss == 0) & (avg_gain == 0)] = 50
    return result


def volume_ratio(volume: pd.Series, window: int) -> pd.Series:
    avg_volume = volume.rolling(window=window).mean()
    return volume / avg_volume


def judge(symbol: str, ohlcv: pd.DataFrame, settings: Settings) -> JudgeResult:
    """1銘柄分のOHLCVからシグナルを判定する。

    TODO: MASA式の具体的な条件(移動平均のクロス、出来高急増、RSIの組み合わせ方など)
    が固まり次第、このスコアリングを実装する。現状はダミーでHOLDを返す。
    """
    params = settings.masa_logic
    close = ohlcv["Close"]
    volume = ohlcv["Volume"]

    details = {
        "sma_short": sma(close, params["moving_averages"]["short"]).iloc[-1],
        "sma_medium": sma(close, params["moving_averages"]["medium"]).iloc[-1],
        "sma_long": sma(close, params["moving_averages"]["long"]).iloc[-1],
        "rsi": rsi(close, params["rsi_period"]).iloc[-1],
        "volume_ratio": volume_ratio(volume, params["volume_average_window"]).iloc[-1],
    }

    score = 0.0  # TODO: 各指標からスコアを積み上げる

    if score >= params["buy_score_threshold"]:
        signal = Signal.BUY
    elif score <= params["sell_score_threshold"]:
        signal = Signal.SELL
    else:
        signal = Signal.HOLD

    return JudgeResult(symbol=symbol, signal=signal, score=score, details=details)
