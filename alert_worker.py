import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

print("🔥 BOT FILE LOADED", flush=True)

from signal_engine import get_multi_timeframe_analysis, evaluate_signal_engine, format_price

TELEGRAM_BOT_TOKEN = "8785866877:AAHM-tze7VEOWcxGGcsVg0dWadheZX_Bhlw"
TELEGRAM_CHAT_ID = "1080439188"

SCAN_SYMBOLS = [("forex", "XAU/USD"),
]

SCAN_INTERVAL_SECONDS = 90
MAX_SIGNALS_PER_DAY = 2
MIN_SIGNAL_GAP_SECONDS = 5400
OPPOSITE_LOCK_SECONDS = 14400
MIN_AI_SCORE_MAIN = 85
MIN_AI_SCORE_OFF = 90
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
    return (
        minute in [25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]
        or minute in [55, 56, 57, 58, 59, 0, 1, 2, 3, 4, 5]
    )


def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "DEIN_TELEGRAM_TOKEN_HIER":
        print("Telegram token missing.", flush=True)
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=8)
        print("Telegram:", r.status_code, r.text[:120], flush=True)
    except Exception as exc:
        print("Telegram error:", exc, flush=True)


def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def count_yes(*values):
    return sum(1 for v in values if str(v).upper() == "YES")


def trade_key(market: str, symbol: str):
    return f"{market}:{symbol}"


def fvg_required(signal: dict):
    side = signal.get("preferred_side", "WAIT")
    if side == "BUY":
        return signal.get("buy_fvg") == "YES"
    if side == "SELL":
        return signal.get("sell_fvg") == "YES"
    return False


def build_ai_score(signal: dict, session: str):
    side = signal.get("preferred_side", "WAIT")
    base = 0

    if signal.get("signal_type") in ["BUY ENTRY READY", "SELL ENTRY READY"]:
        base += 35

    if signal.get("signal_status") in ["CONFIRMED BUY", "CONFIRMED SELL"]:
        base += 15

    if side == "BUY":
        trigger_count = count_yes(
            signal.get("buy_fvg"),
            signal.get("buy_ob"),
            signal.get("buy_sweep"),
        )
        if signal.get("stronger_magnet") == "UP":
            trigger_count += 1
        if signal.get("fib_618") not in [None, "-"]:
            trigger_count += 1
    elif side == "SELL":
        trigger_count = count_yes(
            signal.get("sell_fvg"),
            signal.get("sell_ob"),
            signal.get("sell_sweep"),
        )
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
    else:
        base += 2

    tp1 = safe_float(signal.get("tp1"))
    entry = safe_float(signal.get("entry_price"))
    sl = safe_float(signal.get("sl_price"))
    rr = 0.0

    if side == "BUY" and entry > sl:
        rr = (tp1 - entry) / max(entry - sl, 1e-9)
    elif side == "SELL" and sl > entry:
        rr = (entry - tp1) / max(sl - entry, 1e-9)

    if rr >= 1.8:
        base += 14
    elif rr >= 1.5:
        base += 10
    elif rr >= 1.2:
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
        f"FVG: {signal.get('buy_fvg') if signal.get('preferred_side') == 'BUY' else signal.get('sell_fvg')}\n"
        f"OB: {signal.get('buy_ob') if signal.get('preferred_side') == 'BUY' else signal.get('sell_ob')}\n"
        f"Sweep: {signal.get('buy_sweep') if signal.get('preferred_side') == 'BUY' else signal.get('sell_sweep')}\n"
    )


def send_stats():
    wins = STATE["stats"]["wins"]
    losses = STATE["stats"]["losses"]
    total = wins + losses
    winrate = (wins / total * 100) if total > 0 else 0.0

    send_telegram(
        f"📊 BOT STATS\n"
        f"Signals Sent: {STATE['stats']['signals_sent']}\n"
        f"Wins: {wins}\n"
        f"Losses: {losses}\n"
        f"TP1 Hits: {STATE['stats']['tp1_hits']}\n"
        f"TP2 Hits: {STATE['stats']['tp2_hits']}\n"
        f"Break-even Moves: {STATE['stats']['break_even_hits']}\n"
        f"Winrate: {winrate:.1f}%"
    )


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
        "closed": False,
    }
    save_state()


