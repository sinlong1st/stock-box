import pandas as pd

from stocksense import indicators


def test_calculate_rsi_all_gains_is_100():
    prices = pd.Series(range(1, 21))  # strictly increasing -> no losses
    rsi = indicators.calculate_rsi(prices, period=14)
    assert rsi.iloc[-1] == 100.0


def test_latest_rsi_none_when_insufficient_data():
    assert indicators.latest_rsi(pd.Series(range(1, 15)), period=14) is None  # 14 pts
    assert indicators.latest_rsi(pd.Series(range(1, 17)), period=14) is not None


def test_find_support_and_resistance_average_last_n_locals():
    prices = pd.Series([10, 8, 12, 6, 11, 4, 13, 5, 9])
    # local lows: 8, 6, 4, 5 -> last 3 = (6+4+5)/3 = 5.0
    assert indicators.find_support(prices, n_locals=3) == 5.0
    # local highs: 12, 11, 13 -> (12+11+13)/3 = 12.0
    assert indicators.find_resistance(prices, n_locals=3) == 12.0


def test_support_resistance_fallback_when_too_few_locals():
    prices = pd.Series([5, 3, 7])  # one local low, no local high
    assert indicators.find_support(prices, n_locals=3) == 3.0   # min(close)
    assert indicators.find_resistance(prices, n_locals=3) == 7.0  # max(close)


def test_52w_range_and_position():
    prices = pd.Series([10, 20, 15, 30, 25])
    low, high = indicators.get_52w_range(prices)
    assert (low, high) == (10.0, 30.0)
    assert indicators.get_position_in_range(20, low, high) == 0.5


def test_position_in_range_flat_series_is_neutral():
    assert indicators.get_position_in_range(50, 50, 50) == 0.5
