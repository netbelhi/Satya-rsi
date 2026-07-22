# -*- coding: utf-8 -*-
"""
Data layer: fetches OHLC candles via yfinance for the requested symbol +
timeframe. If yfinance / network is unavailable, falls back to a seeded
synthetic random-walk series (clearly labelled in the UI) so the app and
its divergence logic can still be exercised end-to-end.
"""

import hashlib
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

try:
    import yfinance as yf
    _HAS_YFINANCE = True
except Exception:
    _HAS_YFINANCE = False


def _seed_from(symbol: str, interval: str) -> int:
    h = hashlib.sha256(f"{symbol}:{interval}".encode()).hexdigest()
    return int(h[:8], 16)


def _synthetic_candles(symbol: str, interval: str, bars: int = 400) -> pd.DataFrame:
    """Deterministic pseudo-random walk scaled roughly like Indian index/stock prices,
    used only when live data can't be reached (no internet in this environment)."""
    rng = np.random.default_rng(_seed_from(symbol, interval))

    base_price = {
        "^NSEI": 24500, "^NSEBANK": 51500, "^BSESN": 80500, "^CNXFIN": 23500,
    }.get(symbol, 1500 + (hash(symbol) % 3000))

    freq_minutes = {"5m": 5, "15m": 15, "60m": 60, "1d": 24 * 60}
    step_minutes = freq_minutes.get(interval, 60)

    vol = 0.0016 if interval != "1d" else 0.011
    rets = rng.normal(0, vol, bars)
    # small mean-reversion + occasional trend burst so divergence patterns can appear
    trend = np.sin(np.linspace(0, 6.5, bars)) * vol * 3
    rets = rets + trend / bars
    close = base_price * np.cumprod(1 + rets)

    high = close * (1 + np.abs(rng.normal(0, vol * 0.6, bars)))
    low = close * (1 - np.abs(rng.normal(0, vol * 0.6, bars)))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    volume = rng.integers(50_000, 2_000_000, bars)

    end = datetime.now()
    idx = pd.date_range(end=end, periods=bars, freq=f"{step_minutes}min")

    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


def fetch_candles(symbol: str, interval: str, period: str) -> tuple[pd.DataFrame, bool]:
    """Returns (dataframe, is_live). is_live=False means synthetic fallback was used."""
    if _HAS_YFINANCE:
        try:
            df = yf.download(
                symbol, interval=interval, period=period,
                progress=False, auto_adjust=True, threads=False,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            if df is not None and len(df) >= 30:
                df = df.dropna(subset=["Close"])
                return df, True
        except Exception:
            pass
    return _synthetic_candles(symbol, interval), False
