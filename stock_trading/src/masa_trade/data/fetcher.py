"""株価データ取得。今は yfinance のみ対応。"""

from __future__ import annotations

import pandas as pd
import yfinance as yf

from masa_trade.config import Settings


def fetch_ohlcv(symbol: str, settings: Settings) -> pd.DataFrame:
    """指定銘柄のOHLCVを取得する。列は Open/High/Low/Close/Volume。"""
    period_days = settings.data["lookback_days"]
    interval = settings.data["interval"]
    df = yf.download(
        symbol,
        period=f"{period_days}d",
        interval=interval,
        auto_adjust=True,
        progress=False,
    )
    if df.empty:
        raise ValueError(f"データを取得できませんでした: {symbol}")
    return df