def maybe_update_open_trade(market: str, symbol: str, signal: dict):
    key = trade_key(market, symbol)
    trade = STATE["open_trades"].get(key)
    if not trade or trade.get("closed"):
        return

    price = safe_float(signal.get("trigger_price"))
    side = trade["side"]

    if side == "BUY" and not trade["tp1_sent"] and price >= trade["tp1"]:
        trade["tp1_sent"] = True
        trade["sl"] = trade["entry"]
        STATE["stats"]["tp1_hits"] += 1
        STATE["stats"]["break_even_hits"] += 1
        send_telegram(f"🎯 TP1 HIT\n\n{symbol} BUY\nSL moved to Break Even.")

    if side == "SELL" and not trade["tp1_sent"] and price <= trade["tp1"]:
        trade["tp1_sent"] = True
        trade["sl"] = trade["entry"]
        STATE["stats"]["tp1_hits"] += 1
        STATE["stats"]["break_even_hits"] += 1
        send_telegram(f"🎯 TP1 HIT\n\n{symbol} SELL\nSL moved to Break Even.")

    if trade["tp1_sent"] and not trade["closed"]:
        if side == "BUY" and price > trade["tp2"]:
            trade["sl"] = max(trade["sl"], price - price * 0.002)
        if side == "SELL" and price < trade["tp2"]:
            trade["sl"] = min(trade["sl"], price + price * 0.002)

    if side == "BUY" and price >= trade["tp_large"]:
        trade["closed"] = True
        STATE["stats"]["tp2_hits"] += 1
        STATE["stats"]["wins"] += 1
        send_telegram(f"🏁 TP LARGE HIT\n\n{symbol} BUY")

    elif side == "SELL" and price <= trade["tp_large"]:
        trade["closed"] = True
        STATE["stats"]["tp2_hits"] += 1
        STATE["stats"]["wins"] += 1
        send_telegram(f"🏁 TP LARGE HIT\n\n{symbol} SELL")

    elif side == "BUY" and not trade["closed"] and price <= trade["sl"]:
        trade["closed"] = True
        if trade["tp1_sent"]:
            send_telegram(f"🔁 BREAK EVEN EXIT\n\n{symbol} BUY")
        else:
            STATE["stats"]["losses"] += 1
            send_telegram(f"❌ STOP LOSS HIT\n\n{symbol} BUY")

    elif side == "SELL" and not trade["closed"] and price >= trade["sl"]:
        trade["closed"] = True
        if trade["tp1_sent"]:
            send_telegram(f"🔁 BREAK EVEN EXIT\n\n{symbol} SELL")
        else:
            STATE["stats"]["losses"] += 1
            send_telegram(f"❌ STOP LOSS HIT\n\n{symbol} SELL")

    save_state()


def can_send_new_signal(market: str, symbol: str, signal: dict, ai_score: int, trigger_count: int, rr: float):
    if signal.get("signal_type") not in ["BUY ENTRY READY", "SELL ENTRY READY"]:
        return False, "No confirmed entry"

    if avoid_news_window():
        return False, "News blocked"

    if not fvg_required(signal):
        return False, "FVG required"

    session = active_session_name()

    if session in ["LONDON", "NEW YORK"]:
        if trigger_count < 3:
            return False, "Need 3 triggers"
        if rr < 1.2:
            return False, "RR low"
        if ai_score < MIN_AI_SCORE_MAIN:
            return False, "AI too low"
    else:
        if trigger_count < 4:
            return False, "Need 4 triggers off session"
        if rr < 1.4:
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

    if last_side == current_side:
        if ai_score <= last_score + 5:
            return False, "Not stronger"
        send_telegram(f"🔁 SIGNAL UPDATE\n\n{symbol}\nDirection: {current_side}\nBetter setup detected.")
        return False, "Updated"

    open_trade = STATE["open_trades"].get(key)
    if open_trade and not open_trade.get("closed"):
        return False, "Trade already open"

    return True, "OK"


def run():
    print("🔥 BOT V4 RUNNING", flush=True)

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

                    print("✅ SIGNAL SENT:", symbol, flush=True)

                except Exception as exc:
                    print("Worker symbol error:", symbol, exc, flush=True)

            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as exc:
            print("Worker loop error:", exc, flush=True)
            time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

