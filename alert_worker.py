import os
import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

print("🔥 BOT WORKER LOADED", flush=True)

from signal_engine import (
    get_multi_timeframe_analysis,
    evaluate_signal_engine,
    format_price,
)

TELEGRAM_BOT_TOKEN = os.getenv("8785866877:AAE8QLAQmBT72Azad1QKYFKmtWI6wQdHUqs
")
TELEGRAM_CHAT_ID = os.getenv("1080439188")

SCAN_SYMBOLS = [
    ("forex", "XAU/USD"),
]

SCAN_INTERVAL_SECONDS = 300
STATE_FILE = "bot_state.json"

MAX_SIGNALS_PER_DAY = 3
MIN_SIGNAL_GAP_SECONDS = 3600
OPPOSITE_LOCK_SECONDS = 7200

MIN_AI_SCORE = 85
MIN_RR = 1.0


def utc_now():
    return datetime.now(timezone.utc)


def today_key():
    return utc_now().strftime("%Y-%m-%d")


def active_session_name():
    hour = utc_now().hour

    if 7 <= hour <= 11:
        return "LONDON"
    if 12 <= hour <= 17:
        return "NEW YORK"
    return "OFF_SESSION"


def default_state():
    return {
        "daily_date": today_key(),
        "daily_count": 0,
        "last_signal_time": {},
        "last_signal_side": {},
        "open_trades": {},
        "stats": {
            "signals_sent": 0,
            "closed_trades": 0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "tp1_hits": 0,
            "tp2_hits": 0,
            "tp_large_hits": 0,
        },
    }


def load_state():
    path = Path(STATE_FILE)

    if not path.exists():
        return default_state()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        if data.get("daily_date") != today_key():
            data["daily_date"] = today_key()
            data["daily_count"] = 0

        base = default_state()

        for k, v in base.items():
            if k not in data:
                data[k] = v

        for k, v in base["stats"].items():
            if k not in data["stats"]:
                data["stats"][k] = v

        return data

    except Exception as exc:
        print("load_state error:", exc, flush=True)
        return default_state()


STATE = load_state()


def save_state():
    try:
        Path(STATE_FILE).write_text(json.dumps(STATE, indent=2), encoding="utf-8")
    except Exception as exc:
        print("save_state error:", exc, flush=True)


def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
            },
            timeout=10,
        )
        print("Telegram:", r.status_code, r.text[:150], flush=True)
    except Exception as exc:
        print("Telegram error:", exc, flush=True)


def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def trade_key(market, symbol):
    return f"{market}:{symbol}"


def calc_rr(signal):
    entry = safe_float(signal.get("entry_price"))
    sl = safe_float(signal.get("sl_price"))
    tp1 = safe_float(signal.get("tp1"))
    side = signal.get("preferred_side")

    if side == "BUY" and entry > sl:
        return (tp1 - entry) / max(entry - sl, 1e-9)

    if side == "SELL" and sl > entry:
        return (entry - tp1) / max(sl - entry, 1e-9)

    return 0.0


def build_ai_score(signal, session):
    if signal.get("signal_type") not in ["BUY ENTRY READY", "SELL ENTRY READY"]:
        return 0, 0, 0.0

    base = safe_float(signal.get("signal_score"), 80)
    triggers = int(signal.get("trigger_count", 1))
    rr = calc_rr(signal)

    if session == "LONDON":
        base += 6
    elif session == "NEW YORK":
        base += 8
    else:
        base -= 5

    if rr >= 1.0:
        base += 4
    if rr >= 1.5:
        base += 4
    if rr >= 2.0:
        base += 4

    return min(int(base), 100), triggers, rr


def build_stats_message():
    s = STATE["stats"]
    closed = s["closed_trades"]
    winrate = (s["wins"] / closed * 100) if closed > 0 else 0.0

    return (
        f"📊 LIVE PERFORMANCE\n"
        f"Closed Trades: {s['closed_trades']}\n"
        f"Wins: {s['wins']}\n"
        f"Losses: {s['losses']}\n"
        f"Break-even: {s['breakeven']}\n"
        f"TP1 Hits: {s['tp1_hits']}\n"
        f"TP2 Hits: {s['tp2_hits']}\n"
        f"TP Large Hits: {s['tp_large_hits']}\n"
        f"Winrate: {winrate:.1f}%"
    )


