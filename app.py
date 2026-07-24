# -*- coding: utf-8 -*-
"""
Satya Trading — Multi-Timeframe RSI Divergence Notifier
=========================================================
Live-market RSI divergence scanner for NIFTY 50 / BANK NIFTY / SENSEX and
NSE stocks, across multiple timeframes, with Telegram alerting and
duplicate-alert suppression.

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import time
from datetime import datetime

import pandas as pd
import pytz
import streamlit as st

from core import config
from core.indicators import wilder_rsi
from core.divergence import detect_divergences, latest_signal_only, find_price_pivots, classify_signals
from core.data import fetch_candles
from core.telegram_alert import send_telegram_message, format_alert
from core import persistence
from core import smc
from core import charting

IST = pytz.timezone("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Page setup + dark "trading terminal" theme
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Satya Trading — RSI Divergence Notifier",
    page_icon="📡",
    layout="wide",
)

st.markdown("""
<style>
:root{
  --bg:#0a0e14; --panel:#10161f; --panel2:#151c27; --accent:#00e5a0; --accent2:#3ea6ff;
  --text:#e6edf3; --muted:#8b98a5; --border:#1f2937; --gold:#f0b90b; --red:#ff5470;
}
.stApp{ background:var(--bg); color:var(--text);}
section[data-testid="stSidebar"]{ background:var(--panel); border-right:1px solid var(--border);}
h1,h2,h3{ color:var(--accent) !important; font-family:'Rajdhani',sans-serif;}
.brandbar{ display:flex; align-items:center; justify-content:space-between;
  background:var(--panel); border:1px solid var(--border); border-radius:10px;
  padding:14px 20px; margin-bottom:18px;}
