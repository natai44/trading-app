import os
import requests

BASE_URL = "https://api.twelvedata.com"
API_KEY = os.getenv("8f8f55c79aa54b789bd3177ce55e224e")


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


def bullish(c):
    return c["close"] > c["open"]


def bearish(c):
    return c["close"] < c["open"]


def get_d1_zone(c1d):
    if len(c1d) < 2:
        return None

    prev = c1d[1]
    high = prev["high"]
    low = prev["low"]
    rng = max(high - low, 1e-9)

    return {
        "high": high,
        "low": low,
        "range": rng,
        "buy_zone_high": low + rng * 0.18,
        "sell_zone_low": high - rng * 0.18,
    }


def in_d1_buy_zone(price, d1):
    return price <= d1["buy_zone_high"]


def in_d1_sell_zone(price, d1):
    return price >= d1["sell_zone_low"]


# ---------------- 1H CONTEXT ----------------

def wick_rejection_buy(c):
    body = abs(c["close"] - c["open"])
    lower = min(c["open"], c["close"]) - c["low"]
    upper = c["high"] - max(c["open"], c["close"])
    return bullish(c) and lower > body * 1.2 and lower > upper


def wick_rejection_sell(c):
    body = abs(c["close"] - c["open"])
    upper = c["high"] - max(c["open"], c["close"])
    lower = min(c["open"], c["close"]) - c["low"]
    return bearish(c) and upper > body * 1.2 and upper > lower


def sweep_1h_buy(c1h):
    last = c1h[1]
    prev_low = recent_low(c1h, 2, 10)
    if prev_low is None:
        return False
    return last["low"] < prev_low and last["close"] > prev_low


def sweep_1h_sell(c1h):
    last = c1h[1]
    prev_high = recent_high(c1h, 2, 10)
    if prev_high is None:
        return False
    return last["high"] > prev_high and last["close"] < prev_high


def choch_1h_buy(c1h):
    last = c1h[1]
    prev_high = recent_high(c1h, 2, 10)
    if prev_high is None:
        return False
    return last["close"] > prev_high


def choch_1h_sell(c1h):
    last = c1h[1]
    prev_low = recent_low(c1h, 2, 10)
    if prev_low is None:
        return False
    return last["close"] < prev_low


def context_1h(c1h, side):
    last = c1h[1]

    if side == "BUY":
        sweep = sweep_1h_buy(c1h)
        rejection = wick_rejection_buy(last)
        choch = choch_1h_buy(c1h)
        return sweep or rejection or choch, sweep, rejection, choch

    if side == "SELL":
        sweep = sweep_1h_sell(c1h)
        rejection = wick_rejection_sell(last)
        choch = choch_1h_sell(c1h)
        return sweep or rejection or choch, sweep, rejection, choch

    return False, False, False, False


# ---------------- 5M ENTRY ----------------

def bos_5m_buy(c5):
    last = c5[0]
    prev_high = recent_high(c5, 1, 12)
    if prev_high is None:
        return False
    return last["close"] > prev_high


def bos_5m_sell(c5):
    last = c5[0]
    prev_low = recent_low(c5, 1, 12)
    if prev_low is None:
        return False
    return last["close"] < prev_low


def fvg_5m(c5):
    if len(c5) < 5:
        return None

    c1 = c5[2]
    c2 = c5[1]
    c3 = c5[0]

    total = c2["high"] - c2["low"]
    impulse = abs(c2["close"] - c2["open"])

    if total <= 0:
        return None

    if impulse / total < 0.25:
        return None

    if c1["high"] < c3["low"]:
        return ("BUY", c1["high"], c3["low"])

    if c1["low"] > c3["high"]:
        return ("SELL", c3["high"], c1["low"])

    return None


def sweep_5m_buy(c5):
    last = c5[0]
    prev_low = recent_low(c5, 1, 10)
    if prev_low is None:
        return None
    if last["low"] < prev_low and last["close"] > prev_low:
        return last["low"]
    return None


def sweep_5m_sell(c5):
    last = c5[0]
    prev_high = recent_high(c5, 1, 10)
    if prev_high is None:
        return None
    if last["high"] > prev_high and last["close"] < prev_high:
        return last["high"]
    return None


def retest_5m_buy(c5):
    last = c5[0]
    prev_low = recent_low(c5, 1, 8)
    if prev_low is None:
        return False
    return last["low"] <= prev_low * 1.001 and bullish(last)


def retest_5m_sell(c5):
    last = c5[0]
    prev_high = recent_high(c5, 1, 8)
    if prev_high is None:
        return False
    return last["high"] >= prev_high * 0.999 and bearish(last)


def entry_5m(c5, side):
    fvg = fvg_5m(c5)

    if side == "BUY":
        bos = bos_5m_buy(c5)
        retest = retest_5m_buy(c5)
        fvg_ok = fvg and fvg[0] == "BUY"
        sweep_low = sweep_5m_buy(c5)
        return bos and (fvg_ok or retest), bos, fvg_ok, retest, sweep_low

    if side == "SELL":
        bos = bos_5m_sell(c5)
        retest = retest_5m_sell(c5)
        fvg_ok = fvg and fvg[0] == "SELL"
        sweep_high = sweep_5m_sell(c5)
        return bos and (fvg_ok or retest), bos, fvg_ok, retest, sweep_high

    return False, False, False, False, None


