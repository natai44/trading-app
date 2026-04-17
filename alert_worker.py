import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

print("🔥 BOT FILE LOADED", flush=True)

from signal_engine import get_multi_timeframe_analysis, evaluate_signal_engine, format_price

TELEGRAM_BOT_TOKEN = "8785866877:AAHM-tze7VEOWcxGGcsVg0dWadheZX_Bhlw"
TELEGRAM_CHAT_ID = "@magnet_0510"

SCAN_SYMBOLS = [
    ("forex", "XAU/USD"),
]

SCAN_INTERVAL_SECONDS = 300
MAX_SIGNALS_PER_DAY = 3
MIN_SIGNAL_GAP_SECONDS = 5400
OPPOSITE_LOCK_SECONDS = 14400
STATE_FILE = "bot_state.json"

# BASIC SETUP TRACKING
SETUP_EXPIRY_SECONDS = 60 * 60 * 4   # 4 Stunden
EARLY_MOVE_R_MULTIPLIER = 0.70       # ~0.7R Bewegung ohne Entry-Bestätigung


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
        "last_wait_time": {},
        "tracked_setups": {},
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
            "waits_sent": 0,
            "missed_setups": 0,
            "early_moves": 0,
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

        if "tracked_setups" not in data:
            data["tracked_setups"] = {}

        stats = data.get("stats", {})
        defaults = default_state()["stats"]
        for key, value in defaults.items():
            if key not in stats:
                stats[key] = value
        data["stats"] = stats

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
    st = signal.get("signal_type", "")
    if st == "NO CLEAR SETUP":
        return 0, 0, 0.0

    base = safe_float(signal.get("signal_score"))
    mode = signal.get("setup_mode", "NONE")

    if mode == "FULL":
        triggers = 3
    elif mode == "SAFE":
        triggers = 2
    else:
        triggers = 1

    if session == "LONDON":
        base += 8
    elif session == "NEW YORK":
        base += 10
    else:
        base += 2

    rr = 0.0
    entry = safe_float(signal.get("entry_price"))
    sl = safe_float(signal.get("sl_price"))
    tp1 = safe_float(signal.get("tp1"))
    side = signal.get("preferred_side")

    if entry and sl and tp1:
        if side == "BUY" and entry > sl:
            rr = (tp1 - entry) / max(entry - sl, 1e-9)
        elif side == "SELL" and sl > entry:
            rr = (entry - tp1) / max(sl - entry, 1e-9)

    return min(int(base), 100), triggers, rr


def build_wait_message(market: str, symbol: str, signal: dict, ai_score: int, session: str):
    side = signal.get("preferred_side", "-")
    return (
        f"👀 {signal['signal_type']}\n\n"
        f"Market: {market.upper()} | Symbol: {symbol}\n"
        f"Session: {session}\n"
        f"Direction: {side}\n"
        f"Mode: {signal.get('setup_mode', '-')}\n"
        f"AI Score: {ai_score}\n\n"
        f"Wait Zone: {format_price(signal.get('wait_zone_low'))} - {format_price(signal.get('wait_zone_high'))}\n"
        f"Planned Entry: {format_price(signal.get('wait_entry_price'))}\n\n"
        f"Bot will wait for zone + candle confirmation."
    )


def build_ready_message(market: str, symbol: str, signal: dict, ai_score: int, session: str, trigger_count: int, rr: float):
    return (
        f"🔥 {signal['signal_type']}\n\n"
        f"Market: {market.upper()} | Symbol: {symbol}\n"
        f"Session: {session}\n"
        f"Direction: {signal.get('preferred_side', '-')}\n"
        f"Mode: {signal.get('setup_mode', '-')}\n"
        f"AI Score: {ai_score}\n"
        f"Triggers: {trigger_count}\n"
        f"RR: {rr:.2f}\n\n"
        f"Entry: {format_price(signal.get('entry_price'))}\n"
        f"SL: {format_price(signal.get('sl_price'))}\n"
        f"TP1: {format_price(signal.get('tp1'))}\n"
        f"TP2: {format_price(signal.get('tp2'))}\n"
        f"TP Large: {format_price(signal.get('tp_large'))}\n\n"
        f"Confirmation: zone touched + candle confirmed"
    )


def build_missed_message(symbol: str, side: str):
    return (
        f"❌ SETUP MISSED\n\n"
        f"{symbol} {side}\n\n"
        f"Price did not give a valid confirmed entry in time.\n"
        f"Setup expired."
    )


def build_early_move_message(symbol: str, side: str, price: float):
    return (
        f"⚠️ EARLY MOVE\n\n"
        f"{symbol} {side}\n\n"
        f"Price moved in the expected direction without valid candle confirmation.\n"
        f"Current Price: {format_price(price)}"
    )


