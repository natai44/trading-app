import requests

# ---------------- CONFIG ----------------

BASE_URL = "https://api.twelvedata.com"
API_KEY = "8f8f55c79aa54b789bd3177ce55e224e"

TIMEFRAME_MAIN = "15min"
TIMEFRAME_HIGH = "1h"

# ---------------- API ----------------

def get_candles(symbol: str, interval: str, outputsize=100):
    url = f"{BASE_URL}/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": API_KEY,
        "outputsize": outputsize,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return data.get("values", [])
    except:
        return []

# ---------------- HELPERS ----------------

def format_price(x):
    try:
        return f"{float(x):,.2f}"
    except:
        return "-"

def to_float(c):
    return {
        "open": float(c["open"]),
        "high": float(c["high"]),
        "low": float(c["low"]),
        "close": float(c["close"]),
    }

# ---------------- CANDLE LOGIC ----------------

def bullish_candle(c):
    total = c["high"] - c["low"]
    body = c["close"] - c["open"]
    return (
        c["close"] > c["open"]
        and body > total * 0.6
        and c["close"] > c["high"] - total * 0.2
    )

def bearish_candle(c):
    total = c["high"] - c["low"]
    body = c["open"] - c["close"]
    return (
        c["close"] < c["open"]
        and body > total * 0.6
        and c["close"] < c["low"] + total * 0.2
    )

# ---------------- STRUCTURE ----------------

def detect_trend(candles):
    if len(candles) < 20:
        return "NONE"
    last = candles[0]["close"]
    prev = candles[10]["close"]

    if last > prev:
        return "BUY"
    elif last < prev:
        return "SELL"
    return "NONE"

# ---------------- FVG ----------------

def detect_fvg(candles):
    if len(candles) < 3:
        return None

    c1 = candles[2]
    c2 = candles[1]
    c3 = candles[0]

    # bullish gap
    if c1["high"] < c3["low"]:
        return ("BUY", c1["high"], c3["low"])

    # bearish gap
    if c1["low"] > c3["high"]:
        return ("SELL", c3["high"], c1["low"])

    return None

# ---------------- MAIN ANALYSIS ----------------

def get_multi_timeframe_analysis(market, symbol):
    candles_15 = get_candles(symbol, TIMEFRAME_MAIN)
    candles_1h = get_candles(symbol, TIMEFRAME_HIGH)

    if not candles_15 or not candles_1h:
        return {}

    candles_15 = [to_float(c) for c in candles_15]
    candles_1h = [to_float(c) for c in candles_1h]

    return {
        "candles_15": candles_15,
        "candles_1h": candles_1h,
    }

# ---------------- SIGNAL ENGINE ----------------

def evaluate_signal_engine(data):

    if not data:
        return {"signal_type": "NO CLEAR SETUP"}

    candles = data["candles_15"]
    candles_h = data["candles_1h"]

    current_price = candles[0]["close"]

    trend = detect_trend(candles_h)

    fvg = detect_fvg(candles)

    if not fvg:
        return {"signal_type": "NO CLEAR SETUP"}

    fvg_side, zone_low, zone_high = fvg

    if trend != fvg_side:
        return {"signal_type": "NO CLEAR SETUP"}

    last = candles[0]

    # ---------------- WAIT MODE ----------------

    if trend == "BUY":
        return {
            "signal_type": "WAIT ENTRY BUY",
            "preferred_side": "BUY",
            "wait_zone_low": zone_low,
            "wait_zone_high": zone_high,
            "wait_entry_price": (zone_low + zone_high) / 2,
            "trigger_price": current_price,
            "setup_mode": "SAFE",
            "signal_score": 70,
        }

    if trend == "SELL":
        return {
            "signal_type": "WAIT ENTRY SELL",
            "preferred_side": "SELL",
            "wait_zone_low": zone_low,
            "wait_zone_high": zone_high,
            "wait_entry_price": (zone_low + zone_high) / 2,
            "trigger_price": current_price,
            "setup_mode": "SAFE",
            "signal_score": 70,
        }

    # ---------------- ENTRY CONFIRMATION ----------------

    in_zone = zone_low <= current_price <= zone_high

    if trend == "BUY" and in_zone and bullish_candle(last):
        entry = current_price
        sl = zone_low - entry * 0.002
        risk = entry - sl

        return {
            "signal_type": "BUY ENTRY READY",
            "preferred_side": "BUY",
            "entry_price": entry,
            "sl_price": sl,
            "tp1": entry + risk * 1.0,
            "tp2": entry + risk * 2.0,
            "tp_large": entry + risk * 3.5,
            "trigger_price": current_price,
            "setup_mode": "SAFE",
            "signal_score": 85,
        }

    if trend == "SELL" and in_zone and bearish_candle(last):
        entry = current_price
        sl = zone_high + entry * 0.002
        risk = sl - entry

        return {
            "signal_type": "SELL ENTRY READY",
            "preferred_side": "SELL",
            "entry_price": entry,
            "sl_price": sl,
            "tp1": entry - risk * 1.0,
            "tp2": entry - risk * 2.0,
            "tp_large": entry - risk * 3.5,
            "trigger_price": current_price,
            "setup_mode": "SAFE",
            "signal_score": 85,
        }

    return {"signal_type": "NO CLEAR SETUP"}
