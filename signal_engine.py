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


def no_setup(price=None):
    return {"signal_type": "NO CLEAR SETUP", "trigger_price": price}


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


def get_d1_levels(c1d):
    if len(c1d) < 2:
        return None, None
    prev_day = c1d[1]
    return prev_day["high"], prev_day["low"]


def wick_buy_1h(c):
    body = abs(c["close"] - c["open"])
    total = c["high"] - c["low"]
    if total <= 0:
        return False

    lower_wick = min(c["open"], c["close"]) - c["low"]
    upper_wick = c["high"] - max(c["open"], c["close"])

    return (
        c["close"] > c["open"]
        and lower_wick > body * 1.3
        and lower_wick > upper_wick
    )


def wick_sell_1h(c):
    body = abs(c["close"] - c["open"])
    total = c["high"] - c["low"]
    if total <= 0:
        return False

    upper_wick = c["high"] - max(c["open"], c["close"])
    lower_wick = min(c["open"], c["close"]) - c["low"]

    return (
        c["close"] < c["open"]
        and upper_wick > body * 1.3
        and upper_wick > lower_wick
    )


def sweep_buy(c1h, d1_low):
    last = c1h[1]
    prev_low = recent_low(c1h, 2, 8)
    if prev_low is None:
        return False

    return (
        last["low"] < prev_low and last["close"] > prev_low
    ) or (
        last["low"] < d1_low and last["close"] > d1_low
    )


def sweep_sell(c1h, d1_high):
    last = c1h[1]
    prev_high = recent_high(c1h, 2, 8)
    if prev_high is None:
        return False

    return (
        last["high"] > prev_high and last["close"] < prev_high
    ) or (
        last["high"] > d1_high and last["close"] < d1_high
    )


def rejection_buy_1h(c, d1_low):
    return c["low"] <= d1_low and c["close"] > d1_low


def rejection_sell_1h(c, d1_high):
    return c["high"] >= d1_high and c["close"] < d1_high


def active_fvg(c15):
    if len(c15) < 5:
        return None

    c1 = c15[3]
    c2 = c15[2]
    c3 = c15[1]

    total = c2["high"] - c2["low"]
    impulse = abs(c2["close"] - c2["open"])

    if total <= 0:
        return None

    if impulse / total < 0.30:
        return None

    if c1["high"] < c3["low"]:
        return ("BUY", c1["high"], c3["low"])

    if c1["low"] > c3["high"]:
        return ("SELL", c3["high"], c1["low"])

    return None


def valid_rr(entry, sl, tp1):
    risk = abs(entry - sl)
    reward = abs(tp1 - entry)
    return risk > 0 and reward >= risk * 0.70


def build_buy(price, sl, tp1, tp2, tp_large, mode, score):
    tp1 = price + 25
    tp2 = price + 50
    tp_large = price + 90

    return {
        "signal_type": "BUY ENTRY READY",
        "preferred_side": "BUY",
        "entry_price": price,
        "sl_price": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp_large": tp_large,
        "trigger_price": price,
        "setup_mode": mode,
        "signal_score": score,
    }


def build_sell(price, sl, tp1, tp2, tp_large, mode, score):
    tp1 = price - 25
    tp2 = price - 50
    tp_large = price - 90

    return {
        "signal_type": "SELL ENTRY READY",
        "preferred_side": "SELL",
        "entry_price": price,
        "sl_price": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp_large": tp_large,
        "trigger_price": price,
        "setup_mode": mode,
        "signal_score": score,
    }


def get_multi_timeframe_analysis(market, symbol):
    c15 = get_candles(symbol, "15min")
    c1h = get_candles(symbol, "1h")
    c1d = get_candles(symbol, "1day", outputsize=10)

    if not c15 or not c1h or not c1d:
        return {}

    return {
        "c15": [to_float(c) for c in c15],
        "c1h": [to_float(c) for c in c1h],
        "c1d": [to_float(c) for c in c1d],
    }


