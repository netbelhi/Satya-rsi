# -*- coding: utf-8 -*-
"""Wilder's RSI — the standard smoothing method (not simple-average RSI)."""

import numpy as np
import pandas as pd


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Classic Wilder RSI using an exponential moving average with alpha = 1/period.
    This matches TradingView / most charting platforms' default RSI.
    """
    close = close.astype(float)
    delta = close.diff()

    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Where avg_loss is 0 (pure uptrend), RSI should be 100; where avg_gain is 0, RSI = 0
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    rsi = rsi.where(avg_gain != 0.0, 0.0)
    rsi.iloc[:period] = np.nan
    return rsi