def send_stats():
    s = STATE["stats"]
    winrate = (s["wins"] / s["closed_trades"] * 100) if s["closed_trades"] > 0 else 0.0
    msg = (
        f"📊 BOT STATS\n"
        f"Signals Sent: {s['signals_sent']}\n"
        f"Closed Trades: {s['closed_trades']}\n"
        f"Wins: {s['wins']}\n"
        f"Losses: {s['losses']}\n"
        f"Break-even: {s['breakeven']}\n"
        f"TP1 Hits: {s['tp1_hits']}\n"
        f"TP2 Hits: {s['tp2_hits']}\n"
        f"TP Large Hits: {s['tp_large_hits']}\n"
        f"WAIT Signals: {s['waits_sent']}\n"
        f"Missed Setups: {s['missed_setups']}\n"
        f"Early Moves: {s['early_moves']}\n"
        f"Winrate: {winrate:.1f}%"
    )
    send_telegram(msg)


def register_open_trade(market: str, symbol: str, signal: dict, ai_score: int):
    key = trade_key(market, symbol)
    STATE["open_trades"][key] = {
        "market": market,
        "symbol": symbol,
        "side": signal["preferred_side"],
        "mode": signal.get("setup_mode", "NONE"),
        "entry": safe_float(signal.get("entry_price")),
        "sl": safe_float(signal.get("sl_price")),
        "tp1": safe_float(signal.get("tp1")),
        "tp2": safe_float(signal.get("tp2")),
        "tp_large": safe_float(signal.get("tp_large")),
        "ai_score": ai_score,
        "created_at": int(time.time()),
        "tp1_sent": False,
        "tp2_sent": False,
        "tp_large_sent": False,
        "extended_count": 0,
        "closed": False,
    }
    save_state()


def register_wait_setup(market: str, symbol: str, signal: dict):
    key = trade_key(market, symbol)
    planned_entry = safe_float(signal.get("wait_entry_price"))
    zone_low = safe_float(signal.get("wait_zone_low"))
    zone_high = safe_float(signal.get("wait_zone_high"))
    side = signal.get("preferred_side", "WAIT")

    if not planned_entry or not zone_low or not zone_high:
        return

    if side == "BUY":
        est_sl = zone_low - planned_entry * 0.002
        est_risk = max(planned_entry - est_sl, 1e-9)
    else:
        est_sl = zone_high + planned_entry * 0.002
        est_risk = max(est_sl - planned_entry, 1e-9)

    STATE["tracked_setups"][key] = {
        "market": market,
        "symbol": symbol,
        "side": side,
        "mode": signal.get("setup_mode", "NONE"),
        "created_at": int(time.time()),
        "planned_entry": planned_entry,
        "zone_low": zone_low,
        "zone_high": zone_high,
        "estimated_sl": est_sl,
        "estimated_risk": est_risk,
        "status": "WAIT",
        "early_move_sent": False,
    }
    save_state()


def clear_tracked_setup(market: str, symbol: str):
    key = trade_key(market, symbol)
    if key in STATE["tracked_setups"]:
        del STATE["tracked_setups"][key]
        save_state()


def maybe_track_setup_outcome(market: str, symbol: str, signal: dict):
    key = trade_key(market, symbol)
    setup = STATE["tracked_setups"].get(key)
    if not setup:
        return

    if setup.get("status") != "WAIT":
        return

    now_ts = int(time.time())
    current_price = safe_float(signal.get("trigger_price"))
    side = setup["side"]
    planned_entry = safe_float(setup["planned_entry"])
    est_risk = safe_float(setup["estimated_risk"], 0.0)

    # READY -> tracked setup beenden
    if signal.get("signal_type") in ["BUY ENTRY READY", "SELL ENTRY READY"]:
        setup["status"] = "READY"
        clear_tracked_setup(market, symbol)
        return

    # EARLY MOVE
    if est_risk > 0 and not setup.get("early_move_sent"):
        if side == "BUY":
            moved = current_price >= planned_entry + est_risk * EARLY_MOVE_R_MULTIPLIER
        else:
            moved = current_price <= planned_entry - est_risk * EARLY_MOVE_R_MULTIPLIER

        if moved:
            setup["early_move_sent"] = True
            setup["status"] = "EARLY_MOVE"
            STATE["stats"]["early_moves"] += 1
            send_telegram(build_early_move_message(symbol, side, current_price))
            save_state()
            return

    # MISSED
    if now_ts - setup["created_at"] >= SETUP_EXPIRY_SECONDS:
        setup["status"] = "MISSED"
        STATE["stats"]["missed_setups"] += 1
        send_telegram(build_missed_message(symbol, side))
        clear_tracked_setup(market, symbol)