def build_signal_message(market, symbol, signal, ai_score, session, triggers, rr):
    return (
        f"🔥 {signal['signal_type']}\n\n"
        f"Market: {market.upper()} | Symbol: {symbol}\n"
        f"Session: {session}\n"
        f"Direction: {signal.get('preferred_side', '-')}\n"
        f"Mode: {signal.get('setup_mode', '-')}\n"
        f"AI Score: {ai_score}\n"
        f"Triggers: {triggers}\n"
        f"RR: {rr:.2f}\n\n"
        f"Entry: {format_price(signal.get('entry_price'))}\n"
        f"SL: {format_price(signal.get('sl_price'))}\n"
        f"TP1: {format_price(signal.get('tp1'))}\n"
        f"TP2: {format_price(signal.get('tp2'))}\n"
        f"TP Large: {format_price(signal.get('tp_large'))}\n\n"
        f"FVG: {'YES' if signal.get('fvg') else 'NO'}\n"
        f"OB: {'YES' if signal.get('ob') else 'NO'}\n"
        f"Sweep: {'YES' if signal.get('sweep') else 'NO'}\n"
        f"BOS: {'YES' if signal.get('bos') else 'NO'}\n"
        f"CHOCH: {'YES' if signal.get('choch') else 'NO'}\n"
        f"Magnet: {signal.get('magnet', '-')}"
    )


def register_trade(market, symbol, signal):
    key = trade_key(market, symbol)

    STATE["open_trades"][key] = {
        "market": market,
        "symbol": symbol,
        "side": signal["preferred_side"],
        "entry": safe_float(signal["entry_price"]),
        "sl": safe_float(signal["sl_price"]),
        "tp1": safe_float(signal["tp1"]),
        "tp2": safe_float(signal["tp2"]),
        "tp_large": safe_float(signal["tp_large"]),
        "tp1_sent": False,
        "tp2_sent": False,
        "tp_large_sent": False,
        "closed": False,
        "created_at": int(time.time()),
    }

    save_state()


def can_send_new_signal(market, symbol, signal, ai_score, rr):
    if signal.get("signal_type") not in ["BUY ENTRY READY", "SELL ENTRY READY"]:
        return False, "No confirmed entry"

    if ai_score < MIN_AI_SCORE:
        return False, "AI score low"

    if rr < MIN_RR:
        return False, "RR low"

    if STATE["daily_count"] >= MAX_SIGNALS_PER_DAY:
        return False, "Daily max reached"

    key = trade_key(market, symbol)
    now_ts = time.time()

    open_trade = STATE["open_trades"].get(key)
    if open_trade and not open_trade.get("closed"):
        return False, "Trade already open"

    last_time = STATE["last_signal_time"].get(key, 0)
    last_side = STATE["last_signal_side"].get(key)
    side = signal.get("preferred_side")

    if now_ts - last_time < MIN_SIGNAL_GAP_SECONDS:
        return False, "Cooldown"

    if last_side and last_side != side and now_ts - last_time < OPPOSITE_LOCK_SECONDS:
        return False, "Opposite locked"

    return True, "OK"


