import time
import requests
from signal_engine import get_multi_timeframe_analysis, evaluate_signal_engine, format_price

# ==========================
# TELEGRAM CONFIG
# ==========================

TELEGRAM_BOT_TOKEN = "8785866877:AAHM-tze7VEOWcxGGcsVg0dWadheZX_Bhlw"
TELEGRAM_CHAT_ID = "1080439188"

SCAN_SYMBOLS = [
    ("crypto", "BTCUSDT"),
    ("forex", "XAU/USD"),
]

SCAN_INTERVAL_SECONDS = 90


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg
        }, timeout=5)
    except Exception as e:
        print("Telegram error:", e)


def build_message(market, symbol, signal):
    return f"""
{signal['signal_type']}

Market: {market}
Symbol: {symbol}

Entry: {format_price(signal['entry_price'])}
SL: {format_price(signal['sl_price'])}

TP: {format_price(signal['tp1'])}
"""


def run():
    print("Worker läuft...")

    while True:
        for market, symbol in SCAN_SYMBOLS:
            try:
                mtf = get_multi_timeframe_analysis(market, symbol)
                signal = evaluate_signal_engine(mtf)

                print(symbol, signal["signal_type"])

                if signal["signal_type"] in ["BUY ENTRY READY", "SELL ENTRY READY"]:
                    msg = build_message(market, symbol, signal)
                    send_telegram(msg)

            except Exception as e:
                print("Error:", e)

        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
