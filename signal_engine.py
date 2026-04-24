import requests

BASE_URL = "https://api.twelvedata.com"
API_KEY = "8f8f55c79aa54b789bd3177ce55e224e"


def get_candles(symbol, interval, outputsize=120):
    url = f"{BASE_URL}/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": API_KEY,
        "outputsize": outputsize,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        return r.json().get("values", [])
    except Exception:
        return []


def to_float(c):
    return {
        "open": float(c["open"]),
        "high": float(c["high"]),
        "low": float(c["low"]),
        "close": float(c["close"]),
    }


def trend_htf(candles):
    if len(candles) < 20:
        return None

    last = candles[0]["close"]
    prev = candles[10]["close"]

    if last > prev:
        return "BUY"
    if last < prev:
        return "SELL"
    return None


def active_fvg(candles):
    if len(candles) < 5:
        return None

    c1 = candles[2]
    c2 = candles[1]
    c3 = candles[0]

    impulse = abs(c2["close"] - c2["open"])
    total = c2["high"] - c2["low"]

    if total <= 0:
        return None

    if impulse / total < 0.4:
        return None

    if c1["high"] < c3["low"]:
        return ("BUY", c1["high"], c3["low"])

    if c1["low"] > c3["high"]:
        return ("SELL", c3["high"], c1["low"])

    return None


def active_bull(c):
    return c["close"] > c["open"]


def active_bear(c):
    return c["close"] < c["open"]


def get_multi_timeframe_analysis(market, symbol):
    c5 = get_candles(symbol, "5min")
    c15 = get_candles(symbol, "15min")
    c1h = get_candles(symbol, "1h")

    if not c5 or not c15 or not c1h:
        return {}

    return {
        "c5": [to_float(c) for c in c5],
        "c15": [to_float(c) for c in c15],
        "c1h": [to_float(c) for c in c1h],
    }


def evaluate_signal_engine(data):

    if not data:
        return {"signal_type": "NO CLEAR SETUP"}

    c5 = data["c5"]
    c15 = data["c15"]
    c1h = data["c1h"]

    price = c5[0]["close"]
    last5 = c5[0]

    trend = trend_htf(c1h)
    fvg = active_fvg(c15)

    if not trend or not fvg:
        return {"signal_type": "NO CLEAR SETUP"}

    side, low, high = fvg

    if trend != side:
        return {"signal_type": "NO CLEAR SETUP"}

    # Zone Check
    buffer = price * 0.001
    in_zone = (low - buffer) <= price <= (high + buffer)

    if not in_zone:
        return {"signal_type": "NO CLEAR SETUP"}

    # 5m Entry Timing
    if trend == "BUY" and not active_bull(last5):
        return {"signal_type": "NO CLEAR SETUP"}

    if trend == "SELL" and not active_bear(last5):
        return {"signal_type": "NO CLEAR SETUP"}

    # SL bleibt Struktur (15m)
    if trend == "BUY":
        sl = min(c["low"] for c in c15[:5])
        if sl >= price:
            return {"signal_type": "NO CLEAR SETUP"}

        risk = price - sl

        return {
            "signal_type": "BUY ENTRY READY",
            "preferred_side": "BUY",
            "entry_price": price,
            "sl_price": sl,
            "tp1": price + risk * 1,
            "tp2": price + risk * 2,
            "tp_large": price + risk * 3,
            "trigger_price": price,
            "setup_mode": "ACTIVE",
            "signal_score": 80,
        }

    if trend == "SELL":
        sl = max(c["high"] for c in c15[:5])
        if sl <= price:
            return {"signal_type": "NO CLEAR SETUP"}

        risk = sl - price

        return {
            "signal_type": "SELL ENTRY READY",
            "preferred_side": "SELL",
            "entry_price": price,
            "sl_price": sl,
            "tp1": price - risk * 1,
            "tp2": price - risk * 2,
            "tp_large": price - risk * 3,
            "trigger_price": price,
            "setup_mode": "ACTIVE",
            "signal_score": 80,
        }

    return {"signal_type": "NO CLEAR SETUP"}
