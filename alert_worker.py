import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

print("🔥 BOT FILE LOADED", flush=True)

from signal_engine import get_multi_timeframe_analysis, evaluate_signal_engine, format_price

TELEGRAM_BOT_TOKEN = "8785866877:AAEDOXABhORr4Y9WCsZ3amoAGDksz-rkul0"
TELEGRAM_CHAT_ID = "-1003990959199"

SCAN_SYMBOLS = [
    ("forex", "XAU/USD"),
]

SCAN_INTERVAL_SECONDS = 300
MAX_SIGNALS_PER_DAY = 3
MIN_SIGNAL_GAP_SECONDS = 5400
OPPOSITE_LOCK_SECONDS = 14400
STATE_FILE = "bot_state.json"

MIN_AI_SCORE_MAIN = 75
MIN_AI_SCORE_OFF = 85


def utc_now():
    return datetime.now(timezone.utc)


def today_key():
    return utc_now().strftime("%Y-%m-%d")


def default_state():
    return {
        "daily_date": today_key(),
        "daily_count": 0,
        "last_signal_time": {},
        "last_signal_side": {},
        "last_signal_score": {},
        "open_trades": {},
        "stats": {
            "signals_sent": 0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "tp1_hits": 0,
            "tp2_hits": 0,
            "tp_large_hits": 0,
            "closed_trades": 0,
            "extended_trades": 0,
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

        stats_defaults = default_state()["stats"]
        stats = data.get("stats", {})
        for k, v in stats_defaults.items():
            if k not in stats:
                stats[k] = v
        data["stats"] = stats

        if "open_trades" not in data:
            data["open_trades"] = {}

        return data
    except Exception as exc:
        print("load_state error:", exc, flush=True)
        return default_state()


def save_state():
    try:
        Path(STATE_FILE).write_text(json.dumps(STATE, indent=2), encoding="utf-8")
    except Exception as exc:
        print("save_state error:", exc, flush=True)


STATE = load_state()


def active_session_name():
    hour = utc_now().hour
    if 7 <= hour <= 11:
        return "LONDON"
    if 12 <= hour <= 17:
        return "NEW YORK"
    return "OFF_SESSION"


def avoid_news_window():
    minute = utc_now().minute
    return minute in [25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 55, 56, 57, 58, 59, 0, 1, 2, 3, 4, 5]


def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "DEIN_TELEGRAM_TOKEN_HIER":
        print("Telegram token missing.", flush=True)
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
        print("Telegram:", r.status_code, r.text[:120], flush=True)
    except Exception as exc:
        print("Telegram error:", exc, flush=True)


def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def trade_key(market: str, symbol: str):
    return f"{market}:{symbol}"


def build_ai_score(signal: dict, session: str):
    if signal.get("signal_type") not in ["BUY ENTRY READY", "SELL ENTRY READY"]:
        return 0, 0, 0.0

    base = safe_float(signal.get("signal_score"), 0.0)
    mode = signal.get("setup_mode", "NONE")

    if mode == "PRO":
        triggers = 4
        base += 12
    elif mode == "ACTIVE":
        triggers = 2
        base += 4
    else:
        triggers = 1

    if session == "LONDON":
        base += 8
    elif session == "NEW YORK":
        base += 10
    else:
        base += 2

    entry = safe_float(signal.get("entry_price"))
    sl = safe_float(signal.get("sl_price"))
    tp1 = safe_float(signal.get("tp1"))
    side = signal.get("preferred_side", "WAIT")

    rr = 0.0
    if side == "BUY" and entry > sl:
        rr = (tp1 - entry) / max(entry - sl, 1e-9)
    elif side == "SELL" and sl > entry:
        rr = (entry - tp1) / max(sl - entry, 1e-9)

    if rr >= 1.0:
        base += 5
    if rr >= 1.5:
        base += 5

    return min(int(base), 100), triggers, rr


def build_signal_message(market: str, symbol: str, signal: dict, ai_score: int, session: str, trigger_count: int, rr: float):
    mode = signal.get("setup_mode", "-")
    icon = "🔥" if mode == "PRO" else "⚡"

    return (
        f"{icon} {signal['signal_type']}\n\n"
        f"Market: {market.upper()} | Symbol: {symbol}\n"
        f"Session: {session}\n"
        f"Direction: {signal.get('preferred_side', '-')}\n"
        f"Mode: {mode}\n"
        f"AI Score: {ai_score}\n"
        f"Triggers: {trigger_count}\n"
        f"RR: {rr:.2f}\n\n"
        f"Entry: {format_price(signal.get('entry_price'))}\n"
        f"SL: {format_price(signal.get('sl_price'))}\n"
        f"TP1: {format_price(signal.get('tp1'))}\n"
        f"TP2: {format_price(signal.get('tp2'))}\n"
        f"TP Large: {format_price(signal.get('tp_large'))}"
    )


def send_live_performance(result_label: str):
    s = STATE["stats"]
    closed = s["closed_trades"]
    winrate = (s["wins"] / closed * 100) if closed > 0 else 0.0

    msg = (
        f"{result_label}\n\n"
        f"📊 LIVE PERFORMANCE\n"
        f"Closed Trades: {closed}\n"
        f"Wins: {s['wins']}\n"
        f"Losses: {s['losses']}\n"
        f"Break-even: {s['breakeven']}\n"
        f"TP1 Hits: {s['tp1_hits']}\n"
        f"TP2 Hits: {s['tp2_hits']}\n"
        f"TP Large Hits: {s['tp_large_hits']}\n"
        f"Winrate: {winrate:.1f}%"
    )
    send_telegram(msg)


def build_stats_message():
    s = STATE["stats"]
    winrate = (s["wins"] / s["closed_trades"] * 100) if s["closed_trades"] > 0 else 0.0
    return (
        f"📊 BOT STATS\n"
        f"Signals Sent: {s['signals_sent']}\n"
        f"Closed Trades: {s['closed_trades']}\n"
        f"Wins: {s['wins']}\n"
        f"Losses: {s['losses']}\n"
        f"Break-even: {s['breakeven']}\n"
        f"TP1 Hits: {s['tp1_hits']}\n"
        f"TP2 Hits: {s['tp2_hits']}\n"
        f"TP Large Hits: {s['tp_large_hits']}\n"
        f"Extended Trades: {s['extended_trades']}\n"
        f"Winrate: {winrate:.1f}%"
    )


def send_stats():
    send_telegram(build_stats_message())


def register_open_trade(market: str, symbol: str, signal: dict, ai_score: int):
    key = trade_key(market, symbol)
    entry = safe_float(signal.get("entry_price"))
    sl = safe_float(signal.get("sl_price"))
    tp1 = safe_float(signal.get("tp1"))
    tp2 = safe_float(signal.get("tp2"))
    tp_large = safe_float(signal.get("tp_large"))

    STATE["open_trades"][key] = {
        "market": market,
        "symbol": symbol,
        "side": signal["preferred_side"],
        "mode": signal.get("setup_mode", "NONE"),
        "entry": entry,
        "initial_sl": sl,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp_large": tp_large,
        "initial_tp_large": tp_large,
        "ai_score": ai_score,
        "created_at": int(time.time()),
        "tp1_sent": False,
        "tp2_sent": False,
        "tp_large_sent": False,
        "be_moved": False,
        "extended_count": 0,
        "closed": False,
    }
    save_state()


def maybe_extend_trade(trade: dict, signal: dict):
    if trade["extended_count"] >= 2:
        return False

    price = safe_float(signal.get("trigger_price"))
    side = trade["side"]

    if side == "BUY" and price > trade["tp2"]:
        old_tp = trade["tp_large"]
        new_tp = max(old_tp, price + (price - trade["entry"]) * 0.8)
        if new_tp > old_tp:
            trade["tp_large"] = new_tp
            trade["sl"] = max(trade["sl"], price - price * 0.002)
            trade["extended_count"] += 1
            STATE["stats"]["extended_trades"] += 1
            return True

    if side == "SELL" and price < trade["tp2"]:
        old_tp = trade["tp_large"]
        new_tp = min(old_tp, price - (trade["entry"] - price) * 0.8)
        if new_tp < old_tp:
            trade["tp_large"] = new_tp
            trade["sl"] = min(trade["sl"], price + price * 0.002)
            trade["extended_count"] += 1
            STATE["stats"]["extended_trades"] += 1
            return True

    return False


def maybe_update_open_trade(market: str, symbol: str, signal: dict):
    key = trade_key(market, symbol)
    trade = STATE["open_trades"].get(key)
    if not trade or trade.get("closed"):
        return

    price_raw = signal.get("trigger_price")
    if price_raw is None:
        return

    price = safe_float(price_raw)
    side = trade["side"]

    if side == "BUY" and not trade["tp1_sent"] and price >= trade["tp1"]:
        trade["tp1_sent"] = True
        trade["sl"] = trade["entry"]
        trade["be_moved"] = True
        STATE["stats"]["tp1_hits"] += 1
        send_telegram(
            f"🎯 TP1 HIT\n\n"
            f"{symbol} BUY\n"
            f"Small profit secured.\n"
            f"SL moved to Break Even."
        )

    if side == "SELL" and not trade["tp1_sent"] and price <= trade["tp1"]:
        trade["tp1_sent"] = True
        trade["sl"] = trade["entry"]
        trade["be_moved"] = True
        STATE["stats"]["tp1_hits"] += 1
        send_telegram(
            f"🎯 TP1 HIT\n\n"
            f"{symbol} SELL\n"
            f"Small profit secured.\n"
            f"SL moved to Break Even."
        )

    if side == "BUY" and not trade["tp2_sent"] and price >= trade["tp2"]:
        trade["tp2_sent"] = True
        STATE["stats"]["tp2_hits"] += 1
        trade["sl"] = max(trade["sl"], price - price * 0.002)
        send_telegram(
            f"🚀 TP2 HIT\n\n"
            f"{symbol} BUY\n"
            f"Trade still running.\n"
            f"SL trailed to: {format_price(trade['sl'])}"
        )

    if side == "SELL" and not trade["tp2_sent"] and price <= trade["tp2"]:
        trade["tp2_sent"] = True
        STATE["stats"]["tp2_hits"] += 1
        trade["sl"] = min(trade["sl"], price + price * 0.002)
        send_telegram(
            f"🚀 TP2 HIT\n\n"
            f"{symbol} SELL\n"
            f"Trade still running.\n"
            f"SL trailed to: {format_price(trade['sl'])}"
        )

    if trade["tp2_sent"] and not trade["closed"]:
        extended = maybe_extend_trade(trade, signal)
        if extended:
            send_telegram(
                f"🔁 TRADE UPDATE\n\n"
                f"{symbol} {side}\n"
                f"Market keeps running.\n"
                f"New TP Large: {format_price(trade['tp_large'])}\n"
                f"New SL: {format_price(trade['sl'])}"
            )

    if side == "BUY" and not trade["tp_large_sent"] and price >= trade["tp_large"]:
        trade["tp_large_sent"] = True
        trade["closed"] = True
        STATE["stats"]["tp_large_hits"] += 1
        STATE["stats"]["wins"] += 1
        STATE["stats"]["closed_trades"] += 1
        send_live_performance(f"🏁 TP LARGE HIT\n\n{symbol} BUY")

    if side == "SELL" and not trade["tp_large_sent"] and price <= trade["tp_large"]:
        trade["tp_large_sent"] = True
        trade["closed"] = True
        STATE["stats"]["tp_large_hits"] += 1
        STATE["stats"]["wins"] += 1
        STATE["stats"]["closed_trades"] += 1
        send_live_performance(f"🏁 TP LARGE HIT\n\n{symbol} SELL")

    if side == "BUY" and not trade["closed"] and price <= trade["sl"]:
        trade["closed"] = True
        STATE["stats"]["closed_trades"] += 1
        if trade["tp1_sent"]:
            STATE["stats"]["breakeven"] += 1
            send_live_performance(f"🔁 BREAK EVEN EXIT\n\n{symbol} BUY")
        else:
            STATE["stats"]["losses"] += 1
            send_live_performance(f"❌ STOP LOSS HIT\n\n{symbol} BUY")

    if side == "SELL" and not trade["closed"] and price >= trade["sl"]:
        trade["closed"] = True
        STATE["stats"]["closed_trades"] += 1
        if trade["tp1_sent"]:
            STATE["stats"]["breakeven"] += 1
            send_live_performance(f"🔁 BREAK EVEN EXIT\n\n{symbol} SELL")
        else:
            STATE["stats"]["losses"] += 1
            send_live_performance(f"❌ STOP LOSS HIT\n\n{symbol} SELL")

    save_state()


def can_send_new_signal(market: str, symbol: str, signal: dict, ai_score: int, trigger_count: int, rr: float):
    if signal.get("signal_type") not in ["BUY ENTRY READY", "SELL ENTRY READY"]:
        return False, "No confirmed entry"

    if avoid_news_window():
        return False, "News blocked"

    session = active_session_name()

    if session in ["LONDON", "NEW YORK"]:
        if rr < 1.0:
            return False, "RR low"
        if ai_score < MIN_AI_SCORE_MAIN:
            return False, "AI too low"
    else:
        if rr < 1.0:
            return False, "RR low off session"
        if ai_score < MIN_AI_SCORE_OFF:
            return False, "AI too low off session"

    if STATE["daily_count"] >= MAX_SIGNALS_PER_DAY:
        return False, "Daily max reached"

    key = trade_key(market, symbol)
    now_ts = time.time()
    last_time = STATE["last_signal_time"].get(key, 0)
    last_side = STATE["last_signal_side"].get(key)
    last_score = STATE["last_signal_score"].get(key, 0)
    current_side = signal.get("preferred_side")

    if now_ts - last_time < MIN_SIGNAL_GAP_SECONDS:
        return False, "Cooldown"

    if last_side and last_side != current_side and now_ts - last_time < OPPOSITE_LOCK_SECONDS:
        return False, "Opposite locked"

    if last_side == current_side and ai_score <= last_score + 5:
        return False, "Not stronger"

    open_trade = STATE["open_trades"].get(key)
    if open_trade and not open_trade.get("closed"):
        return False, "Trade already open"

    return True, "OK"


def run():
    print("🔥 BOT HYBRID RUNNING", flush=True)

    while True:
        try:
            print("⏳ checking market...", flush=True)
            session = active_session_name()
            print("Current session:", session, flush=True)

            if STATE.get("daily_date") != today_key():
                STATE["daily_date"] = today_key()
                STATE["daily_count"] = 0
                save_state()
                print("Daily reset done.", flush=True)

            for market, symbol in SCAN_SYMBOLS:
                try:
                    print(f"Scanning {market} {symbol} ...", flush=True)

                    mtf = get_multi_timeframe_analysis(market, symbol)
                    signal = evaluate_signal_engine(mtf)

                    print("DEBUG SIGNAL:", symbol, signal, flush=True)

                    maybe_update_open_trade(market, symbol, signal)

                    ai_score, trigger_count, rr = build_ai_score(signal, session)
                    print(f"DEBUG SCORE: {symbol} ai={ai_score} triggers={trigger_count} rr={rr:.2f}", flush=True)

                    allowed, reason = can_send_new_signal(market, symbol, signal, ai_score, trigger_count, rr)
                    if not allowed:
                        print(symbol, "blocked:", reason, flush=True)
                        continue

                    send_telegram(build_signal_message(market, symbol, signal, ai_score, session, trigger_count, rr))

                    key = trade_key(market, symbol)
                    STATE["last_signal_time"][key] = int(time.time())
                    STATE["last_signal_side"][key] = signal.get("preferred_side")
                    STATE["last_signal_score"][key] = ai_score
                    STATE["daily_count"] += 1
                    STATE["stats"]["signals_sent"] += 1

                    register_open_trade(market, symbol, signal, ai_score)

                    if STATE["stats"]["signals_sent"] % 3 == 0:
                        send_stats()

                    save_state()
                    print("✅ SIGNAL SENT:", symbol, flush=True)

                except Exception as exc:
                    print("Worker symbol error:", symbol, exc, flush=True)

            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as exc:
            print("Worker loop error:", exc, flush=True)
            time.sleep(SCAN_INTERVAL_SECONDS)


if name == "__main__":
    send_telegram("TEST BOT MESSAGE")
    run()
