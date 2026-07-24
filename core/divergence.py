# -*- coding: utf-8 -*-
"""
Pivot (swing) detection on price, and RSI divergence classification.

Divergence types (classic definitions):
  Regular Bearish : price makes a Higher High, RSI makes a Lower High   -> reversal down
  Regular Bullish : price makes a Lower Low,   RSI makes a Higher Low   -> reversal up
  Hidden Bearish  : price makes a Lower High,  RSI makes a Higher High -> trend continuation down
  Hidden Bullish  : price makes a Higher Low,  RSI makes a Lower Low   -> trend continuation up
"""

from dataclasses import dataclass
from typing import List, Optional
import numpy as np
import pandas as pd


@dataclass
class Pivot:
    pos: int          # integer bar position in the series
    timestamp: object  # pandas Timestamp
    price: float
    rsi: float
    kind: str          # 'H' or 'L'


@dataclass
class DivergenceSignal:
    symbol: str
    timeframe: str
    div_type: str       # "Regular Bullish" | "Regular Bearish" | "Hidden Bullish" | "Hidden Bearish"
    pivot_kind: str      # 'H' or 'L'
    p1: Pivot
    p2: Pivot
    signal_key: str       # unique dedup key

    @property
    def bias(self) -> str:
        return "BUY" if "Bullish" in self.div_type else "SELL"


def find_price_pivots(close: pd.Series, left: int, right: int) -> List[Pivot]:
    """Find confirmed swing highs/lows on the price series.
    A pivot at position i is confirmed once `right` bars after it exist.
    """
    vals = close.values
    n = len(vals)
    pivots: List[Pivot] = []
    for i in range(left, n - right):
        window = vals[i - left : i + right + 1]
        v = vals[i]
        if np.isnan(v) or np.isnan(window).any():
            continue
        center = left
        if v == window.max() and np.argmax(window) == center:
            pivots.append(Pivot(i, close.index[i], float(v), np.nan, "H"))
        elif v == window.min() and np.argmin(window) == center:
            pivots.append(Pivot(i, close.index[i], float(v), np.nan, "L"))
    return pivots


def _attach_rsi(pivots: List[Pivot], rsi: pd.Series) -> List[Pivot]:
    out = []
    for p in pivots:
        r = rsi.iloc[p.pos]
        if pd.isna(r):
            continue
        out.append(Pivot(p.pos, p.timestamp, p.price, float(r), p.kind))
    return out


def _dedupe_close_pivots(pivots: List[Pivot], min_gap: int) -> List[Pivot]:
    """Keep only the most extreme pivot within a min_gap window of the same kind,
    to avoid noisy back-to-back pivots."""
    if not pivots:
        return pivots
    cleaned: List[Pivot] = [pivots[0]]
    for p in pivots[1:]:
        last = cleaned[-1]
        if p.kind == last.kind and (p.pos - last.pos) < min_gap:
            keep_new = (p.price > last.price) if p.kind == "H" else (p.price < last.price)
            if keep_new:
                cleaned[-1] = p
        else:
            cleaned.append(p)
    return cleaned


def detect_divergences(
    df: pd.DataFrame,
    rsi: pd.Series,
    symbol: str,
    timeframe: str,
    left: int,
    right: int,
    min_gap: int,
    lookback_pivots: int = 6,
) -> List[DivergenceSignal]:
    """Scan the last `lookback_pivots` pivot-highs and pivot-lows for divergence
    against RSI at the same bar positions. Returns ALL matches found in the
    lookback window (caller decides which are "new" vs already-alerted)."""
    close = df["Close"]
    raw_pivots = find_price_pivots(close, left, right)
    raw_pivots = _attach_rsi(raw_pivots, rsi)
    raw_pivots = _dedupe_close_pivots(raw_pivots, min_gap)

    highs = [p for p in raw_pivots if p.kind == "H"][-lookback_pivots:]
    lows = [p for p in raw_pivots if p.kind == "L"][-lookback_pivots:]

    signals: List[DivergenceSignal] = []

    for a, b in zip(highs, highs[1:]):
        if b.price > a.price and b.rsi < a.rsi:
            dtype = "Regular Bearish"
        elif b.price < a.price and b.rsi > a.rsi:
            dtype = "Hidden Bearish"
        else:
            continue
        key = f"{symbol}|{timeframe}|{dtype}|{b.pos}"
        signals.append(DivergenceSignal(symbol, timeframe, dtype, "H", a, b, key))

    for a, b in zip(lows, lows[1:]):
        if b.price < a.price and b.rsi > a.rsi:
            dtype = "Regular Bullish"
        elif b.price > a.price and b.rsi < a.rsi:
            dtype = "Hidden Bullish"
        else:
            continue
        key = f"{symbol}|{timeframe}|{dtype}|{b.pos}"
        signals.append(DivergenceSignal(symbol, timeframe, dtype, "L", a, b, key))

    return signals


def latest_signal_only(signals: List[DivergenceSignal]) -> List[DivergenceSignal]:
    """Keep only the most recent signal per (symbol, timeframe, div_type)."""
    best = {}
    for s in signals:
        k = (s.symbol, s.timeframe, s.div_type)
        if k not in best or s.p2.pos > best[k].p2.pos:
            best[k] = s
    return list(best.values())


def _invalidation_status(signal: DivergenceSignal, close: pd.Series) -> str:
    """'Active'  = confirmed and the reversal thesis still holds (price hasn't since
                   broken past the pivot extreme in the adverse direction).
       'False'   = confirmed, but price later broke past that pivot extreme —
                   the setup is invalidated (e.g. a fresh lower low after a bullish
                   divergence's low pivot means the "higher low" thesis failed)."""
    pos2 = signal.p2.pos
    after = close.values[pos2 + 1:]
    if len(after) == 0:
        return "Active"
    if signal.bias == "BUY":
        return "False" if bool((after < signal.p2.price).any()) else "Active"
    else:
        return "False" if bool((after > signal.p2.price).any()) else "Active"


def classify_signals(
    df: pd.DataFrame,
    rsi: pd.Series,
    symbol: str,
    timeframe: str,
    left: int,
    right_confirmed: int,
    min_gap: int,
    lookback_pivots: int = 6,
):
    """Returns a list of (DivergenceSignal, status) tuples where status is one of:
       'Active'  — fully pivot-confirmed, reversal thesis still valid right now.
       'False'   — fully pivot-confirmed, but later price action invalidated it.
       'Pending' — a newer, still-forming pattern using a looser (1-bar) pivot
                   confirmation — not locked in yet, can change on the next bar(s).
    Only one Active/False signal and at most one Pending signal exist per div_type,
    since both passes are already deduped via latest_signal_only()."""
    close = df["Close"]

    confirmed = latest_signal_only(
        detect_divergences(df, rsi, symbol, timeframe, left, right_confirmed, min_gap, lookback_pivots)
    )
    provisional = latest_signal_only(
        detect_divergences(df, rsi, symbol, timeframe, left, 1, min_gap, lookback_pivots)
    )

    results = []
    confirmed_pos = {}
    for s in confirmed:
        status = _invalidation_status(s, close)
        results.append((s, status))
        confirmed_pos[s.div_type] = s.p2.pos

    for s in provisional:
        last_confirmed_pos = confirmed_pos.get(s.div_type)
        if last_confirmed_pos is None or s.p2.pos > last_confirmed_pos:
            results.append((s, "Pending"))

    return results
