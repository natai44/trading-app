import requests

# ===========================a==============
# PRICE DATA
# =========================================

def get_forex_or_gold_candles(symbol="XAU/USD", interval="5min"):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": 100,
        "apikey": "8f8f55c79aa54b789bd3177ce55e224e"
    }

    data = requests.get(url, params=params).json()

    candles = list(reversed(data["values"]))
    return [
        {
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"])
        }
        for c in candles
    ]


# =========================================
# HELPERS
# =========================================

def format_price(x):
    return f"{x:.2f}"


def get_bias(h1, d1):
    if h1[-1]["close"] > h1[-10]["close"] and d1[-1]["close"] > d1[-10]["close"]:
        return "BULLISH"
    if h1[-1]["close"] < h1[-10]["close"] and d1[-1]["close"] < d1[-10]["close"]:
        return "BEARISH"
    return "NEUTRAL"


# =========================================
# CANDLE PATTERN (WICHTIG)
# =========================================

def bullish_candle(c):
    return c["close"] > c["open"] and (c["close"] - c["low"]) > (c["high"] - c["close"])

def bearish_candle(c):
    return c["close"] < c["open"] and (c["high"] - c["close"]) > (c["close"] - c["low"])


# =========================================
# TRIGGERS (SIMPLIFIED SMART)
# =========================================

def detect_fvg(candles):
    c1 = candles[-3]
    c3 = candles[-1]

    if c3["low"] > c1["high"]:
        return "BUY"
    if c3["high"] < c1["low"]:
        return "SELL"
    return None


def detect_sweep(candles):
    last = candles[-1]
    prev = candles[-2]

    if last["low"] < prev["low"]:
        return "BUY"
    if last["high"] > prev["high"]:
        return "SELL"
    return None


def detect_ob(candles):
    last = candles[-1]
    prev = candles[-2]

    if prev["close"] < prev["open"] and last["close"] > prev["high"]:
        return "BUY"
    if prev["close"] > prev["open"] and last["close"] < prev["low"]:
        return "SELL"
    return None


# =========================================
# MAIN ENGINE
# =========================================

def evaluate_signal_engine(mtf):

    m5 = mtf["Scalp"]["candles"]
    m15 = mtf["Intraday"]["candles"]
    h1 = mtf["H1"]["candles"]
    d1 = mtf["Daily"]["candles"]

    bias = get_bias(h1, d1)

    last5 = m5[-1]

    # === TRIGGERS ===
    fvg = detect_fvg(m5)
    sweep = detect_sweep(m5)
    ob = detect_ob(m5)

    buy_triggers = [fvg == "BUY", sweep == "BUY", ob == "BUY"]
    sell_triggers = [fvg == "SELL", sweep == "SELL", ob == "SELL"]

    buy_count = sum(buy_triggers)
    sell_count = sum(sell_triggers)

    # === CANDLE CONFIRMATION ===
    buy_confirm = bullish_candle(last5)
    sell_confirm = bearish_candle(last5)

    # === DECISION ===
    signal_type = "NO CLEAR SETUP"
    preferred_side = "WAIT"

    if bias == "BULLISH" and buy_count >= 2 and buy_confirm:
        signal_type = "BUY ENTRY READY"
        preferred_side = "BUY"

    elif bias == "BEARISH" and sell_count >= 2 and sell_confirm:
        signal_type = "SELL ENTRY READY"
        preferred_side = "SELL"

    # === ENTRY / SL / TP ===
    entry = last5["close"]

    sl = m15[-5]["low"] if preferred_side == "BUY" else m15[-5]["high"]
    tp = h1[-1]["high"] if preferred_side == "BUY" else h1[-1]["low"]

    return {
        "signal_type": signal_type,
        "signal_status": "CONFIRMED " + preferred_side if preferred_side != "WAIT" else "WAIT",
        "preferred_side": preferred_side,

        "entry_price": entry,
        "sl_price": sl,
        "tp1": tp,
        "tp2": tp * 1.01,
        "tp_large": tp * 1.02,

        "buy_fvg": "YES" if fvg == "BUY" else "NO",
        "sell_fvg": "YES" if fvg == "SELL" else "NO",
        "buy_ob": "YES" if ob == "BUY" else "NO",
        "sell_ob": "YES" if ob == "SELL" else "NO",
        "buy_sweep": "YES" if sweep == "BUY" else "NO",
        "sell_sweep": "YES" if sweep == "SELL" else "NO",

        "stronger_magnet": "UP" if preferred_side == "BUY" else "DOWN",
        "fib_618": "-",

        "trigger_price": entry,
        "signal_score": 80
    }


# =========================================
# MTF WRAPPER
# =========================================

def get_multi_timeframe_analysis(market, symbol):
    return {
        "Scalp": {"candles": get_forex_or_gold_candles(symbol, "5min")},
        "Intraday": {"candles": get_forex_or_gold_candles(symbol, "15min")},
        "H1": {"candles": get_forex_or_gold_candles(symbol, "1h")},
        "Daily": {"candles": get_forex_or_gold_candles(symbol, "1day")},
    }
