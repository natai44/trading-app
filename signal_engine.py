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


def candle_body(c):
    return abs(c["close"] - c["open"])


def upper_wick(c):
    return c["high"] - max(c["open"], c["close"])


def lower_wick(c):
    return min(c["open"], c["close"]) - c["low"]


def bullish(c):
    return c["close"] > c["open"]


def bearish(c):
    return c["close"] < c["open"]


def build_buy(price, sl, tp1, tp2, tp_large, mode, score):
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


def valid_rr(entry, sl, tp1):
    risk = abs(entry - sl)
    reward = abs(tp1 - entry)
    return risk > 0 and reward >= risk * 0.70


# ---------------- LIQUIDITY ----------------

def get_liquidity_high(c1h):
    # liquidity above = recent 1H swing/equal highs before sweep candle
    return recent_high(c1h, 2, 18)


def get_liquidity_low(c1h):
    # liquidity below = recent 1H swing/equal lows before sweep candle
    return recent_low(c1h, 2, 18)


def detect_1h_sweep(c1h):
    """
    Uses last CLOSED 1H candle = c1h[1]
    BUY sweep: takes liquidity low and closes back above
    SELL sweep: takes liquidity high and closes back below
    """
    if len(c1h) < 20:
        return None

    sweep_candle = c1h[1]
    liq_high = get_liquidity_high(c1h)
    liq_low = get_liquidity_low(c1h)

    if liq_high is None or liq_low is None:
        return None

    body = candle_body(sweep_candle)
    if body <= 0:
        body = 0.01

    # SELL sweep/rejection
    sell_sweep = (
        sweep_candle["high"] > liq_high
        and sweep_candle["close"] < liq_high
        and upper_wick(sweep_candle) > body * 1.2
    )

    # BUY sweep/rejection
    buy_sweep = (
        sweep_candle["low"] < liq_low
        and sweep_candle["close"] > liq_low
        and lower_wick(sweep_candle) > body * 1.2
    )

    if sell_sweep and not buy_sweep:
        return {
            "side": "SELL",
            "liquidity": liq_high,
            "sweep_extreme": sweep_candle["high"],
            "sweep_candle": sweep_candle,
        }

    if buy_sweep and not sell_sweep:
        return {
            "side": "BUY",
            "liquidity": liq_low,
            "sweep_extreme": sweep_candle["low"],
            "sweep_candle": sweep_candle,
        }

    return None


# ---------------- 15M RETEST ----------------

def retest_confirmed(c15, sweep):
    """
    Uses last CLOSED 15m candle = c15[1]
    Retest must return into sweep-zone and close direction.
    """
    if len(c15) < 20 or not sweep:
        return False

    c = c15[1]
    side = sweep["side"]
    liq = sweep["liquidity"]
    extreme = sweep["sweep_extreme"]

    if side == "BUY":
        zone_low = extreme
        zone_high = liq

        touched_zone = c["low"] <= zone_high and c["high"] >= zone_low
        confirmed = bullish(c) and c["close"] > liq

        return touched_zone and confirmed

    if side == "SELL":
        zone_low = liq
        zone_high = extreme

        touched_zone = c["high"] >= zone_low and c["low"] <= zone_high
        confirmed = bearish(c) and c["close"] < liq

        return touched_zone and confirmed

    return False


# ---------------- TP TARGETS ----------------

def get_buy_targets(entry, sl, c1h, c15):
    highs = []

    for c in c15[2:50]:
        if c["high"] > entry:
            highs.append(c["high"])

    for c in c1h[2:40]:
        if c["high"] > entry:
            highs.append(c["high"])

    highs = sorted(set(highs))

    risk = entry - sl

    tp1 = highs[0] if len(highs) >= 1 else entry + risk * 1.0
    tp2 = highs[1] if len(highs) >= 2 else max(tp1, entry + risk * 1.7)
    tp_large = highs[2] if len(highs) >= 3 else max(tp2, entry + risk * 2.5)

    tp1 = max(tp1, entry + risk * 0.8)
    tp2 = max(tp2, tp1)
    tp_large = max(tp_large, tp2)

    return tp1, tp2, tp_large


def get_sell_targets(entry, sl, c1h, c15):
    lows = []

    for c in c15[2:50]:
        if c["low"] < entry:
            lows.append(c["low"])

    for c in c1h[2:40]:
        if c["low"] < entry:
            lows.append(c["low"])

    lows = sorted(set(lows), reverse=True)

    risk = sl - entry

    tp1 = lows[0] if len(lows) >= 1 else entry - risk * 1.0
    tp2 = lows[1] if len(lows) >= 2 else min(tp1, entry - risk * 1.7)
    tp_large = lows[2] if len(lows) >= 3 else min(tp2, entry - risk * 2.5)

    tp1 = min(tp1, entry - risk * 0.8)
    tp2 = min(tp2, tp1)
    tp_large = min(tp_large, tp2)

    return tp1, tp2, tp_large


# ---------------- MAIN DATA ----------------

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
        return no_setup(None)

    c15 = data.get("c15", [])
    c1h = data.get("c1h", [])

    if len(c15) < 50 or len(c1h) < 40:
        return no_setup(None)

    # Entry price = last closed 15m close
    price = c15[1]["close"]

    sweep = detect_1h_sweep(c1h)
    if not sweep:
        return no_setup(price)

    if not retest_confirmed(c15, sweep):
        return no_setup(price)

    side = sweep["side"]
    buffer = max(price * 0.0005, 2.0)

    if side == "BUY":
        sl = sweep["sweep_extreme"] - buffer

        if sl >= price:
            return no_setup(price)

        tp1, tp2, tp_large = get_buy_targets(price, sl, c1h, c15)

        if not valid_rr(price, sl, tp1):
            return no_setup(price)

        return build_buy(
            price=price,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            tp_large=tp_large,
            mode="LIQ_SWEEP_RETEST_BUY",
            score=92,
        )

    if side == "SELL":
        sl = sweep["sweep_extreme"] + buffer

        if sl <= price:
            return no_setup(price)

        tp1, tp2, tp_large = get_sell_targets(price, sl, c1h, c15)

        if not valid_rr(price, sl, tp1):
            return no_setup(price)

        return build_sell(
            price=price,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            tp_large=tp_large,
            mode="LIQ_SWEEP_RETEST_SELL",
            score=92,
        )

    return no_setup(price)
