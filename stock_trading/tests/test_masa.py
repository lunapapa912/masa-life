import pandas as pd

from masa_trade.logic.masa import rsi, sma, volume_ratio


def test_sma_basic():
    series = pd.Series([1, 2, 3, 4, 5])
    result = sma(series, window=2)
    assert result.iloc[-1] == 4.5


def test_volume_ratio_basic():
    volume = pd.Series([100, 100, 100, 200])
    result = volume_ratio(volume, window=3)
    # 直近3件 [100, 100, 200] の平均は 400/3
    assert round(result.iloc[-1], 4) == round(200 / (400 / 3), 4)


def test_rsi_all_gains_is_100():
    series = pd.Series(range(1, 20))
    result = rsi(series, period=14)
    assert result.iloc[-1] == 100