def maybe_update_open_trade(market, symbol, price):
    key = trade_key(market, symbol)
    trade = STATE["open_trades"].get(key)

    if not trade or trade.get("closed"):
        return

    side = trade["side"]

    if side == "BUY":
        if not trade["tp1_sent"] and price >= trade["tp1"]:
            trade["tp1_sent"] = True
            trade["sl"] = trade["entry"]
            STATE["stats"]["tp1_hits"] += 1
            send_telegram(
                f"🎯 TP1 HIT\n\n{symbol} BUY\nSL moved to Break-even.\n\n"
                + build_stats_message()
            )

        if not trade["tp2_sent"] and price >= trade["tp2"]:
            trade["tp2_sent"] = True
            STATE["stats"]["tp2_hits"] += 1
            trade["sl"] = max(trade["sl"], trade["tp1"])
            send_telegram(
                f"🚀 TP2 HIT\n\n{symbol} BUY\nSL trailed to TP1.\n\n"
                + build_stats_message()
            )

        if not trade["tp_large_sent"] and price >= trade["tp_large"]:
            trade["tp_large_sent"] = True
            trade["closed"] = True
            STATE["stats"]["tp_large_hits"] += 1
            STATE["stats"]["wins"] += 1
            STATE["stats"]["closed_trades"] += 1
            send_telegram(
                f"🏁 TP LARGE HIT\n\n{symbol} BUY\n\n"
                + build_stats_message()
            )

        if not trade["closed"] and price <= trade["sl"]:
            trade["closed"] = True
            STATE["stats"]["closed_trades"] += 1

            if trade["tp1_sent"]:
                STATE["stats"]["breakeven"] += 1
                send_telegram(
                    f"🔁 BREAK EVEN EXIT\n\n{symbol} BUY\n\n"
                    + build_stats_message()
                )
            else:
                STATE["stats"]["losses"] += 1
                send_telegram(
                    f"❌ STOP LOSS HIT\n\n{symbol} BUY\n\n"
                    + build_stats_message()
                )

    if side == "SELL":
        if not trade["tp1_sent"] and price <= trade["tp1"]:
            trade["tp1_sent"] = True
            trade["sl"] = trade["entry"]
            STATE["stats"]["tp1_hits"] += 1
            send_telegram(
                f"🎯 TP1 HIT\n\n{symbol} SELL\nSL moved to Break-even.\n\n"
                + build_stats_message()
            )

        if not trade["tp2_sent"] and price <= trade["tp2"]:
            trade["tp2_sent"] = True
            STATE["stats"]["tp2_hits"] += 1
            trade["sl"] = min(trade["sl"], trade["tp1"])
            send_telegram(
                f"🚀 TP2 HIT\n\n{symbol} SELL\nSL trailed to TP1.\n\n"
                + build_stats_message()
            )

        if not trade["tp_large_sent"] and price <= trade["tp_large"]:
            trade["tp_large_sent"] = True
            trade["closed"] = True
            STATE["stats"]["tp_large_hits"] += 1
            STATE["stats"]["wins"] += 1
            STATE["stats"]["closed_trades"] += 1
            send_telegram(
                f"🏁 TP LARGE HIT\n\n{symbol} SELL\n\n"
                + build_stats_message()
            )

        if not trade["closed"] and price >= trade["sl"]:
            trade["closed"] = True
            STATE["stats"]["closed_trades"] += 1

            if trade["tp1_sent"]:
                STATE["stats"]["breakeven"] += 1
                send_telegram(
                    f"🔁 BREAK EVEN EXIT\n\n{symbol} SELL\n\n"
                    + build_stats_message()
                )
            else:
                STATE["stats"]["losses"] += 1
                send_telegram(
                    f"❌ STOP LOSS HIT\n\n{symbol} SELL\n\n"
                    + build_stats_message()
                )

    save_state()


def run():
    print("🔥 BOT RUNNING", flush=True)

    while True:
        try:
            session = active_session_name()
            print("⏳ checking market...", flush=True)
            print("Current session:", session, flush=True)

            if STATE.get("daily_date") != today_key():
                STATE["daily_date"] = today_key()
                STATE["daily_count"] = 0
                save_state()

            for market, symbol in SCAN_SYMBOLS:
                print(f"Scanning {market} {symbol} ...", flush=True)

                mtf = get_multi_timeframe_analysis(market, symbol)
                signal = evaluate_signal_engine(mtf)

                print("DEBUG SIGNAL:", symbol, signal, flush=True)

                price = safe_float(signal.get("trigger_price"))
                if price:
                    maybe_update_open_trade(market, symbol, price)

                ai_score, triggers, rr = build_ai_score(signal, session)

                allowed, reason = can_send_new_signal(
                    market, symbol, signal, ai_score, rr
                )

                if not allowed:
                    print(symbol, "blocked:", reason, flush=True)
                    continue

                send_telegram(
                    build_signal_message(
                        market, symbol, signal, ai_score, session, triggers, rr
                    )
                )

                key = trade_key(market, symbol)
                STATE["last_signal_time"][key] = int(time.time())
                STATE["last_signal_side"][key] = signal.get("preferred_side")
                STATE["daily_count"] += 1
                STATE["stats"]["signals_sent"] += 1

                register_trade(market, symbol, signal)

                save_state()
                print("✅ SIGNAL SENT:", symbol, flush=True)

            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as exc:
            print("Worker loop error:", exc, flush=True)
            time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
