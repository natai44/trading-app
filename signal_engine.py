import requests

BASE_URL = "https://api.twelvedata.com"
API_KEY = "8f8f55c79aa54b789bd3177ce55e224e"


def get_candles(symbol, interval, outputsize=100):
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


def format_price(x):
    try:
        return f"{float(x):,.2f}"
    except Exception:
        return "-"


# ---------------- TREND ----------------

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


# ---------------- FVG ----------------

def strong_fvg(candles):
    if len(candles) < 5:
        return None

    c1 = candles[2]
    c2 = candles[1]
    c3 = candles[0]

    impulse = abs(c2["close"] - c2["open"])
    total = c2["high"] - c2["low"]
    if total <= 0:
        return None

    strength = impulse / total
    if strength < 0.6:
        return None

    # BUY FVG
    if c1["high"] < c3["low"]:
        size = c3["low"] - c1["high"]
        if size < total * 0.5:
            return None
        return ("BUY", c1["high"], c3["low"])

    # SELL FVG
    if c1["low"] > c3["high"]:
        size = c1["low"] - c3["high"]
        if size < total * 0.5:
            return None
        return ("SELL", c3["high"], c1["low"])

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

    strength = impulse / total
    if strength < 0.45:
        return None

    # BUY FVG
    if c1["high"] < c3["low"]:
        size = c3["low"] - c1["high"]
        if size < total * 0.25:
            return None
        return ("BUY", c1["high"], c3["low"])

    # SELL FVG
    if c1["low"] > c3["high"]:
        size = c1["low"] - c3["high"]
        if size < total * 0.25:
            return None
        return ("SELL", c3["high"], c1["low"])

    return None


# ---------------- SWEEP ----------------

def detect_sweep(candles):
    if len(candles) < 5:
        return None

    last = candles[0]
    prev_high = max(c["high"] for c in candles[1:5])
    prev_low = min(c["low"] for c in candles[1:5])

    if last["high"] > prev_high and last["close"] < prev_high:
        return "SELL"

    if last["low"] < prev_low and last["close"] > prev_low:
        return "BUY"

    return None


# ---------------- CANDLE ----------------

def strong_bull(c):
    total = c["high"] - c["low"]
    if total <= 0:
        return False
    body = c["close"] - c["open"]
    return (
        c["close"] > c["open"]
        and body > total * 0.70
        and c["close"] > c["high"] - total * 0.25
    )


def strong_bear(c):
    total = c["high"] - c["low"]
    if total <= 0:
        return False
    body = c["open"] - c["close"]
    return (
        c["close"] < c["open"]
        and body > total * 0.70
        and c["close"] < c["low"] + total * 0.25
    )


def active_bull(c):
    total = c["high"] - c["low"]
    if total <= 0:
        return False
    body = c["close"] - c["open"]
    return (
        c["close"] > c["open"]
        and body > total * 0.50
    )


def active_bear(c):
    total = c["high"] - c["low"]
    if total <= 0:
        return False
    body = c["open"] - c["close"]
    return (
        c["close"] < c["open"]
        and body > total * 0.50
    )


# ---------------- MAIN ----------------

def get_multi_timeframe_analysis(market, symbol):
    c15 = get_candles(symbol, "15min")
    c1h = get_candles(symbol, "1h")

    if not c15 or not c1h:
        return {}

    return {
        "c15": [to_float(c) for c in c15],
        "c1h": [to_float(c) for c in c1h],
    }


def evaluate_signal_engine(data):
    if not data:
        return {
            "signal_type": "NO CLEAR SETUP",
            "trigger_price": None,
        }

    c15 = data["c15"]
    c1h = data["c1h"]

    if not c15 or not c1h:
        return {
            "signal_type": "NO CLEAR SETUP",
            "trigger_price": None,
        }

    price = c15[0]["close"]
    last = c15[0]

    trend = trend_htf(c1h)
    if not trend:
        return {
            "signal_type": "NO CLEAR SETUP",
            "trigger_price": price,
        }

    strict_zone = strong_fvg(c15)
    loose_zone = active_fvg(c15)
    sweep = detect_sweep(c15)

    # =======================
    # PRO MODE FIRST
    # =======================
    if strict_zone:
        side, low, high = strict_zone
        in_zone = low <= price <= high

        if (
            trend == side
            and sweep == trend
            and in_zone
        ):
            if trend == "BUY" and strong_bull(last):
                entry = price
                sl = low - entry * 0.002
                risk = entry - sl
                return {
                    "signal_type": "BUY ENTRY READY",
                    "preferred_side": "BUY",
                    "entry_price": entry,
                    "sl_price": sl,
                    "tp1": entry + risk * 1.0,
                    "tp2": entry + risk * 2.0,
                    "tp_large": entry + risk * 4.0,
                    "trigger_price": price,
                    "setup_mode": "PRO",
                    "signal_score": 95,
                }

            if trend == "SELL" and strong_bear(last):
                entry = price
                sl = high + entry * 0.002
                risk = sl - entry
                return {
                    "signal_type": "SELL ENTRY READY",
                    "preferred_side": "SELL",
                    "entry_price": entry,
                    "sl_price": sl,
                    "tp1": entry - risk * 1.0,
                    "tp2": entry - risk * 2.0,
                    "tp_large": entry - risk * 4.0,
                    "trigger_price": price,
                    "setup_mode": "PRO",
                    "signal_score": 95,
                }

    # =======================
    # ACTIVE MODE SECOND
    # =======================
    if loose_zone:
        side, low, high = loose_zone
        buffer = price * 0.0008
        in_zone = (low - buffer) <= price <= (high + buffer)

        sweep_ok = (sweep == trend) or (sweep is None)
        momentum_ok = (
            (trend == "BUY" and last["close"] > last["open"])
            or (trend == "SELL" and last["close"] < last["open"])
        )

        if trend == side and in_zone and sweep_ok and momentum_ok:
            if trend == "BUY" and active_bull(last):
                entry = price
                sl = low - entry * 0.0018
                risk = entry - sl
                return {
                    "signal_type": "BUY ENTRY READY",
                    "preferred_side": "BUY",
                    "entry_price": entry,
                    "sl_price": sl,
                    "tp1": entry + risk * 1.0,
                    "tp2": entry + risk * 1.8,
                    "tp_large": entry + risk * 3.0,
                    "trigger_price": price,
                    "setup_mode": "ACTIVE",
                    "signal_score": 78,
                }

            if trend == "SELL" and active_bear(last):
                entry = price
                sl = high + entry * 0.0018
                risk = sl - entry
                return {
                    "signal_type": "SELL ENTRY READY",
                    "preferred_side": "SELL",
                    "entry_price": entry,
                    "sl_price": sl,
                    "tp1": entry - risk * 1.0,
                    "tp2": entry - risk * 1.8,
                    "tp_large": entry - risk * 3.0,
                    "trigger_price": price,
                    "setup_mode": "ACTIVE",
                    "signal_score": 78,
                }

    return {
        "signal_type": "NO CLEAR SETUP",
        "trigger_price": price,
    }
