# Satya Trading — Multi-Timeframe RSI Divergence Notifier

Live-market RSI divergence scanner for **NIFTY 50, BANK NIFTY, SENSEX, NIFTY FIN SERVICE**
aur NSE stocks — 5m / 15m / 1h / 1d timeframes par ek saath, Telegram alerts
ke saath, aur duplicate-alert suppression.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

Browser mein `http://localhost:8501` khul jayega.

## Telegram alerts setup (optional)

1. Telegram par **@BotFather** ko message karo → `/newbot` → bot token milega.
2. Apne bot ko ek message bhejo, phir `https://api.telegram.org/bot<TOKEN>/getUpdates`
   khol ke apna **chat_id** nikaal lo.
3. App ke sidebar mein "Enable Telegram alerts" on karo, bot token + chat ID daalo.

## Kya detect hota hai

| Type | Price | RSI | Matlab |
|---|---|---|---|
| Regular Bearish | Higher High | Lower High | Reversal down (SELL) |
| Regular Bullish | Lower Low | Higher Low | Reversal up (BUY) |
| Hidden Bearish | Lower High | Higher High | Trend-continuation down (SELL) |
| Hidden Bullish | Higher Low | Lower Low | Trend-continuation up (BUY) |

## Indices covered

**Broad**: NIFTY 50, BANK NIFTY, SENSEX, NIFTY FIN SERVICE, NIFTY MIDCAP 100
**Sectoral**: NIFTY IT, NIFTY AUTO, NIFTY PHARMA, NIFTY FMCG, NIFTY METAL,
NIFTY ENERGY, NIFTY REALTY, NIFTY PSU BANK, NIFTY MEDIA, NIFTY INFRA

Sabhi `core/config.py` → `INDEX_SYMBOLS` mein defined hain. Kuch sectoral index
tickers data-provider ke hisaab se badal sakte hain — agar koi symbol live fetch
nahi hota, app us symbol ke liye automatically synthetic demo data par switch
ho jata hai (crash nahi hoga), UI mein badge dikh jayega.

## SMC Confluence

Har RSI divergence signal ko teen SMC zones ke against check kiya jata hai
(matching direction — BUY signal ↔ bullish zone, SELL signal ↔ bearish zone):

1. **Order Block** — unmitigated bullish/bearish OB jiske andar pivot price aata ho
2. **FVG (Fair Value Gap)** — recent imbalance zone jo pivot price ko overlap kare
3. **BOS/CHoCH structure** — sabse recent structure break/reversal jiski direction match kare

Jitne zone match karein, utna confluence score (0-3):
- 🟢🟢 **Strong** (score ≥ 2)
- 🟡 **Partial** (score = 1)
- **—** (score = 0, sirf RSI divergence, koi SMC backing nahi)

Sidebar se "Sirf SMC-confirmed signals par alert bhejo" on karke Telegram alerts
ko sirf un signals tak limit kar sakte ho jinka confluence score ek threshold
se upar ho.

## Duplicate-alert persistence (important for cloud deploy)

Local file (`alerted_signals.json`) sirf tab tak reliable hai jab tak app
apne hi computer par chal rahi ho. **Streamlit Community Cloud** ka
filesystem ephemeral hai — jab app sleep se wake hoti hai ya redeploy hoti
hai, local file reset ho sakti hai, aur koi ek signal dobara alert ho sakta hai.

Isko permanently fix karne ke liye app ab **GitHub Gist** ko bhi persistent
store ke roop mein support karta hai:

1. GitHub → profile photo → **Settings** → **Developer settings** →
   **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**
2. Sirf **`gist`** scope tick karo, generate karo, token copy kar lo
   (yeh sirf ek baar dikhta hai)
3. App ke sidebar mein **"💾 Alert Persistence"** section kholo, token paste
   karo, Gist ID khaali chodo, **"🆕 Naya alert-store Gist banao"** dabao
4. Milne wale Gist ID ko — best practice ke taur par — Streamlit Cloud
   **App Settings → Secrets** mein is format mein save kar do:
   ```
   GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"
   GIST_ID = "abc123..."
   ```
   Isse har baar sidebar mein token/gist ID daalne ki zaroorat nahi rahegi,
   aur dedup permanently persist hoga — restart/redeploy ke baad bhi.

Agar token/Gist configure nahi karte, app automatically local-file fallback
par chalta rahega (local runs ke liye theek hai, cloud ke liye nahi).

## Notes

- Data **yfinance** se aata hai. Agar kabhi yfinance/internet fail ho jaye, app
  automatically **synthetic demo data** par switch ho jata hai (UI mein clearly
  "SYNTHETIC DEMO" badge dikhega) — taaki app kabhi crash na ho.
- `alerted_signals.json` file mein already-alerted pivots track hote hain, taaki
  ek hi divergence baar-baar notify na ho.
- yfinance intraday data limits: 5m/15m ~ last 60 din, 1h ~ last 730 din, 1d ~ full history.
- Live Mode on karne par app har N seconds mein khud re-scan karta hai (sidebar
  se interval set karo).

## File structure

```
app.py                     — Streamlit UI + scan loop
core/config.py              — watchlist, timeframes, RSI/pivot params
core/indicators.py           — Wilder RSI
core/divergence.py           — pivot detection + divergence classification
core/data.py                  — yfinance fetch + synthetic fallback
core/smc.py                    — FVG, Order Block, BOS/CHoCH structure + confluence scoring
core/telegram_alert.py         — Telegram Bot API sender
core/persistence.py             — duplicate-alert suppression (GitHub Gist, with local-file fallback)
```

---
*Satya Trading — SMC/ICT trading tools series. Sirf educational use ke liye; trading mein risk hai.*