from signal_engine import get_multi_timeframe_analysis, evaluate_signal_engine, format_price

# =========================================================
# CONFIG
# =========================================================

TELEGRAM_BOT_TOKEN = "8785866877:AAHM-tze7VEOWcxGGcsVg0dWadheZX_Bhlw"
TELEGRAM_CHAT_ID = "1080439188"

SCAN_SYMBOLS = [
    ("crypto", "BTCUSDT"),
    ("forex", "XAU/USD"),
]

SCAN_INTERVAL_SECONDS = 90
MAX_SIGNALS_PER_DAY = 2
MIN_SIGNAL_GAP_SECONDS = 5400      # 90 min
OPPOSITE_LOCK_SECONDS = 14400      # 4h
MIN_AI_SCORE_MAIN = 85             # London / New York
MIN_AI_SCORE_OFF = 90              # Outside main sessions
STATE_FILE = "bot_state.json"

# =========================================================
# TIME / STATE
# =========================================================

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
    except Exception as exc:
        print("load_state error:", exc)
        return default_state()

def save_state(state):
    try:
        Path(STATE_FILE).write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        print("save_state error:", exc)

STATE = load_state()

# =========================================================
# SESSION / NEWS
# =========================================================

def active_session_name():
    hour = utc_now().hour
    if 7 <= hour <= 11:
        return "LONDON"
    if 12 <= hour <= 17:
        return "NEW YORK"
    return "OFF_SESSION"

def is_strong_session():
    return active_session_name() in ["LONDON", "NEW YORK"]

def avoid_news_window():
    minute = utc_now().minute
    around_half = minute in [25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]
    around_full = minute in [55, 56, 57, 58, 59, 0, 1, 2, 3, 4, 5]
    return around_half or around_full

# =========================================================
# TELEGRAM
# =========================================================

