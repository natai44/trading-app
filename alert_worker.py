import json
import time
import requests
from datetime import datetime, timezone

from signal_engine import get_multi_timeframe_analysis, evaluate_signal_engine, format_price

TELEGRAM_BOT_TOKEN = "8785866877:AAHM-tze7VEOWcxGGcsVg0dWadheZX_Bhlw"
TELEGRAM_CHAT_ID = "1080439188"

SCAN_SYMBOLS = [
    ("crypto", "BTCUSDT"),
    ("forex", "XAU/USD"),
]

SCAN_INTERVAL_SECONDS = 90
MAX_SIGNALS_PER_DAY = 2
MIN_SIGNAL_GAP_SECONDS = 5400
OPPOSITE_LOCK_SECONDS = 14400
MIN_AI_SCORE = 88
STATE_FILE = "bot_state.json"


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
            "wins": 0,
            "losses": 0,
            "tp1_hits": 0,
            "tp2_hits": 0,
            "break_even_hits": 0,
            "signals_sent": 0,
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
        return data
    except Exception:
        return default_state()


def save_state(state):
    Path(STATE_FILE).write_text(json.dumps(state, indent=2), encoding="utf-8")


STATE = load_state()


def active_session_name():
    hour = utc_now().hour
    if 7 <= hour <= 11:
        return "LONDON"
    if 12 <= hour <= 17:
        return "NEW YORK"
    return None