def evaluate_signal_engine(data):
    if not data:
        return no_setup(None)

    c15 = data.get("c15", [])
    c1h = data.get("c1h", [])
    c1d = data.get("c1d", [])

    if len(c15) < 30 or len(c1h) < 20 or len(c1d) < 2:
        return no_setup(None)

    price = c15[0]["close"]
    last_1h = c1h[1]

    d1_high, d1_low = get_d1_levels(c1d)
    if d1_high is None or d1_low is None:
        return no_setup(price)

    d1_range = max(d1_high - d1_low, 1e-9)
    d1_mid = (d1_high + d1_low) / 2

    zone_buffer = d1_range * 0.12
    breakout_buffer = d1_range * 0.03
    retest_buffer = d1_range * 0.08

    near_d1_low = price <= d1_low + zone_buffer
    near_d1_high = price >= d1_high - zone_buffer

    breakout_buy = last_1h["close"] > d1_high + breakout_buffer
    breakout_sell = last_1h["close"] < d1_low - breakout_buffer

    fvg = active_fvg(c15)

    # =========================
    # D1 ZONE BUY
    # D1 Zone → 1H Wick/Sweep/Rejection → Entry
    # =========================
    if near_d1_low and not breakout_sell:
        confirmation = (
            wick_buy_1h(last_1h)
            or sweep_buy(c1h, d1_low)
            or rejection_buy_1h(last_1h, d1_low)
        )

        if not confirmation:
            return no_setup(price)

        sl_struct = recent_low(c1h, 1, 8)
        if sl_struct is None:
            return no_setup(price)

        sl = min(sl_struct, last_1h["low"], d1_low)

        if sl >= price:
            return no_setup(price)

        risk = price - sl

        tp1 = max(d1_mid, price + risk * 1.0)
        tp2 = max(d1_high, tp1, price + risk * 1.7)
        tp_large = max(d1_high + d1_range * 0.25, tp2, price + risk * 2.5)

        if not valid_rr(price, sl, tp1):
            return no_setup(price)

        return build_buy(price, sl, tp1, tp2, tp_large, "D1_ZONE_BUY", 90)

    # =========================
    # D1 ZONE SELL
    # D1 Zone → 1H Wick/Sweep/Rejection → Entry
    # =========================
    if near_d1_high and not breakout_buy:
        confirmation = (
            wick_sell_1h(last_1h)
            or sweep_sell(c1h, d1_high)
            or rejection_sell_1h(last_1h, d1_high)
        )

        if not confirmation:
            return no_setup(price)

        sl_struct = recent_high(c1h, 1, 8)
        if sl_struct is None:
            return no_setup(price)

        sl = max(sl_struct, last_1h["high"], d1_high)

        if sl <= price:
            return no_setup(price)

        risk = sl - price

        tp1 = min(d1_mid, price - risk * 1.0)
        tp2 = min(d1_low, tp1, price - risk * 1.7)
        tp_large = min(d1_low - d1_range * 0.25, tp2, price - risk * 2.5)

        if not valid_rr(price, sl, tp1):
            return no_setup(price)

        return build_sell(price, sl, tp1, tp2, tp_large, "D1_ZONE_SELL", 90)

    # =========================
    # BREAKOUT BUY
    # D1 Breakout → Retest OR FVG → Entry
    # =========================
    if breakout_buy:
        retest = abs(price - d1_high) <= retest_buffer

        fvg_ok = False
        zone_low = d1_high

        if fvg and fvg[0] == "BUY":
            _, fvg_low, fvg_high = fvg
            fvg_buffer = price * 0.0008
            if (fvg_low - fvg_buffer) <= price <= (fvg_high + fvg_buffer):
                fvg_ok = True
                zone_low = fvg_low

        if not (retest or fvg_ok):
            return no_setup(price)

        sl_struct = recent_low(c1h, 1, 8)
        if sl_struct is None:
            return no_setup(price)

        sl = min(sl_struct, zone_low, d1_high)

        if sl >= price:
            return no_setup(price)

        risk = price - sl

        tp1 = max(price + risk * 1.0, d1_high + d1_range * 0.15)
        tp2 = max(price + risk * 1.7, d1_high + d1_range * 0.35)
        tp_large = max(price + risk * 2.5, d1_high + d1_range * 0.60)

        if not valid_rr(price, sl, tp1):
            return no_setup(price)

        return build_buy(price, sl, tp1, tp2, tp_large, "D1_BREAKOUT_BUY", 92)

    # =========================
    # BREAKOUT SELL
    # D1 Breakout → Retest OR FVG → Entry
    # =========================
    if breakout_sell:
        retest = abs(price - d1_low) <= retest_buffer

        fvg_ok = False
        zone_high = d1_low

        if fvg and fvg[0] == "SELL":
            _, fvg_low, fvg_high = fvg
            fvg_buffer = price * 0.0008
            if (fvg_low - fvg_buffer) <= price <= (fvg_high + fvg_buffer):
                fvg_ok = True
                zone_high = fvg_high

        if not (retest or fvg_ok):
            return no_setup(price)

        sl_struct = recent_high(c1h, 1, 8)
        if sl_struct is None:
            return no_setup(price)

        sl = max(sl_struct, zone_high, d1_low)

        if sl <= price:
            return no_setup(price)

        risk = sl - price

        tp1 = min(price - risk * 1.0, d1_low - d1_range * 0.15)
        tp2 = min(price - risk * 1.7, d1_low - d1_range * 0.35)
        tp_large = min(price - risk * 2.5, d1_low - d1_range * 0.60)

        if not valid_rr(price, sl, tp1):
            return no_setup(price)

        return build_sell(price, sl, tp1, tp2, tp_large, "D1_BREAKOUT_SELL", 92)

    return no_setup(price)
