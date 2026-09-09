"""汎用テクニカル指標の計算関数。

短期ENTRYスコア(`logic/schema.py` の `ChartData`)を組み立てる材料として使う。
v1.3のENTRYスコアの具体的な配点式はまだ決まっていないため、ここでは
「どの指標を使うか」までを実装し、配点への変換は `logic/masa.py` 側で行う。
"""

from __future__ import annotations

import pandas as pd


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