def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "PUT_YOUR_NEW_TELEGRAM_TOKEN_HERE":
        print("Telegram token missing.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=8)
        print("Telegram:", r.status_code, r.text[:200])
    except Exception as exc:
        print("Telegram error:", exc)


def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def count_yes(*values):
    return sum(1 for v in values if str(v).upper() == "YES")


def build_ai_score(signal: dict, session: str):
    side = signal.get("preferred_side", "WAIT")
    base = 0

    if signal.get("signal_type") in ["BUY ENTRY READY", "SELL ENTRY READY"]:
        base += 35

    if signal.get("signal_status") in ["CONFIRMED BUY", "CONFIRMED SELL"]:
        base += 15

    if side == "BUY":
        trigger_count = count_yes(signal.get("buy_fvg"), signal.get("buy_ob"), signal.get("buy_sweep"))
        if signal.get("stronger_magnet") == "UP":
            trigger_count += 1
        if signal.get("fib_618") not in [None, "-"]:
            trigger_count += 1
    elif side == "SELL":
        trigger_count = count_yes(signal.get("sell_fvg"), signal.get("sell_ob"), signal.get("sell_sweep"))
        if signal.get("stronger_magnet") == "DOWN":
            trigger_count += 1
        if signal.get("fib_618") not in [None, "-"]:
            trigger_count += 1
    else:
        trigger_count = 0

    base += trigger_count * 8

    if session == "LONDON":
        base += 8
    elif session == "NEW YORK":
        base += 10

    tp1 = safe_float(signal.get("tp1"))
    entry = safe_float(signal.get("entry_price"))
    sl = safe_float(signal.get("sl_price"))
    rr = 0.0

    if signal.get("preferred_side") == "BUY" and entry > sl:
        rr = (tp1 - entry) / max(entry - sl, 1e-9)
    elif signal.get("preferred_side") == "SELL" and sl > entry:
        rr = (entry - tp1) / max(sl - entry, 1e-9)

    if rr >= 1.5:
        base += 10
    elif rr >= 1.0:
        base += 6

    raw_score = safe_float(signal.get("signal_score"))
    base += min(int(raw_score / 8), 12)

    return min(base, 100), trigger_count, rr


def build_signal_message(market: str, symbol: str, signal: dict, ai_score: int, session: str, trigger_count: int, rr: float):
    return (
        f"🔥 {signal['signal_type']}\n\n"
        f"Market: {market.upper()} | Symbol: {symbol}\n"
        f"Session: {session}\n"
        f"Direction: {signal.get('preferred_side', '-')}\n"
        f"AI Score: {ai_score}\n"
        f"Triggers: {trigger_count}\n"
        f"RR: {rr:.2f}\n\n"
        f"Entry: {format_price(signal.get('entry_price'))}\n"
        f"SL: {format_price(signal.get('sl_price'))}\n"
        f"TP1: {format_price(signal.get('tp1'))}\n"
        f"TP2: {format_price(signal.get('tp2'))}\n"
        f"TP Large: {format_price(signal.get('tp_large'))}\n\n"
        f"Magnet: {signal.get('stronger_magnet', '-')}\n"
        f"FVG: {signal.get('buy_fvg') if signal.get('preferred_side') == 'BUY' else signal.get('sell_fvg')}\n"
        f"OB: {signal.get('buy_ob') if signal.get('preferred_side') == 'BUY' else signal.get('sell_ob')}\n"
        f"Sweep: {signal.get('buy_sweep') if signal.get('preferred_side') == 'BUY' else signal.get('sell_sweep')}\n"
    )


def trade_key(market: str, symbol: str):
    return f"{market}:{symbol}"


def register_open_trade(market: str, symbol: str, signal: dict, ai_score: int):
    key = trade_key(market, symbol)
    STATE["open_trades"][key] = {
        "market": market,
        "symbol": symbol,
        "side": signal["preferred_side"],
        "entry": safe_float(signal.get("entry_price")),
        "sl": safe_float(signal.get("sl_price")),
        "tp1": safe_float(signal.get("tp1")),
        "tp2": safe_float(signal.get("tp2")),
        "tp_large": safe_float(signal.get("tp_large")),
        "ai_score": ai_score,
        "created_at": int(time.time()),
        "tp1_sent": False,
        "tp2_sent": False,
        "be_sent": False,
        "closed": False,
    }
    save_state(STATE)


def maybe_update_open_trade(market: str, symbol: str, signal: dict):
    key = trade_key(market, symbol)
    trade = STATE["open_trades"].get(key)
    if not trade or trade.get("closed"):
        return

    price = safe_float(signal.get("trigger_price"))
    side = trade["side"]

    if side == "BUY" and not trade["tp1_sent"] and price >= trade["tp1"]:
        trade["tp1_sent"] = True
        STATE["stats"]["tp1_hits"] += 1
        send_telegram(
            f"🎯 TP1 HIT\n\n"
            f"Symbol: {symbol}\nSide: BUY\nEntry: {format_price(trade['entry'])}\n"
            f"TP1: {format_price(trade['tp1'])}\nCurrent: {format_price(price)}\n\n"
            f"SL can move to breakeven."
        )

    if side == "SELL" and not trade["tp1_sent"] and price <= trade["tp1"]:
        trade["tp1_sent"] = True
        STATE["stats"]["tp1_hits"] += 1
        send_telegram(
            f"🎯 TP1 HIT\n\n"
            f"Symbol: {symbol}\nSide: SELL\nEntry: {format_price(trade['entry'])}\n"
            f"TP1: {format_price(trade['tp1'])}\nCurrent: {format_price(price)}\n\n"
            f"SL can move to breakeven."
        )

    if trade["tp1_sent"] and not trade["be_sent"]:
        trade["be_sent"] = True
        STATE["stats"]["break_even_hits"] += 1
        send_telegram(
            f"🔁 TRAIL UPDATE\n\n"
            f"Symbol: {symbol}\nSide: {trade['side']}\n"
            f"Action: Move SL to breakeven\nBreakeven: {format_price(trade['entry'])}"
        )

    if side == "BUY" and not trade["tp2_sent"] and price >= trade["tp2"]:
        trade["tp2_sent"] = True
        trade["closed"] = True
        STATE["stats"]["tp2_hits"] += 1
        STATE["stats"]["wins"] += 1
        send_telegram(
            f"🚀 TP2 HIT / TRADE WON\n\n"
            f"Symbol: {symbol}\nSide: BUY\nEntry: {format_price(trade['entry'])}\n"
            f"TP2: {format_price(trade['tp2'])}\nCurrent: {format_price(price)}"
        )

    if side == "SELL" and not trade["tp2_sent"] and price <= trade["tp2"]:
        trade["tp2_sent"] = True
        trade["closed"] = True
        STATE["stats"]["tp2_hits"] += 1
        STATE["stats"]["wins"] += 1
        send_telegram(
            f"🚀 TP2 HIT / TRADE WON\n\n"
            f"Symbol: {symbol}\nSide: SELL\nEntry: {format_price(trade['entry'])}\n"
            f"TP2: {format_price(trade['tp2'])}\nCurrent: {format_price(price)}"
        )

    if side == "BUY" and not trade["closed"] and price <= trade["sl"]:
        trade["closed"] = True
        STATE["stats"]["losses"] += 1
        send_telegram(
            f"❌ STOP LOSS HIT\n\n"
            f"Symbol: {symbol}\nSide: BUY\nEntry: {format_price(trade['entry'])}\n"
            f"SL: {format_price(trade['sl'])}\nCurrent: {format_price(price)}"
        )

    if side == "SELL" and not trade["closed"] and price >= trade["sl"]:
        trade["closed"] = True
        STATE["stats"]["losses"] += 1
        send_telegram(
            f"❌ STOP LOSS HIT\n\n"
            f"Symbol: {symbol}\nSide: SELL\nEntry: {format_price(trade['entry'])}\n"
            f"SL: {format_price(trade['sl'])}\nCurrent: {format_price(price)}"
        )

    save_state(STATE)


def can_send_new_signal(market: str, symbol: str, signal: dict, ai_score: int, trigger_count: int, rr: float):
    if signal.get("signal_type") not in ["BUY ENTRY READY", "SELL ENTRY READY"]:
        return False, "No confirmed entry."

    if ai_score < MIN_AI_SCORE:
        return False, f"AI score too low ({ai_score})."

    if trigger_count < 4:
        return False, f"Not enough triggers ({trigger_count})."

    if rr < 1.4:
        return False, f"RR too low ({rr:.2f})."

    if STATE["daily_count"] >= MAX_SIGNALS_PER_DAY:
        return False, "Daily max signals reached."

    key = trade_key(market, symbol)
    now_ts = time.time()
    last_time = STATE["last_signal_time"].get(key, 0)
    last_side = STATE["last_signal_side"].get(key)
    last_score = STATE["last_signal_score"].get(key, 0)

    side = signal.get("preferred_side")

    if now_ts - last_time < MIN_SIGNAL_GAP_SECONDS:
        return False, "Cooldown active."

    if last_side and last_side != side and now_ts - last_time < OPPOSITE_LOCK_SECONDS:
        return False, "Opposite side locked."

    if last_side == side and ai_score <= last_score + 6:
        return False, "Not enough stronger than previous."

    open_trade = STATE["open_trades"].get(key)
    if open_trade and not open_trade.get("closed"):
        return False, "Trade already open on symbol."

    return True, "OK"


def run():
    print("🎯 ULTRA SNIPER BOT RUNNING")

    while True:
        try:
            if STATE.get("daily_date") != today_key():
                STATE["daily_date"] = today_key()
                STATE["daily_count"] = 0
                save_state(STATE)

            session = active_session_name()
            if not session:
                print("Outside London/New York session.")
                time.sleep(SCAN_INTERVAL_SECONDS)
                continue

            for market, symbol in SCAN_SYMBOLS:
                try:
                    mtf = get_multi_timeframe_analysis(market, symbol)
                    signal = evaluate_signal_engine(mtf)

                    print(symbol, "->", signal.get("signal_type"), "|", signal.get("preferred_side"), "| score:", signal.get("signal_score"))

                    maybe_update_open_trade(market, symbol, signal)

                    ai_score, trigger_count, rr = build_ai_score(signal, session)
                    allowed, reason = can_send_new_signal(market, symbol, signal, ai_score, trigger_count, rr)

                    if not allowed:
                        print(symbol, "blocked:", reason)
                        continue

                    msg = build_signal_message(market, symbol, signal, ai_score, session, trigger_count, rr)
                    send_telegram(msg)

                    key = trade_key(market, symbol)
                    STATE["last_signal_time"][key] = int(time.time())
                    STATE["last_signal_side"][key] = signal.get("preferred_side")
                    STATE["last_signal_score"][key] = ai_score
                    STATE["daily_count"] += 1
                    STATE["stats"]["signals_sent"] += 1

                    register_open_trade(market, symbol, signal, ai_score)
                    save_state(STATE)

                    print("✅ SIGNAL SENT:", symbol)

                except Exception as exc:
                    print("Worker symbol error:", symbol, exc)

            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as exc:
            print("Worker loop error:", exc)
            time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
