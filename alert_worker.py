import time
import requests

# 🔥 DEIN TELEGRAM (NEUEN TOKEN HIER EINFÜGEN!)
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = "1080439188"

# 🔄 API (gleich wie in main.py)
TWELVE_DATA_API_KEY = "8f8f55c79aa54b789bd3177ce55e224e"

# ⏱ Cooldown gegen Spam
LAST_ALERTS = {}
COOLDOWN = 900  # 15 Minuten


# 📊 Daten holen
def get_data(symbol):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "5min",
        "outputsize": 50,
        "apikey": TWELVE_DATA_API_KEY,
    }

    r = requests.get(url, params=params)
    data = r.json()

    if "values" not in data:
        return None

    candles = list(reversed(data["values"]))
    closes = [float(c["close"]) for c in candles]

    return closes


# 📈 einfache Logik (stabil & sicher)
def analyze(symbol):
    closes = get_data(symbol)
    if not closes:
        return None

    current = closes[-1]
    sma_fast = sum(closes[-5:]) / 5
    sma_slow = sum(closes[-20:]) / 20

    if sma_fast > sma_slow:
        trend = "BUY"
    elif sma_fast < sma_slow:
        trend = "SELL"
    else:
        trend = "NONE"

    return {
        "trend": trend,
        "price": current
    }


# 📩 Telegram senden
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg
        })
    except:
        pass


# 🚨 Alert Logik
def check_alert(symbol):
    data = analyze(symbol)
    if not data:
        return

    trend = data["trend"]
    price = data["price"]

    key = f"{symbol}_{trend}"
    now = time.time()

    if key in LAST_ALERTS:
        if now - LAST_ALERTS[key] < COOLDOWN:
            return

    if trend == "BUY":
        msg = f"🚀 BUY SIGNAL\n{symbol}\nPrice: {price}"
        send_telegram(msg)
        LAST_ALERTS[key] = now

    elif trend == "SELL":
        msg = f"🔥 SELL SIGNAL\n{symbol}\nPrice: {price}"
        send_telegram(msg)
        LAST_ALERTS[key] = now


# 🔁 MAIN LOOP
def run():
    while True:
        try:
            print("Scanning...")

            # 🔥 NUR BTC + GOLD
            check_alert("BTCUSDT")
            check_alert("XAU/USD")

            time.sleep(60)  # jede 60 Sekunden

        except Exception as e:
            print("Error:", e)
            time.sleep(60)


if __name__ == "__main__":
    run()
