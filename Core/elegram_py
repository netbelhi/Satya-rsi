# -*- coding: utf-8 -*-
"""
Satya Trading — RSI Divergence Notifier (Multi-Timeframe)
Configuration: watchlist, timeframes, RSI/pivot parameters, Telegram settings.
"""

# --------------------------------------------------------------------------
# Indices (Yahoo Finance symbols) — broad + sectoral
# --------------------------------------------------------------------------
INDEX_SYMBOLS = {
    # Broad
    "NIFTY 50":            "^NSEI",
    "BANK NIFTY":          "^NSEBANK",
    "SENSEX":              "^BSESN",
    "NIFTY FIN SERVICE":   "^CNXFIN",
    "NIFTY MIDCAP 100":    "^NSEMDCP50",
    # Sectoral
    "NIFTY IT":            "^CNXIT",
    "NIFTY AUTO":          "^CNXAUTO",
    "NIFTY PHARMA":        "^CNXPHARMA",
    "NIFTY FMCG":          "^CNXFMCG",
    "NIFTY METAL":         "^CNXMETAL",
    "NIFTY ENERGY":        "^CNXENERGY",
    "NIFTY REALTY":        "^CNXREALTY",
    "NIFTY PSU BANK":      "^CNXPSUBANK",
    "NIFTY MEDIA":         "^CNXMEDIA",
    "NIFTY INFRA":         "^CNXINFRA",
}

# Default selection shown pre-checked in the sidebar (rest available on demand)
DEFAULT_INDEX_SELECTION = [
    "NIFTY 50", "BANK NIFTY", "SENSEX", "NIFTY IT", "NIFTY AUTO", "NIFTY PHARMA",
]

# Note: a couple of sectoral index tickers vary by data provider/exchange feed.
# If any symbol above fails to fetch live data, the app automatically falls
# back to synthetic demo data for that symbol (clearly badged in the UI) —
# it will never crash the scan. Fix/replace the ticker here if needed.


# --------------------------------------------------------------------------
# Default stock watchlist (NSE — .NS suffix for yfinance)
# --------------------------------------------------------------------------
DEFAULT_STOCK_WATCHLIST = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS",
    "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS", "LT.NS", "ITC.NS",
    "BHARTIARTL.NS", "HINDUNILVR.NS", "BAJFINANCE.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "ADANIENT.NS",
    "ASIANPAINT.NS", "WIPRO.NS", "HCLTECH.NS", "ULTRACEMCO.NS",
    "TITAN.NS", "NTPC.NS", "POWERGRID.NS",
]

# --------------------------------------------------------------------------
# Timeframes: label -> (yfinance interval, yfinance lookback period)
# yfinance intraday limits: 5m/15m data ~60d max, 60m ~730d, 1d ~max
# --------------------------------------------------------------------------
TIMEFRAMES = {
    "5m":  ("5m",  "5d"),
    "15m": ("15m", "10d"),
    "1h":  ("60m", "60d"),
    "1d":  ("1d",  "1y"),
}
DEFAULT_TIMEFRAMES = ["5m", "15m", "1h", "1d"]

# --------------------------------------------------------------------------
# RSI & pivot / divergence detection parameters
# --------------------------------------------------------------------------
RSI_PERIOD = 14
PIVOT_LEFT = 3          # bars to the left that must be lower/higher
PIVOT_RIGHT = 3         # bars to the right that must be lower/higher (confirmation lag)
MIN_BARS_BETWEEN_PIVOTS = 3
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# --------------------------------------------------------------------------
# SMC confluence (Order Blocks / FVG / BOS-CHoCH structure)
# --------------------------------------------------------------------------
SMC_LOOKBACK_BARS = 30      # how far back an OB/FVG/structure event can be and still "count"
SMC_ZONE_TOLERANCE = 0.002   # 0.2% price tolerance when checking if a pivot sits inside a zone
REQUIRE_CONFLUENCE_DEFAULT = False
MIN_CONFLUENCE_SCORE_DEFAULT = 1

# --------------------------------------------------------------------------
# Telegram (leave blank to disable — can also be set from the sidebar)
# --------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""

# --------------------------------------------------------------------------
# Refresh & storage
# --------------------------------------------------------------------------
AUTO_REFRESH_SECONDS = 60
DATA_CACHE_TTL_SECONDS = 45
ALERT_LOG_PATH = "alerted_signals.json"

# Market hours (IST) — used to show an "open/closed" badge, not to block scanning
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"