def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "DEIN_TELEGRAM_TOKEN_HIER":
        print("Telegram token missing.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=8)
        print("Telegram:", r.status_code, r.text[:120])
    except Exception as exc:
        print("Telegram error:", exc)

# =========================================================
# HELPERS
# =========================================================

def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def count_yes(*values):
    return sum(1 for v in values if str(v).upper() == "YES")

def trade_key(market: str, symbol: str):
    return f"{market}:{symbol}"

def strong_candle_confirmation_from_signal(signal: dict):
    side = signal.get("preferred_side", "WAIT")

    if side == "BUY":
        return count_yes(
            signal.get("buy_fvg"),
            signal.get("buy_ob"),
            signal.get("buy_sweep"),
        ) >= 2

    if side == "SELL":
        return count_yes(
            signal.get("sell_fvg"),
            signal.get("sell_ob"),
            signal.get("sell_sweep"),
        ) >= 2

    return False

def fvg_required(signal: dict):
    side = signal.get("preferred_side", "WAIT")
    if side == "BUY":
        return signal.get("buy_fvg") == "YES"
    if side == "SELL":
        return signal.get("sell_fvg") == "YES"
    return False

# =========================================================
# AI SCORE
# =========================================================

def build_ai_score(signal: dict, session: str):
    side = signal.get("preferred_side", "WAIT")
    base = 0

    if signal.get("signal_type") in ["BUY ENTRY READY", "SELL ENTRY READY"]:
        base += 35

    signal_status = str(signal.get("signal_status", ""))
    if signal_status in ["CONFIRMED BUY", "CONFIRMED SELL"]:
        base += 15

    if side == "BUY":
        trigger_count = count_yes(
            signal.get("buy_fvg"),
            signal.get("buy_ob"),
            signal.get("buy_sweep"),
        )
        if signal.get("stronger_magnet") == "UP":
            trigger_count += 1
        if signal.get("fib_618") not in [None, "-"]:
            trigger_count += 1
    elif side == "SELL":
        trigger_count = count_yes(
            signal.get("sell_fvg"),
            signal.get("sell_ob"),
            signal.get("sell_sweep"),
        )
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
    else:
        base += 2

    tp1 = safe_float(signal.get("tp1"))
    entry = safe_float(signal.get("entry_price"))
    sl = safe_float(signal.get("sl_price"))
    rr = 0.0

    if signal.get("preferred_side") == "BUY" and entry > sl:
        rr = (tp1 - entry) / max(entry - sl, 1e-9)
    elif signal.get("preferred_side") == "SELL" and sl > entry:
        rr = (entry - tp1) / max(sl - entry, 1e-9)

    if rr >= 1.8:
        base += 14
    elif rr >= 1.5:
        base += 10
    elif rr >= 1.2:
        base += 6

    if strong_candle_confirmation_from_signal(signal):
        base += 8

    raw_score = safe_float(signal.get("signal_score"))
    base += min(int(raw_score / 8), 12)

    return min(base, 100), trigger_count, rr

# =========================================================
# MESSAGES
# =========================================================

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

def send_stats():
    wins = STATE["stats"]["wins"]
    losses = STATE["stats"]["losses"]
    total = wins + losses
    winrate = (wins / total * 100) if total > 0 else 0.0

    send_telegram(
        f"📊 BOT STATS\n"
        f"Signals Sent: {STATE['stats']['signals_sent']}\n"
        f"Wins: {wins}\n"
        f"Losses: {losses}\n"
        f"TP1 Hits: {STATE['stats']['tp1_hits']}\n"
        f"TP2 Hits: {STATE['stats']['tp2_hits']}\n"
        f"Break-even Moves: {STATE['stats']['break_even_hits']}\n"
        f"Winrate: {winrate:.1f}%"
    )

# =========================================================
# TRADE MANAGEMENT
# =========================================================

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

    # TP1 -> move to breakeven
    if side == "BUY" and not trade["tp1_sent"] and price >= trade["tp1"]:
        trade["tp1_sent"] = True
        trade["sl"] = trade["entry"]
        STATE["stats"]["tp1_hits"] += 1
        STATE["stats"]["break_even_hits"] += 1
        send_telegram(
            f"🎯 TP1 HIT\n\n"
            f"Symbol: {symbol}\n"
            f"Side: BUY\n"
            f"Entry: {format_price(trade['entry'])}\n"
            f"TP1: {format_price(trade['tp1'])}\n"
            f"Current: {format_price(price)}\n\n"
            f"SL moved to Break Even."
        )

    if side == "SELL" and not trade["tp1_sent"] and price <= trade["tp1"]:
        trade["tp1_sent"] = True
        trade["sl"] = trade["entry"]
        STATE["stats"]["tp1_hits"] += 1
        STATE["stats"]["break_even_hits"] += 1
        send_telegram(
            f"🎯 TP1 HIT\n\n"
            f"Symbol: {symbol}\n"
            f"Side: SELL\n"
            f"Entry: {format_price(trade['entry'])}\n"
            f"TP1: {format_price(trade['tp1'])}\n"
            f"Current: {format_price(price)}\n\n"
            f"SL moved to Break Even."
        )

    # Breakout follow mode after TP1
    if trade["tp1_sent"] and not trade["closed"]:
        if side == "BUY" and price > trade["tp2"]:
            new_sl = max(trade["sl"], price - price * 0.002)
            if new_sl > trade["sl"]:
                trade["sl"] = new_sl

        if side == "SELL" and price < trade["tp2"]:
            new_sl = min(trade["sl"], price + price * 0.002)
            if new_sl < trade["sl"]:
                trade["sl"] = new_sl

    # TP2 hit
    if side == "BUY" and not trade["tp2_sent"] and price >= trade["tp2"]:
        trade["tp2_sent"] = True
        STATE["stats"]["tp2_hits"] += 1
        send_telegram(
            f"🚀 TP2 HIT\n\n"
            f"Symbol: {symbol}\n"
            f"Side: BUY\n"
            f"Entry: {format_price(trade['entry'])}\n"
            f"TP2: {format_price(trade['tp2'])}\n"
            f"Current: {format_price(price)}"
        )

    if side == "SELL" and not trade["tp2_sent"] and price <= trade["tp2"]:
        trade["tp2_sent"] = True
        STATE["stats"]["tp2_hits"] += 1
        send_telegram(
            f"🚀 TP2 HIT\n\n"
            f"Symbol: {symbol}\n"
            f"Side: SELL\n"
            f"Entry: {format_price(trade['entry'])}\n"
            f"TP2: {format_price(trade['tp2'])}\n"
            f"Current: {format_price(price)}"
        )

    # Exit by stop
    if side == "BUY" and not trade["closed"] and price <= trade["sl"]:
        trade["closed"] = True
        if trade["tp2_sent"]:
            STATE["stats"]["wins"] += 1
            send_telegram(f"🏁 TRADE CLOSED IN PROFIT\n\n{symbol} BUY")
        else:
            STATE["stats"]["losses"] += 1
            send_telegram(f"❌ STOP LOSS HIT\n\n{symbol} BUY")

    if side == "SELL" and not trade["closed"] and price >= trade["sl"]:
        trade["closed"] = True
        if trade["tp2_sent"]:
            STATE["stats"]["wins"] += 1
            send_telegram(f"🏁 TRADE CLOSED IN PROFIT\n\n{symbol} SELL")
        else:
            STATE["stats"]["losses"] += 1
            send_telegram(f"❌ STOP LOSS HIT\n\n{symbol} SELL")

    save_state(STATE)

# =========================================================
# FILTERS
# =========================================================

def can_send_new_signal(market: str, symbol: str, signal: dict, ai_score: int, trigger_count: int, rr: float):
    if signal.get("signal_type") not in ["BUY ENTRY READY", "SELL ENTRY READY"]:
        return False, "No confirmed entry."

    if avoid_news_window():
        return False, "News blocked"

    if not fvg_required(signal):
        return False, "FVG required"

    session = active_session_name()

    if session in ["LONDON", "NEW YORK"]:
        if trigger_count < 3:
            return False, "Need 3 triggers"
        if rr < 1.2:
            return False, "RR low"
        if ai_score < MIN_AI_SCORE_MAIN:
            return False, "AI too low"
    else:
        if trigger_count < 4:
            return False, "Need 4 triggers off session"
        if rr < 1.4:
            return False, "RR low off session"
        if ai_score < MIN_AI_SCORE_OFF:
            return False, "AI too low off session"

    if STATE["daily_count"] >= MAX_SIGNALS_PER_DAY:
        return False, "Daily max signals reached"

    key = trade_key(market, symbol)
    now_ts = time.time()
    last_time = STATE["last_signal_time"].get(key, 0)
    last_side = STATE["last_signal_side"].get(key)
    last_score = STATE["last_signal_score"].get(key, 0)
    current_side = signal.get("preferred_side")

    if now_ts - last_time < MIN_SIGNAL_GAP_SECONDS:
        return False, "Cooldown"

    if last_side and last_side != current_side and now_ts - last_time < OPPOSITE_LOCK_SECONDS:
        return False, "Opposite side locked"

    if last_side == current_side:
        if ai_score <= last_score + 5:
            return False, "Not stronger"
        send_telegram(
            f"🔁 SIGNAL UPDATE\n\n"
            f"{symbol}\n"
            f"Direction: {current_side}\n"
            f"Better setup detected."
        )
        return False, "Updated"

    open_trade = STATE["open_trades"].get(key)
    if open_trade and not open_trade.get("closed"):
        return False, "Trade already open"

    return True, "OK"

# =========================================================
# MAIN LOOP
# =========================================================

def run():
    print("🔥 BOT V4 RUNNING")
    print("STATE:", STATE)

    while True:
        try:
            print("⏳ checking market...")
            session = active_session_name()
            print("Current session:", session)

            if STATE.get("daily_date") != today_key():
                STATE["daily_date"] = today_key()
                STATE["daily_count"] = 0
                save_state(STATE)
                print("Daily reset done.")

            for market, symbol in SCAN_SYMBOLS:
                try:
                    print(f"Scanning {market} {symbol} ...")
                    mtf = get_multi_timeframe_analysis(market, symbol)
                    signal = evaluate_signal_engine(mtf)

                    print("DEBUG SIGNAL:", symbol, signal)

                    maybe_update_open_trade(market, symbol, signal)

                    ai_score, trigger_count, rr = build_ai_score(signal, session)
                    print(f"DEBUG SCORE: {symbol} ai={ai_score} triggers={trigger_count} rr={rr:.2f}")

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

                    if STATE["stats"]["signals_sent"] % 3 == 0:
                        send_stats()

                    print("✅ SIGNAL SENT:", symbol)

                except Exception as exc:
                    print("Worker symbol error:", symbol, exc)

            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as exc:
            print("Worker loop error:", exc)
            time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
