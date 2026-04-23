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


# ---------------- FVG / ZONE ----------------

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
    if strength < 0.40:
        return None

    # BUY FVG
    if c1["high"] < c3["low"]:
        size = c3["low"] - c1["high"]
        if size < total * 0.20:
            return None
        return ("BUY", c1["high"], c3["low"])

    # SELL FVG
    if c1["low"] > c3["high"]:
        size = c1["low"] - c3["high"]
        if size < total * 0.20:
            return None
        return ("SELL", c3["high"], c1["low"])

    return None


# ---------------- CANDLE / MOMENTUM ----------------

def active_bull(c):
    total = c["high"] - c["low"]
    if total <= 0:
        return False
    body = c["close"] - c["open"]
    return c["close"] > c["open"] and body > total * 0.50


def active_bear(c):
    total = c["high"] - c["low"]
    if total <= 0:
        return False
    body = c["open"] - c["close"]
    return c["close"] < c["open"] and body > total * 0.50


# ---------------- STRUCTURE HELPERS ----------------

def recent_high(candles, start, end):
    chunk = candles[start:end]
    if not chunk:
        return None
    return max(c["high"] for c in chunk)


def recent_low(candles, start, end):
    chunk = candles[start:end]
    if not chunk:
        return None
    return min(c["low"] for c in chunk)


def valid_tp_distance(entry, sl, tp1):
    risk = abs(entry - sl)
    reward = abs(tp1 - entry)
    if risk <= 0:
        return False
    return reward >= risk * 0.7


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

    if not c15 or not c1h or len(c15) < 30 or len(c1h) < 20:
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

    zone = active_fvg(c15)
    if not zone:
        return {
            "signal_type": "NO CLEAR SETUP",
            "trigger_price": price,
        }

    side, low, high = zone

    if trend != side:
        return {
            "signal_type": "NO CLEAR SETUP",
            "trigger_price": price,
        }

    # 1H context filter: avoid buying too high / selling too low
    h1_high = recent_high(c1h, 0, 20)
    h1_low = recent_low(c1h, 0, 20)
    if h1_high is None or h1_low is None:
        return {
            "signal_type": "NO CLEAR SETUP",
            "trigger_price": price,
        }

    h1_range = max(h1_high - h1_low, 1e-9)
    h1_pos = (price - h1_low) / h1_range  # 0 = bottom, 1 = top

    if trend == "BUY" and h1_pos > 0.88:
        return {
            "signal_type": "NO CLEAR SETUP",
            "trigger_price": price,
        }

    if trend == "SELL" and h1_pos < 0.12:
        return {
            "signal_type": "NO CLEAR SETUP",
            "trigger_price": price,
        }

    # Wider active zone so bot is not too strict
    buffer = price * 0.001
    in_zone = (low - buffer) <= price <= (high + buffer)

    if not in_zone:
        return {
            "signal_type": "NO CLEAR SETUP",
            "trigger_price": price,
        }

    # momentum / confirmation, but not overly strict
    momentum_ok = (
        (trend == "BUY" and active_bull(last))
        or (trend == "SELL" and active_bear(last))
    )

    if not momentum_ok:
        return {
            "signal_type": "NO CLEAR SETUP",
            "trigger_price": price,
        }

    # ---------------- SL / TP by structure ----------------

    if trend == "BUY":
        swing_low_15 = recent_low(c15, 0, 5)
        swing_low_1h = recent_low(c1h, 0, 5)

        if swing_low_15 is None or swing_low_1h is None:
            return {
                "signal_type": "NO CLEAR SETUP",
                "trigger_price": price,
            }

        sl = min(swing_low_15, swing_low_1h, low)
        if sl >= price:
            return {
                "signal_type": "NO CLEAR SETUP",
                "trigger_price": price,
            }

        tp1 = recent_high(c15, 5, 15)
        tp2 = recent_high(c15, 15, 30)
        tp_large = recent_high(c1h, 0, 20)

        if tp1 is None or tp2 is None or tp_large is None:
            return {
                "signal_type": "NO CLEAR SETUP",
                "trigger_price": price,
            }

        # keep logical ordering
        tp1 = max(tp1, price + (price - sl) * 0.8)
        tp2 = max(tp2, tp1)
        tp_large = max(tp_large, tp2)

        if not valid_tp_distance(price, sl, tp1):
            return {
                "signal_type": "NO CLEAR SETUP",
                "trigger_price": price,
            }

        return {
            "signal_type": "BUY ENTRY READY",
            "preferred_side": "BUY",
            "entry_price": price,
            "sl_price": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp_large": tp_large,
            "trigger_price": price,
            "setup_mode": "ACTIVE",
            "signal_score": 82,
        }

    if trend == "SELL":
        swing_high_15 = recent_high(c15, 0, 5)
        swing_high_1h = recent_high(c1h, 0, 5)

        if swing_high_15 is None or swing_high_1h is None:
            return {
                "signal_type": "NO CLEAR SETUP",
                "trigger_price": price,
            }

        sl = max(swing_high_15, swing_high_1h, high)
        if sl <= price:
            return {
                "signal_type": "NO CLEAR SETUP",
                "trigger_price": price,
            }

        tp1 = recent_low(c15, 5, 15)
        tp2 = recent_low(c15, 15, 30)
        tp_large = recent_low(c1h, 0, 20)

        if tp1 is None or tp2 is None or tp_large is None:
            return {
                "signal_type": "NO CLEAR SETUP",
                "trigger_price": price,
            }

        # keep logical ordering
        tp1 = min(tp1, price - (sl - price) * 0.8)
        tp2 = min(tp2, tp1)
        tp_large = min(tp_large, tp2)

        if not valid_tp_distance(price, sl, tp1):
            return {
                "signal_type": "NO CLEAR SETUP",
                "trigger_price": price,
            }

        return {
            "signal_type": "SELL ENTRY READY",
            "preferred_side": "SELL",
            "entry_price": price,
            "sl_price": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp_large": tp_large,
            "trigger_price": price,
            "setup_mode": "ACTIVE",
            "signal_score": 82,
        }

    return {
        "signal_type": "NO CLEAR SETUP",
        "trigger_price": price,
    }
