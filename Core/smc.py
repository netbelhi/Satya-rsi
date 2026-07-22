# -*- coding: utf-8 -*-
"""
SMC (Smart Money Concept) layer — Fair Value Gaps, Order Blocks, and
BOS/CHoCH structure events — used to build a "confluence score" for each
RSI divergence signal (matches Satya Trading's SMC/ICT toolkit approach:
structure + liquidity + OB/FVG confirmation before taking a signal).
"""

from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np
import pandas as pd

from core.divergence import Pivot, DivergenceSignal


@dataclass
class FVGZone:
    kind: str          # 'bullish' | 'bearish'
    top: float
    bottom: float
    pos: int            # position of the middle (impulse) candle
    timestamp: object


@dataclass
class OrderBlock:
    kind: str           # 'bullish' | 'bearish'
    top: float
    bottom: float
    pos: int
    timestamp: object
    mitigated: bool = False


@dataclass
class StructureEvent:
    kind: str            # 'BOS' | 'CHoCH'
    direction: str        # 'bullish' | 'bearish'
    pos: int
    price: float
    timestamp: object


@dataclass
class ConfluenceResult:
    score: int
    tags: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.score >= 2:
            return "🟢🟢 Strong SMC Confluence"
        if self.score == 1:
            return "🟡 Partial Confluence"
        return "—"


# ---------------------------------------------------------------------------
# Fair Value Gaps (3-candle imbalance)
# ---------------------------------------------------------------------------
def find_fvgs(df: pd.DataFrame) -> List[FVGZone]:
    h = df["High"].values
    l = df["Low"].values
    n = len(df)
    zones: List[FVGZone] = []
    for i in range(1, n - 1):
        if l[i + 1] > h[i - 1]:
            zones.append(FVGZone("bullish", top=float(l[i + 1]), bottom=float(h[i - 1]),
                                  pos=i, timestamp=df.index[i]))
        elif h[i + 1] < l[i - 1]:
            zones.append(FVGZone("bearish", top=float(l[i - 1]), bottom=float(h[i + 1]),
                                  pos=i, timestamp=df.index[i]))
    return zones


# ---------------------------------------------------------------------------
# Order Blocks — the opposite-colour candle right before the FVG-creating move
# ---------------------------------------------------------------------------
def find_order_blocks(df: pd.DataFrame, fvgs: List[FVGZone]) -> List[OrderBlock]:
    o = df["Open"].values
    c = df["Close"].values
    n = len(df)
    obs: List[OrderBlock] = []
    for fvg in fvgs:
        ob_pos = fvg.pos - 1
        if ob_pos < 0:
            continue
        body_top = float(max(o[ob_pos], c[ob_pos]))
        body_bottom = float(min(o[ob_pos], c[ob_pos]))
        is_down_candle = c[ob_pos] < o[ob_pos]
        is_up_candle = c[ob_pos] > o[ob_pos]
        if fvg.kind == "bullish" and is_down_candle:
            obs.append(OrderBlock("bullish", top=body_top, bottom=body_bottom,
                                   pos=ob_pos, timestamp=df.index[ob_pos]))
        elif fvg.kind == "bearish" and is_up_candle:
            obs.append(OrderBlock("bearish", top=body_top, bottom=body_bottom,
                                   pos=ob_pos, timestamp=df.index[ob_pos]))

    # Mark mitigated: price later closed all the way through the OB zone
    close = df["Close"].values
    for ob in obs:
        after = close[ob.pos + 1:]
        if len(after) == 0:
            continue
        if ob.kind == "bullish":
            ob.mitigated = bool(np.any(after < ob.bottom))
        else:
            ob.mitigated = bool(np.any(after > ob.top))
    return obs


# ---------------------------------------------------------------------------
# BOS / CHoCH structure events (pivot-level swing-break state machine)
# ---------------------------------------------------------------------------
def detect_structure_events(pivots: List[Pivot]) -> List[StructureEvent]:
    events: List[StructureEvent] = []
    ordered = sorted(pivots, key=lambda p: p.pos)

    last_high: Optional[Pivot] = None
    last_low: Optional[Pivot] = None
    trend = None  # 'up' | 'down' | None

    for p in ordered:
        if p.kind == "H":
            if last_high is not None and p.price > last_high.price:
                kind = "BOS" if trend == "up" else "CHoCH"
                events.append(StructureEvent(kind, "bullish", p.pos, p.price, p.timestamp))
                trend = "up"
            last_high = p
        else:  # 'L'
            if last_low is not None and p.price < last_low.price:
                kind = "BOS" if trend == "down" else "CHoCH"
                events.append(StructureEvent(kind, "bearish", p.pos, p.price, p.timestamp))
                trend = "down"
            last_low = p

    return events


# ---------------------------------------------------------------------------
# Confluence scoring — does an SMC zone / structure event back up this signal?
# ---------------------------------------------------------------------------
def compute_confluence(
    signal: DivergenceSignal,
    fvgs: List[FVGZone],
    obs: List[OrderBlock],
    structure_events: List[StructureEvent],
    lookback_bars: int,
    zone_tolerance: float,
) -> ConfluenceResult:
    direction = "bullish" if signal.bias == "BUY" else "bearish"
    pivot_pos = signal.p2.pos
    pivot_price = signal.p2.price
    tags: List[str] = []
    score = 0

    # 1. Order Block confluence — unmitigated, matching direction, price overlaps
    candidate_obs = [
        ob for ob in obs
        if ob.kind == direction and not ob.mitigated
        and ob.pos <= pivot_pos and (pivot_pos - ob.pos) <= lookback_bars
    ]
    for ob in sorted(candidate_obs, key=lambda o: -o.pos):
        lo, hi = ob.bottom * (1 - zone_tolerance), ob.top * (1 + zone_tolerance)
        if lo <= pivot_price <= hi:
            tags.append(f"{direction.title()} Order Block @ {ob.bottom:.1f}-{ob.top:.1f}")
            score += 1
            break

    # 2. FVG confluence
    candidate_fvgs = [
        f for f in fvgs
        if f.kind == direction and f.pos <= pivot_pos and (pivot_pos - f.pos) <= lookback_bars
    ]
    for f in sorted(candidate_fvgs, key=lambda x: -x.pos):
        lo, hi = f.bottom * (1 - zone_tolerance), f.top * (1 + zone_tolerance)
        if lo <= pivot_price <= hi:
            tags.append(f"{direction.title()} FVG @ {f.bottom:.1f}-{f.top:.1f}")
            score += 1
            break

    # 3. Structure confluence — most recent BOS/CHoCH before the pivot agrees in direction
    recent = [
        e for e in structure_events
        if e.pos <= pivot_pos and (pivot_pos - e.pos) <= lookback_bars
    ]
    if recent:
        last_event = max(recent, key=lambda e: e.pos)
        if last_event.direction == direction:
            tags.append(f"{last_event.kind} {last_event.direction.title()} structure")
            score += 1

    return ConfluenceResult(score=score, tags=tags)