# ---------------- SL / TP ----------------

def get_targets_buy(entry, sl, c5, c1h, d1):
    risk = entry - sl

    highs_5m = sorted({c["high"] for c in c5[1:60] if c["high"] > entry})
    highs_1h = sorted({c["high"] for c in c1h[1:40] if c["high"] > entry})

    tp1 = highs_5m[0] if highs_5m else entry + risk * 1.0
    tp2 = highs_1h[0] if highs_1h else entry + risk * 1.7
    tp_large = d1["high"]

    tp1 = max(tp1, entry + risk * 0.8)
    tp2 = max(tp2, tp1, entry + risk * 1.3)
    tp_large = max(tp_large, tp2, entry + risk * 2.0)

    return tp1, tp2, tp_large


def get_targets_sell(entry, sl, c5, c1h, d1):
    risk = sl - entry

    lows_5m = sorted({c["low"] for c in c5[1:60] if c["low"] < entry}, reverse=True)
    lows_1h = sorted({c["low"] for c in c1h[1:40] if c["low"] < entry}, reverse=True)

    tp1 = lows_5m[0] if lows_5m else entry - risk * 1.0
    tp2 = lows_1h[0] if lows_1h else entry - risk * 1.7
    tp_large = d1["low"]

    tp1 = min(tp1, entry - risk * 0.8)
    tp2 = min(tp2, tp1, entry - risk * 1.3)
    tp_large = min(tp_large, tp2, entry - risk * 2.0)

    return tp1, tp2, tp_large


def valid_risk(entry, sl):
    risk = abs(entry - sl)

    if risk < 8:
        return False
    if risk > 55:
        return False

    return True


def valid_rr(entry, sl, tp1):
    risk = abs(entry - sl)
    reward = abs(tp1 - entry)
    return risk > 0 and reward >= risk * 0.75


def build_signal(side, entry, sl, tp1, tp2, tp_large, mode, score, info):
    return {
        "signal_type": f"{side} ENTRY READY",
        "preferred_side": side,
        "entry_price": entry,
        "sl_price": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp_large": tp_large,
        "trigger_price": entry,
        "setup_mode": mode,
        "signal_score": score,
        "trigger_count": info["triggers"],
        "fvg": info["fvg"],
        "ob": False,
        "sweep": info["sweep"],
        "bos": info["bos"],
        "choch": info["choch"],
        "magnet": side,
    }


def get_multi_timeframe_analysis(market, symbol):
    c5 = get_candles(symbol, "5min")
    c1h = get_candles(symbol, "1h")
    c1d = get_candles(symbol, "1day", outputsize=10)

    if not c5 or not c1h or not c1d:
        return {}

    return {
        "c5": [to_float(c) for c in c5],
        "c1h": [to_float(c) for c in c1h],
        "c1d": [to_float(c) for c in c1d],
    }


def evaluate_signal_engine(data):
    if not data:
        return no_setup(None)

    c5 = data.get("c5", [])
    c1h = data.get("c1h", [])
    c1d = data.get("c1d", [])

    if len(c5) < 60 or len(c1h) < 40 or len(c1d) < 2:
        return no_setup(None)

    entry = c5[0]["close"]
    d1 = get_d1_zone(c1d)

    if not d1:
        return no_setup(entry)

    side = None

    if in_d1_buy_zone(entry, d1):
        side = "BUY"

    if in_d1_sell_zone(entry, d1):
        side = "SELL"

    if not side:
        return no_setup(entry)

    ctx_ok, sweep_1h, rejection_1h, choch_1h = context_1h(c1h, side)

    if not ctx_ok:
        return no_setup(entry)

    ent_ok, bos, fvg_ok, retest, sweep_5m_extreme = entry_5m(c5, side)

    if not ent_ok:
        return no_setup(entry)

    buffer = max(entry * 0.0005, 2.0)

    if side == "BUY":
        if sweep_5m_extreme is None:
            return no_setup(entry)

        sl = sweep_5m_extreme - buffer

        if sl >= entry or not valid_risk(entry, sl):
            return no_setup(entry)

        tp1, tp2, tp_large = get_targets_buy(entry, sl, c5, c1h, d1)

        if not valid_rr(entry, sl, tp1):
            return no_setup(entry)

    else:
        if sweep_5m_extreme is None:
            return no_setup(entry)

        sl = sweep_5m_extreme + buffer

        if sl <= entry or not valid_risk(entry, sl):
            return no_setup(entry)

        tp1, tp2, tp_large = get_targets_sell(entry, sl, c5, c1h, d1)

        if not valid_rr(entry, sl, tp1):
            return no_setup(entry)

    triggers = 0
    if ctx_ok:
        triggers += 1
    if sweep_1h:
        triggers += 1
    if rejection_1h:
        triggers += 1
    if choch_1h:
        triggers += 1
    if bos:
        triggers += 1
    if fvg_ok:
        triggers += 1
    if retest:
        triggers += 1

    score = min(82 + triggers * 3, 100)

    return build_signal(
        side,
        entry,
        sl,
        tp1,
        tp2,
        tp_large,
        "D1_1H_5M_ACTIVE",
        score,
        {
            "triggers": triggers,
            "fvg": fvg_ok,
            "sweep": sweep_1h,
            "bos": bos,
            "choch": choch_1h,
        },
    )
