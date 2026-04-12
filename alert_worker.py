import time
import requests
from signal_engine import get_multi_timeframe_analysis, evaluate_signal_engine, format_price

# WICHTIG:
# Alten Telegram Token bei BotFather widerrufen und hier den NEUEN einsetzen.
TELEGRAM_BOT_TOKEN = "8785866877:AAHM-tze7VEOWcxGGcsVg0dWadheZX_Bhlw"
TELEGRAM_CHAT_ID = "1080439188"

SCAN_SYMBOLS = [
    ("crypto", "BTCUSDT"),
    ("forex", "XAU/USD"),
]

ALERT_COOLDOWN_SECONDS = 900  # 15 Minuten pro Symbol/Signal
SCAN_INTERVAL_SECONDS = 90

LAST_ALERTS = {}


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "PUT_YOUR_NEW_TELEGRAM_TOKEN_HERE":
        print("Telegram token fehlt.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=8)
    except Exception as exc:
        print("Telegram send error:", exc)


def build_message(market: str, symbol: str, signal: dict) -> str:
    return (
        f"{signal['signal_type']}\n"
        f"Market: {market.upper()} | Symbol: {symbol}\n"
        f"Preferred: {signal['preferred_side']} | Score: {signal['signal_score']}\n"
        f"Buy Zone: {format_price(signal['buy_zone_low'])} - {format_price(signal['buy_zone_high'])}\n"
        f"Sell Zone: {format_price(signal['sell_zone_low'])} - {format_price(signal['sell_zone_high'])}\n"
        f"Entry: {format_price(signal['entry_price'])}\n"
        f"SL: {format_price(signal['sl_price'])}\n"
        f"TP1 / TP2: {format_price(signal['tp1'])} / {format_price(signal['tp2'])}\n"
        f"TP M / L: {format_price(signal['tp_medium'])} / {format_price(signal['tp_large'])}\n"
        f"Fib 0.618: {format_price(signal['fib_618'])}\n"
        f"Session: {signal['session_name']}"
    )


def get_alert_type(signal: dict):
    signal_type = signal.get("signal_type", "")
    score = float(signal.get("signal_score", 0) or 0)

    if signal_type == "BUY ENTRY READY" and score >= 55:
        return "BUY_ENTRY_READY"
    if signal_type == "SELL ENTRY READY" and score >= 55:
        return "SELL_ENTRY_READY"
    if signal_type == "BUY ZONE ACTIVE" and score >= 45:
        return "BUY_ZONE_ACTIVE"
    if signal_type == "SELL ZONE ACTIVE" and score >= 45:
        return "SELL_ZONE_ACTIVE"
    return None


def maybe_send_alert(market: str, symbol: str, signal: dict):
    alert_type = get_alert_type(signal)
    if not alert_type:
        print(f"No strong alert for {symbol}: {signal.get('signal_type')} score={signal.get('signal_score')}")
        return

    key = f"{market}:{symbol}:{alert_type}"
    now = time.time()
    last_sent = LAST_ALERTS.get(key, 0)

    if now - last_sent < ALERT_COOLDOWN_SECONDS:
        print(f"Cooldown active for {key}")
        return

    msg = build_message(market, symbol, signal)
    send_telegram_message(msg)
    LAST_ALERTS[key] = now
    print(f"Alert sent: {key}")


def run_once():
    for market, symbol in SCAN_SYMBOLS:
        try:
            mtf = get_multi_timeframe_analysis(market, symbol)
            signal = evaluate_signal_engine(mtf)
            print(f"{symbol} -> {signal['signal_type']} | score={signal['signal_score']} | preferred={signal['preferred_side']}")
            maybe_send_alert(market, symbol, signal)
        except Exception as exc:
            err = f"Worker error on {symbol}: {exc}"
            print(err)


def main():
    print("Alert worker started. Symbols: BTCUSDT and XAU/USD")
    while True:
        run_once()
        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