.brandbar .title{ color:var(--gold); letter-spacing:3px; font-size:13px; text-transform:uppercase;}
.badge{ display:inline-block; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:600; margin-left:8px;}
.badge-open{ background:rgba(0,229,160,0.15); color:var(--accent); border:1px solid var(--accent);}
.badge-closed{ background:rgba(255,84,112,0.15); color:var(--red); border:1px solid var(--red);}
.badge-live{ background:rgba(62,166,255,0.15); color:var(--accent2); border:1px solid var(--accent2);}
.badge-demo{ background:rgba(240,185,11,0.15); color:var(--gold); border:1px solid var(--gold);}
div[data-testid="stMetric"]{ background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:10px;}
.stDataFrame{ border:1px solid var(--border);}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="brandbar">
  <div><div class="title">Satya Trading</div>
       <div style="font-size:22px;font-weight:700;color:#e6edf3;">RSI Divergence Notifier — Multi-Timeframe</div></div>
  <div style="text-align:right;color:#8b98a5;font-size:12px;">NIFTY 50 · BANK NIFTY · SENSEX · NSE Stocks</div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎯 Watchlist")
    sel_indices = st.multiselect(
        "Indices (broad + sectoral)", list(config.INDEX_SYMBOLS.keys()),
        default=config.DEFAULT_INDEX_SELECTION,
    )
    sel_stocks = st.multiselect(
        "NSE Stocks", config.DEFAULT_STOCK_WATCHLIST,
        default=config.DEFAULT_STOCK_WATCHLIST[:8],
    )
    extra_symbol = st.text_input("+ Add custom NSE symbol (e.g. DMART.NS)", "")

    st.markdown("### ⏱️ Timeframes")
    sel_timeframes = st.multiselect(
        "Scan on", list(config.TIMEFRAMES.keys()),
        default=config.DEFAULT_TIMEFRAMES,
    )

    st.markdown("### ⚙️ RSI / Pivot Settings")
    rsi_period = st.slider("RSI period", 5, 30, config.RSI_PERIOD)
    pivot_lr = st.slider("Pivot left/right bars", 2, 6, config.PIVOT_LEFT)
    min_gap = st.slider("Min bars between pivots", 1, 10, config.MIN_BARS_BETWEEN_PIVOTS)

    st.markdown("### 🧩 SMC Confluence")
    smc_lookback = st.slider("Lookback bars for OB/FVG/structure", 10, 80, config.SMC_LOOKBACK_BARS)
    require_confluence = st.checkbox(
        "Sirf SMC-confirmed signals par alert bhejo", value=config.REQUIRE_CONFLUENCE_DEFAULT
    )
    min_conf_score = st.slider("Min confluence score", 1, 3, config.MIN_CONFLUENCE_SCORE_DEFAULT)

    st.markdown("### 💾 Alert Persistence")
    def _secret(key: str) -> str:
        try:
            return st.secrets.get(key, "")
        except Exception:
            return ""

    _secret_token = _secret("GITHUB_TOKEN")
    _secret_gist = _secret("GIST_ID")

    if _secret_token and _secret_gist:
        gh_token, gist_id = _secret_token, _secret_gist
        st.caption("✅ Streamlit Secrets se GitHub Gist mila — cloud-persistent hai.")
    else:
        with st.expander("Cloud par persistent banao (recommended for Streamlit Cloud)", expanded=False):
            st.caption(
                "Local file Streamlit Cloud restart/sleep par reset ho jati hai, isliye "
                "koi bhi ek signal dobara alert ho sakta hai. Permanent dedup ke liye "
                "GitHub token + Gist ID do — ya best: **App Settings → Secrets** mein "
                "`GITHUB_TOKEN` aur `GIST_ID` ke naam se save kar do, phir yeh box bhi nahi dikhega."
            )
            gh_token = st.text_input(
                "GitHub Personal Access Token (scope: gist)", type="password",
                help="github.com → Settings → Developer settings → Personal access tokens → "
                     "Generate new token (classic) → sirf 'gist' scope tick karo.",
            )
            gist_id = st.text_input("Gist ID (khaali chodo agar naya banana hai)")
            if gh_token and not gist_id and st.button("🆕 Naya alert-store Gist banao"):
                new_id = persistence.create_gist(gh_token)
                if new_id:
                    gist_id = new_id
                    st.success(
                        f"Gist ban gaya — ID: `{new_id}`. Ise **App Settings → Secrets** mein "
                        f"`GIST_ID = \"{new_id}\"` ke saath save kar lo, taaki dobara type na karna pade."
                    )
                else:
                    st.error("Gist nahi ban paya — token check karo (scope 'gist' hona chahiye).")

    st.markdown("### 📲 Telegram Alerts")
    telegram_enabled = st.checkbox("Enable Telegram alerts", value=False)
    bot_token = st.text_input("Bot token", value=config.TELEGRAM_BOT_TOKEN, type="password")
    chat_id = st.text_input("Chat ID", value=config.TELEGRAM_CHAT_ID)

    st.markdown("### 🔄 Live Scanning")
    live_mode = st.checkbox("Auto-refresh (Live Mode)", value=False)
    refresh_secs = st.slider("Refresh every (sec)", 20, 300, config.AUTO_REFRESH_SECONDS, step=10)
    scan_now = st.button("🔍 Scan Now", use_container_width=True)

# ---------------------------------------------------------------------------
# Build the symbol list (label -> yahoo symbol)
# ---------------------------------------------------------------------------
symbol_map = {name: config.INDEX_SYMBOLS[name] for name in sel_indices}
for s in sel_stocks:
    symbol_map[s.replace(".NS", "")] = s
if extra_symbol.strip():
    sym = extra_symbol.strip().upper()
    if not sym.endswith(".NS") and not sym.startswith("^"):
        sym = sym + ".NS"
    symbol_map[extra_symbol.strip().upper().replace(".NS", "")] = sym

if not symbol_map or not sel_timeframes:
    st.warning("Sidebar se kam se kam ek symbol aur ek timeframe select karo.")
    st.stop()

# ---------------------------------------------------------------------------
# Market status badge (IST)
# ---------------------------------------------------------------------------
now_ist = datetime.now(IST)
open_t = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
close_t = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
is_weekday = now_ist.weekday() < 5
market_open = is_weekday and open_t <= now_ist <= close_t

