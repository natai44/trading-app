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

    strength = impulse / total
    if strength < 0.40:
        return None

    if c1["high"] < c3["low"]:
        return ("BUY", c1["high"], c3["low"])

    if c1["low"] > c3["high"]:
        return ("SELL", c3["high"], c1["low"])

    return None


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


def candle_buy(c):
    return c["close"] > c["open"]


def candle_sell(c):
    return c["close"] < c["open"]


def valid_tp(entry, sl, tp1):
    risk = abs(entry - sl)
    reward = abs(tp1 - entry)
    if risk <= 0:
        return False
    return reward >= risk * 0.7


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
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": None}

    c5 = data["c5"]
    c15 = data["c15"]
    c1h = data["c1h"]

    if not c5 or not c15 or not c1h or len(c5) < 5 or len(c15) < 30 or len(c1h) < 20:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": None}

    price = c5[0]["close"]
    last5 = c5[0]

    trend = trend_htf(c1h)
    if not trend:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    zone = active_fvg(c15)
    if not zone:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    side, zone_low, zone_high = zone

    if trend != side:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    # 1H position filter: don't buy too high / sell too low
    h1_high = recent_high(c1h, 0, 20)
    h1_low = recent_low(c1h, 0, 20)

    if h1_high is None or h1_low is None:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    h1_range = max(h1_high - h1_low, 1e-9)
    h1_pos = (price - h1_low) / h1_range

    if trend == "BUY" and h1_pos > 0.88:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    if trend == "SELL" and h1_pos < 0.12:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    # 15m zone, slightly flexible
    buffer = price * 0.001
    in_zone = (zone_low - buffer) <= price <= (zone_high + buffer)

    if not in_zone:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    # 5m entry timing only
    if trend == "BUY" and not candle_buy(last5):
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    if trend == "SELL" and not candle_sell(last5):
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    # BUY
    if trend == "BUY":
        sl_15 = recent_low(c15, 0, 5)
        sl_1h = recent_low(c1h, 0, 5)

        if sl_15 is None or sl_1h is None:
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

        sl = min(sl_15, sl_1h, zone_low)

        if sl >= price:
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

        tp1 = recent_high(c15, 5, 15)
        tp2 = recent_high(c15, 15, 30)
        tp_large = recent_high(c1h, 0, 20)

        if tp1 is None or tp2 is None or tp_large is None:
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

        risk = price - sl

        tp1 = max(tp1, price + risk * 0.8)
        tp2 = max(tp2, tp1)
        tp_large = max(tp_large, tp2)

        if not valid_tp(price, sl, tp1):
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

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

    # SELL
    if trend == "SELL":
        sl_15 = recent_high(c15, 0, 5)
        sl_1h = recent_high(c1h, 0, 5)

        if sl_15 is None or sl_1h is None:
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

        sl = max(sl_15, sl_1h, zone_high)

        if sl <= price:
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

        tp1 = recent_low(c15, 5, 15)
        tp2 = recent_low(c15, 15, 30)
        tp_large = recent_low(c1h, 0, 20)

        if tp1 is None or tp2 is None or tp_large is None:
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

        risk = sl - price

        tp1 = min(tp1, price - risk * 0.8)
        tp2 = min(tp2, tp1)
        tp_large = min(tp_large, tp2)

        if not valid_tp(price, sl, tp1):
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

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

    return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}
