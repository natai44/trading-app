import requests

BASE_URL = "https://api.twelvedata.com"
API_KEY = "8f8f55c79aa54b789bd3177ce55e224e"


def get_candles(symbol, interval, outputsize=120):
    try:
        r = requests.get(
            f"{BASE_URL}/time_series",
            params={
                "symbol": symbol,
                "interval": interval,
                "apikey": API_KEY,
                "outputsize": outputsize,
            },
            timeout=10,
        )
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


def recent_high(candles, start, end):
    part = candles[start:end]
    if not part:
        return None
    return max(c["high"] for c in part)


def recent_low(candles, start, end):
    part = candles[start:end]
    if not part:
        return None
    return min(c["low"] for c in part)


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

    if impulse / total < 0.35:
        return None

    if c1["high"] < c3["low"]:
        return ("BUY", c1["high"], c3["low"])

    if c1["low"] > c3["high"]:
        return ("SELL", c3["high"], c1["low"])

    return None


def candle_buy(c):
    return c["close"] > c["open"]


def candle_sell(c):
    return c["close"] < c["open"]


def john_wick_buy(c):
    body = abs(c["close"] - c["open"])
    total = c["high"] - c["low"]

    if total <= 0:
        return False

    lower_wick = min(c["open"], c["close"]) - c["low"]
    upper_wick = c["high"] - max(c["open"], c["close"])

    return (
        c["close"] > c["open"]
        and lower_wick > body * 1.5
        and lower_wick > upper_wick
    )


def john_wick_sell(c):
    body = abs(c["close"] - c["open"])
    total = c["high"] - c["low"]

    if total <= 0:
        return False

    upper_wick = c["high"] - max(c["open"], c["close"])
    lower_wick = min(c["open"], c["close"]) - c["low"]

    return (
        c["close"] < c["open"]
        and upper_wick > body * 1.5
        and upper_wick > lower_wick
    )


def get_d1_levels(c1d):
    if len(c1d) < 2:
        return None, None

    yesterday = c1d[1]
    return yesterday["high"], yesterday["low"]


def get_d1_bias(price, c15, c1h, d1_high, d1_low):
    threshold = price * 0.003

    near_high = abs(price - d1_high) <= threshold
    near_low = abs(price - d1_low) <= threshold

    recent_15_high = recent_high(c15, 0, 8)
    recent_15_low = recent_low(c15, 0, 8)
    recent_1h_high = recent_high(c1h, 0, 4)
    recent_1h_low = recent_low(c1h, 0, 4)

    if None in [recent_15_high, recent_15_low, recent_1h_high, recent_1h_low]:
        return None

    # Rejection / sweep from D1 high
    if near_high or (recent_15_high > d1_high and price < d1_high) or (recent_1h_high > d1_high and price < d1_high):
        return "SELL"

    # Rejection / sweep from D1 low
    if near_low or (recent_15_low < d1_low and price > d1_low) or (recent_1h_low < d1_low and price > d1_low):
        return "BUY"

    # Breakout continuation above D1 high
    if price > d1_high + threshold:
        return "BUY"

    # Breakout continuation below D1 low
    if price < d1_low - threshold:
        return "SELL"

    return None


def valid_rr(entry, sl, tp1):
    risk = abs(entry - sl)
    reward = abs(tp1 - entry)

    if risk <= 0:
        return False

    return reward >= risk * 0.75


def get_multi_timeframe_analysis(market, symbol):
    c5 = get_candles(symbol, "5min")
    c15 = get_candles(symbol, "15min")
    c1h = get_candles(symbol, "1h")
    c1d = get_candles(symbol, "1day", outputsize=10)

    if not c5 or not c15 or not c1h or not c1d:
        return {}

    return {
        "c5": [to_float(c) for c in c5],
        "c15": [to_float(c) for c in c15],
        "c1h": [to_float(c) for c in c1h],
        "c1d": [to_float(c) for c in c1d],
    }


def evaluate_signal_engine(data):
    if not data:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": None}

    c5 = data.get("c5", [])
    c15 = data.get("c15", [])
    c1h = data.get("c1h", [])
    c1d = data.get("c1d", [])

    if len(c5) < 5 or len(c15) < 30 or len(c1h) < 20 or len(c1d) < 2:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": None}

    price = c5[0]["close"]
    last5 = c5[0]

    d1_high, d1_low = get_d1_levels(c1d)

    if d1_high is None or d1_low is None:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    direction = get_d1_bias(price, c15, c1h, d1_high, d1_low)

    if not direction:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    fvg = active_fvg(c15)

    if not fvg:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    fvg_side, zone_low, zone_high = fvg

    if fvg_side != direction:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    buffer = price * 0.0015
    in_zone = (zone_low - buffer) <= price <= (zone_high + buffer)

    if not in_zone:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    if direction == "BUY":
        entry_ok = candle_buy(last5) or john_wick_buy(last5)
    else:
        entry_ok = candle_sell(last5) or john_wick_sell(last5)

    if not entry_ok:
        return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

    if direction == "BUY":
        sl_15 = recent_low(c15, 0, 8)
        sl_1h = recent_low(c1h, 0, 4)

        if sl_15 is None or sl_1h is None:
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

        sl = min(sl_15, sl_1h, zone_low)

        if sl >= price:
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

        risk = price - sl

        tp1_struct = recent_high(c15, 5, 20)
        tp2_struct = recent_high(c1h, 0, 20)

        if tp1_struct is None or tp2_struct is None:
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

        tp1 = max(tp1_struct, price + risk * 1.0)
        tp2 = max(tp2_struct, tp1, price + risk * 1.7)
        tp_large = max(d1_high, tp2, price + risk * 2.5)

        if not valid_rr(price, sl, tp1):
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
            "signal_score": 86,
        }

    if direction == "SELL":
        sl_15 = recent_high(c15, 0, 8)
        sl_1h = recent_high(c1h, 0, 4)

        if sl_15 is None or sl_1h is None:
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

        sl = max(sl_15, sl_1h, zone_high)

        if sl <= price:
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

        risk = sl - price

        tp1_struct = recent_low(c15, 5, 20)
        tp2_struct = recent_low(c1h, 0, 20)

        if tp1_struct is None or tp2_struct is None:
            return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}

        tp1 = min(tp1_struct, price - risk * 1.0)
        tp2 = min(tp2_struct, tp1, price - risk * 1.7)
        tp_large = min(d1_low, tp2, price - risk * 2.5)

        if not valid_rr(price, sl, tp1):
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
            "signal_score": 86,
        }

    return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}