c1, c2, c3 = st.columns([2, 2, 6])
with c1:
    st.markdown(
        f'Market: <span class="badge {"badge-open" if market_open else "badge-closed"}">'
        f'{"OPEN" if market_open else "CLOSED"}</span>',
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(f"IST time: **{now_ist.strftime('%H:%M:%S')}**")

# ---------------------------------------------------------------------------
# Cached data fetch
# ---------------------------------------------------------------------------
@st.cache_data(ttl=config.DATA_CACHE_TTL_SECONDS, show_spinner=False)
def _cached_fetch(symbol: str, interval: str, period: str, resample: str = None):
    return fetch_candles(symbol, interval, period, resample)


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------
alert_store = persistence.get_store(gh_token, gist_id, config.ALERT_LOG_PATH)
alerted_keys = alert_store.load()
rows = []
any_live = False
any_synthetic = False
new_signals_this_scan = []
chart_context = {}   # (label, tf) -> {"df", "rsi", "fvgs", "obs", "signals": [(sig,status), ...]}

progress = st.progress(0.0, text="Scanning...")
total = len(symbol_map) * len(sel_timeframes)
done = 0

for label, symbol in symbol_map.items():
    for tf in sel_timeframes:
        tf_cfg = config.TIMEFRAMES[tf]
        interval, period, resample = tf_cfg["interval"], tf_cfg["period"], tf_cfg.get("resample")
        try:
            df, is_live = _cached_fetch(symbol, interval, period, resample)
            any_live = any_live or is_live
            any_synthetic = any_synthetic or (not is_live)
            if df is None or len(df) < (rsi_period + pivot_lr + 5):
                done += 1
                continue
            rsi = wilder_rsi(df["Close"], rsi_period)

            # --- SMC context for this symbol/timeframe (computed once, reused per signal) ---
            fvgs = smc.find_fvgs(df)
            obs = smc.find_order_blocks(df, fvgs)
            price_pivots = find_price_pivots(df["Close"], pivot_lr, pivot_lr)
            structure_events = smc.detect_structure_events(price_pivots)

            classified = classify_signals(
                df, rsi, label, tf, pivot_lr, pivot_lr, min_gap, lookback_pivots=6
            )
            chart_context[(label, tf)] = {
                "df": df, "rsi": rsi, "fvgs": fvgs, "obs": obs, "signals": classified,
            }

            for s, status in classified:
                conf = smc.compute_confluence(
                    s, fvgs, obs, structure_events, smc_lookback, config.SMC_ZONE_TOLERANCE
                )
                tp = smc.compute_trade_plan(s, obs) if status in ("Active", "Pending") else None
                is_new = status == "Active" and s.signal_key not in alerted_keys
                status_badge = {"Active": "🟢 Active", "Pending": "🟡 Pending", "False": "⚪ False"}[status]

                rows.append({
                    "Symbol": label, "TF": tf, "Type": s.div_type, "Bias": s.bias,
                    "Status": status_badge,
                    "Pivot Time": s.p2.timestamp, "Price": round(s.p2.price, 2),
                    "RSI": round(s.p2.rsi, 1), "SMC": conf.label,
                    "Entry": round(tp.entry, 2) if tp else "—",
                    "SL": round(tp.stop_loss, 2) if tp else "—",
                    "T1 (1.5R)": round(tp.target1, 2) if tp else "—",
                    "T2 (3R)": round(tp.target2, 2) if tp else "—",
                    "SMC Tags": "; ".join(conf.tags) if conf.tags else "—",
                    "New": "🆕" if is_new else "",
                })
                if is_new:
                    new_signals_this_scan.append((s, label, conf))
                    alerted_keys.add(s.signal_key)
        except Exception as e:
            rows.append({
                "Symbol": label, "TF": tf, "Type": f"error: {e}", "Bias": "-", "Status": "-",
                "Pivot Time": "-", "Price": None, "RSI": None, "SMC": "-",
                "Entry": "-", "SL": "-", "T1 (1.5R)": "-", "T2 (3R)": "-",
                "SMC Tags": "-", "New": "",
            })
        done += 1
        progress.progress(done / total, text=f"Scanning... {label} [{tf}]")

progress.empty()
save_ok = alert_store.save(alerted_keys)

# ---------------------------------------------------------------------------
# Data-source badge
# ---------------------------------------------------------------------------
with c3:
    if any_live and not any_synthetic:
        st.markdown('Data: <span class="badge badge-live">LIVE (yfinance)</span>', unsafe_allow_html=True)
    elif any_live and any_synthetic:
        st.markdown('Data: <span class="badge badge-live">LIVE</span> '
                     '<span class="badge badge-demo">+ SYNTHETIC (kuch symbols)</span>', unsafe_allow_html=True)
    else:
        st.markdown('Data: <span class="badge badge-demo">SYNTHETIC DEMO — no internet/yfinance in this environment</span>',
                     unsafe_allow_html=True)
    persist_cls = "badge-live" if isinstance(alert_store, persistence.GistStore) else "badge-demo"
    st.markdown(f'Dedup storage: <span class="badge {persist_cls}">{alert_store.backend_name}</span>',
                unsafe_allow_html=True)
    if not save_ok:
        st.caption("⚠️ Alert store save fail hua is scan mein — agla scan retry karega.")

# ---------------------------------------------------------------------------
# Send Telegram alerts for new signals
# ---------------------------------------------------------------------------
if telegram_enabled and new_signals_this_scan:
    to_send = new_signals_this_scan
    if require_confluence:
        to_send = [(s, lbl, c) for (s, lbl, c) in new_signals_this_scan if c.score >= min_conf_score]
        skipped = len(new_signals_this_scan) - len(to_send)
        if skipped:
            st.caption(f"ℹ️ {skipped} naya signal mila but SMC confluence (min score {min_conf_score}) na milne ki wajah se alert skip hua.")
    for sig, label, conf in to_send:
        msg = format_alert(sig, label, confluence=conf)
        ok, info = send_telegram_message(bot_token, chat_id, msg)
        if not ok:
            st.toast(f"Telegram bhej nahi paya ({label} {sig.timeframe}): {info}", icon="⚠️")
elif new_signals_this_scan and not telegram_enabled:
    st.info(f"{len(new_signals_this_scan)} naya divergence signal mila — Telegram alerts abhi off hain (sidebar se on karo).")

# ---------------------------------------------------------------------------
# Results table
# ---------------------------------------------------------------------------
st.markdown("### 📊 Active Divergence Signals")
if rows:
    result_df = pd.DataFrame(rows)
    result_df = result_df.sort_values("New", ascending=False)

    def _style_bias(v):
        if v == "BUY":
            return "color:#00e5a0;font-weight:700;"
        if v == "SELL":
            return "color:#ff5470;font-weight:700;"
        return ""

    styler = result_df.style
    style_fn = getattr(styler, "map", None) or styler.applymap
    st.dataframe(
        style_fn(_style_bias, subset=["Bias"]),
        use_container_width=True, hide_index=True, height=min(60 + 35 * len(result_df), 600),
    )
    if new_signals_this_scan:
        st.success(f"✅ Is scan mein {len(new_signals_this_scan)} NAYA signal mila (🆕 marked).")
else:
    st.info("Abhi koi divergence signal nahi mila selected watchlist/timeframes par.")

# ---------------------------------------------------------------------------
# Chart view
# ---------------------------------------------------------------------------
st.markdown("### 📈 Chart View")
if chart_context:
    chart_keys = list(chart_context.keys())

    def _chart_key_label(k):
        lbl, tf = k
        n_sigs = len([s for s in chart_context[k]["signals"] if s[1] != "False"])
        return f"{lbl} — {tf}" + (f"  ({n_sigs} signal)" if n_sigs else "")

    # default to the first symbol/tf that has an Active signal, if any
    default_idx = 0
    for i, k in enumerate(chart_keys):
        if any(st_ == "Active" for _, st_ in chart_context[k]["signals"]):
            default_idx = i
            break

    chosen = st.selectbox(
        "Symbol — Timeframe chuno", chart_keys, index=default_idx,
        format_func=_chart_key_label,
    )
    ctx = chart_context[chosen]
    non_false = [(s, st_) for s, st_ in ctx["signals"] if st_ != "False"]
    show_all_statuses = st.checkbox("Invalidated (⚪ False) signals bhi dikhao chart mein", value=False)
    plot_signals = ctx["signals"] if show_all_statuses else non_false

    # trade plan shown for the best available signal: prefer Active, else Pending
    tp, tp_sig = None, None
    active_ones = [(s, st_) for s, st_ in ctx["signals"] if st_ == "Active"]
    pending_ones = [(s, st_) for s, st_ in ctx["signals"] if st_ == "Pending"]
    pick_from = active_ones or pending_ones
    if pick_from:
        tp_sig, _ = max(pick_from, key=lambda pair: pair[0].p2.pos)
        tp = smc.compute_trade_plan(tp_sig, ctx["obs"])

    fig = charting.build_chart(
        ctx["df"], ctx["rsi"], ctx["fvgs"], ctx["obs"], plot_signals,
        trade_plan=tp, title=f"{chosen[0]} — {chosen[1]}",
    )
    st.plotly_chart(fig, use_container_width=True)

    if tp:
        st.caption(
            f"Trade plan **{tp_sig.div_type}** ({tp_sig.bias}) basis: **{tp.basis}** — "
            f"Entry `{tp.entry:.2f}` · SL `{tp.stop_loss:.2f}` · "
            f"T1 `{tp.target1:.2f}` (1.5R) · T2 `{tp.target2:.2f}` (3R). "
            "Yeh suggestion hai, apna risk khud manage karo."
        )
    st.caption(
        "Zones: hara/laal shaded box = Order Block, halka box = FVG. "
        "🟢 Active pivot-line = confirmed reversal thesis abhi valid hai · "
        "🟡 Pending (dotted) = pattern abhi ban raha hai, lock nahi hua · "
        "⚪ False (dotted grey) = invalidate ho chuka."
    )
else:
    st.info("Chart dekhne ke liye pehle 'Scan Now' se kam se kam ek symbol/timeframe scan karo.")

st.caption(
    "Regular Bullish/Bearish = reversal signal. Hidden Bullish/Bearish = trend-continuation signal. "
    "Pivot confirmation me thoda lag hota hai (pivot ke baad N bars chahiye) — yeh normal hai, repaint avoid karne ke liye."
)

with st.expander("ℹ️ Kaise kaam karta hai"):
    st.markdown("""
- **RSI**: Wilder's smoothing method (TradingView jaisa default RSI).
- **Pivot detection**: price mein swing high/low dhoondhta hai (confirmation ke liye kuch bars baad tak wait karta hai).
- **Divergence**: pichle do price pivots (same kind — high/high ya low/low) ko unke corresponding RSI values se compare karta hai.
- **Duplicate suppression**: ek baar alert ho chuka pivot dobara notify nahi hota (`alerted_signals.json` mein track hota hai).
- **Multi-timeframe**: har symbol ko sabhi selected timeframes (5m/15m/1h/1d) par independently scan karta hai.
- **SMC Confluence**: har signal ke pivot price ko teen SMC zones se match karta hai — unmitigated **Order Block**, **FVG (imbalance)**, aur recent **BOS/CHoCH structure** — matching direction (BUY signal ↔ bullish zone, SELL signal ↔ bearish zone). Jitne zone match karein, utna zyada confluence score (0-3). "Sirf SMC-confirmed" option on karne par sirf un signals par hi Telegram alert jayega jinka score threshold se upar ho.
- **Live Mode**: on karne par app har `refresh_secs` seconds mein khud-ba-khud re-scan karta hai.
- **Status (Active/Pending/False)**: 🟢 **Active** = pivot fully confirmed aur reversal thesis abhi tak valid hai. 🟡 **Pending** = pattern abhi ban raha hai (looser, near-real-time confirmation se), lock nahi hua — agle bar(s) mein badal sakta hai. ⚪ **False** = pehle confirm hua tha, lekin baad mein price ne pivot ke ulta break kar diya — thesis invalidate ho gayi.
- **Entry / SL / Targets**: agar signal ke pass ek matching unmitigated Order Block hai, entry/SL usi se liye jaate hain (OB ke edge se) — warna pivot level se. Targets 1.5R aur 3R par (R = entry-SL ka distance). Ye ek suggestion hai, apna risk khud manage karo — 1-2% per trade (khud ka account) ya 0.25-1% (funded account) se zyada risk mat lo.
- **Chart View**: har scanned symbol/timeframe ke liye candlestick + RSI chart, jisme Order Block/FVG zones, divergence pivot-lines (status ke hisaab se color-coded), aur Entry/SL/Target lines overlay hoti hain.
""")

# ---------------------------------------------------------------------------
# Auto-refresh (Live Mode)
# ---------------------------------------------------------------------------
if live_mode:
    st.caption(f"⏳ Agla auto-scan {refresh_secs}s mein...")
    time.sleep(refresh_secs)
    st.rerun()