def maybe_extend_trade(trade: dict, signal: dict):
    if trade["extended_count"] >= 2:
        return False

    side = trade["side"]
    price = safe_float(signal.get("trigger_price"))

    if side == "BUY" and price > trade["tp2"]:
        old_tp = trade["tp_large"]
        new_tp = max(old_tp, price + (price - trade["entry"]) * 0.8)
        if new_tp > old_tp:
            trade["tp_large"] = new_tp
            trade["sl"] = max(trade["sl"], price - price * 0.002)
            trade["extended_count"] += 1
            return True

    if side == "SELL" and price < trade["tp2"]:
        old_tp = trade["tp_large"]
        new_tp = min(old_tp, price - (trade["entry"] - price) * 0.8)
        if new_tp < old_tp:
            trade["tp_large"] = new_tp
            trade["sl"] = min(trade["sl"], price + price * 0.002)
            trade["extended_count"] += 1
            return True

    return False


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
        send_telegram(
            f"🎯 TP1 HIT\n\n"
            f"{symbol} BUY\n"
            f"Small profit secured.\n"
            f"SL moved to Break Even."
        )

    if side == "SELL" and not trade["tp1_sent"] and price <= trade["tp1"]:
        trade["tp1_sent"] = True
        trade["sl"] = trade["entry"]
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
        send_telegram(f"🏁 TP LARGE HIT\n\n{symbol} BUY")

    if side == "SELL" and not trade["tp_large_sent"] and price <= trade["tp_large"]:
        trade["tp_large_sent"] = True
        trade["closed"] = True
        STATE["stats"]["tp_large_hits"] += 1
        STATE["stats"]["wins"] += 1
        STATE["stats"]["closed_trades"] += 1
        send_telegram(f"🏁 TP LARGE HIT\n\n{symbol} SELL")

    if side == "BUY" and not trade["closed"] and price <= trade["sl"]:
        trade["closed"] = True
        STATE["stats"]["closed_trades"] += 1
        if trade["tp1_sent"]:
            STATE["stats"]["breakeven"] += 1
            send_telegram(f"🔁 BREAK EVEN EXIT\n\n{symbol} BUY")
        else:
            STATE["stats"]["losses"] += 1
            send_telegram(f"❌ STOP LOSS HIT\n\n{symbol} BUY")

    if side == "SELL" and not trade["closed"] and price >= trade["sl"]:
        trade["closed"] = True
        STATE["stats"]["closed_trades"] += 1
        if trade["tp1_sent"]:
            STATE["stats"]["breakeven"] += 1
            send_telegram(f"🔁 BREAK EVEN EXIT\n\n{symbol} SELL")
        else:
            STATE["stats"]["losses"] += 1
            send_telegram(f"❌ STOP LOSS HIT\n\n{symbol} SELL")

    save_state()


def can_send_wait_signal(market: str, symbol: str, signal: dict):
    if signal.get("signal_type") not in ["WAIT ENTRY BUY", "WAIT ENTRY SELL"]:
        return False, "Not wait signal"

    key = trade_key(market, symbol)
    now_ts = time.time()
    last_wait = STATE["last_wait_time"].get(key, 0)

    # kein neues WAIT wenn schon aktives WAIT läuft
    existing = STATE["tracked_setups"].get(key)
    if existing and existing.get("status") == "WAIT":
        return False, "Existing wait active"

    if now_ts - last_wait < 3600:
        return False, "Wait cooldown"

    open_trade = STATE["open_trades"].get(key)
    if open_trade and not open_trade.get("closed"):
        return False, "Trade already open"

    return True, "OK"


def can_send_ready_signal(market: str, symbol: str, signal: dict, ai_score: int):
    if signal.get("signal_type") not in ["BUY ENTRY READY", "SELL ENTRY READY"]:
        return False, "No confirmed entry"

    if avoid_news_window():
        return False, "News blocked"

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
    print("🔥 BOT V7 RUNNING", flush=True)

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
                    maybe_track_setup_outcome(market, symbol, signal)

                    ai_score, trigger_count, rr = build_ai_score(signal, session)
                    print(f"DEBUG SCORE: {symbol} ai={ai_score} triggers={trigger_count} rr={rr:.2f}", flush=True)

                    # WAIT
                    wait_allowed, wait_reason = can_send_wait_signal(market, symbol, signal)
                    if signal.get("signal_type") in ["WAIT ENTRY BUY", "WAIT ENTRY SELL"] and wait_allowed:
                        send_telegram(build_wait_message(market, symbol, signal, ai_score, session))
                        STATE["last_wait_time"][trade_key(market, symbol)] = int(time.time())
                        STATE["stats"]["waits_sent"] += 1
                        register_wait_setup(market, symbol, signal)
                        save_state()
                        print("👀 WAIT SENT:", symbol, flush=True)

                    # READY
                    ready_allowed, ready_reason = can_send_ready_signal(market, symbol, signal, ai_score)
                    if not ready_allowed:
                        print(symbol, "blocked:", ready_reason, flush=True)
                        continue

                    send_telegram(build_ready_message(market, symbol, signal, ai_score, session, trigger_count, rr))

                    key = trade_key(market, symbol)
                    STATE["last_signal_time"][key] = int(time.time())
                    STATE["last_signal_side"][key] = signal.get("preferred_side")
                    STATE["last_signal_score"][key] = ai_score
                    STATE["daily_count"] += 1
                    STATE["stats"]["signals_sent"] += 1

                    register_open_trade(market, symbol, signal, ai_score)
                    clear_tracked_setup(market, symbol)

                    if STATE["stats"]["signals_sent"] % 3 == 0:
                        send_stats()

                    save_state()
                    print("✅ READY SIGNAL SENT:", symbol, flush=True)

                except Exception as exc:
                    print("Worker symbol error:", symbol, exc, flush=True)

            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as exc:
            print("Worker loop error:", exc, flush=True)
            time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
