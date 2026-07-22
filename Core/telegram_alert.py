# -*- coding: utf-8 -*-
"""Minimal Telegram Bot API wrapper for sending divergence alerts."""

import requests


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> tuple[bool, str]:
    if not bot_token or not chat_id:
        return False, "Bot token / chat ID missing"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(
            url,
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=8,
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            return True, "sent"
        return False, f"Telegram API error: {resp.status_code} {resp.text[:200]}"
    except Exception as e:
        return False, f"Network/Telegram error: {e}"


def format_alert(signal, market_label: str, confluence=None) -> str:
    arrow = "🟢 BUY" if signal.bias == "BUY" else "🔴 SELL"
    msg = (
        f"<b>Satya Trading — RSI Divergence Alert</b>\n"
        f"{arrow}  |  <b>{signal.div_type}</b>\n"
        f"Symbol: <b>{market_label}</b>\n"
        f"Timeframe: <b>{signal.timeframe}</b>\n"
        f"Pivot: {signal.p1.timestamp} → {signal.p2.timestamp}\n"
        f"Price: {signal.p1.price:.2f} → {signal.p2.price:.2f}\n"
        f"RSI: {signal.p1.rsi:.1f} → {signal.p2.rsi:.1f}\n"
    )
    if confluence is not None:
        msg += f"SMC: <b>{confluence.label}</b>\n"
        for tag in confluence.tags:
            msg += f"  • {tag}\n"
    return msg
