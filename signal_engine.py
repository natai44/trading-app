import requests

def format_price(p):
    if p is None:
        return "-"
    p = float(p)
    return f"{p:.2f}"

def get_forex(symbol, interval):
    url = "https://api.twelvedata.com/time_series"
    r = requests.get(url, params={
        "symbol": symbol,
        "interval": interval,
        "outputsize": 120,
        "apikey": "8f8f55c79aa54b789bd3177ce55e224e"
    }).json()

    candles = []
    for c in reversed(r["values"]):
        candles.append({
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
        })
    return candles


def get_multi_timeframe_analysis(market, symbol):
    return {
        "m5": get_forex(symbol, "5min"),
        "m15": get_forex(symbol, "15min"),
        "m30": get_forex(symbol, "30min"),
        "h1": get_forex(symbol, "1h"),
        "d1": get_forex(symbol, "1day"),
    }


# ===== LOGIC =====

def get_bias(h1, d1):
    if h1[-1]["close"] > h1[-10]["close"] and d1[-1]["close"] > d1[-10]["close"]:
        return "BULLISH"
    if h1[-1]["close"] < h1[-10]["close"] and d1[-1]["close"] < d1[-10]["close"]:
        return "BEARISH"
    return "NEUTRAL"


def bullish_candle(c):
    body = abs(c["close"] - c["open"])
    total = c["high"] - c["low"]
    return c["close"] > c["open"] and body > total * 0.5


def bearish_candle(c):
    body = abs(c["close"] - c["open"])
    total = c["high"] - c["low"]
    return c["close"] < c["open"] and body > total * 0.5


def detect_fvg(c):
    if len(c) < 3:
        return None
    if c[-1]["low"] > c[-3]["high"]:
        return "BUY"
    if c[-1]["high"] < c[-3]["low"]:
        return "SELL"
    return None


def detect_sweep(c):
    if c[-1]["low"] < c[-2]["low"]:
        return "BUY"
    if c[-1]["high"] > c[-2]["high"]:
        return "SELL"
    return None


def detect_ob(c):
    if c[-2]["close"] < c[-2]["open"] and c[-1]["close"] > c[-2]["high"]:
        return "BUY"
    if c[-2]["close"] > c[-2]["open"] and c[-1]["close"] < c[-2]["low"]:
        return "SELL"
    return None


def evaluate_signal_engine(mtf):

    m5 = mtf["m5"]
    m15 = mtf["m15"]
    m30 = mtf["m30"]
    h1 = mtf["h1"]
    d1 = mtf["d1"]

    bias = get_bias(h1, d1)
    price = m5[-1]["close"]

    fvg = detect_fvg(m5)
    sweep = detect_sweep(m5)
    ob = detect_ob(m5)

    buy_triggers = sum([fvg=="BUY", sweep=="BUY", ob=="BUY"])
    sell_triggers = sum([fvg=="SELL", sweep=="SELL", ob=="SELL"])

    buy_confirm = bullish_candle(m5[-1])
    sell_confirm = bearish_candle(m5[-1])

    signal_type = "NO CLEAR SETUP"
    preferred = "WAIT"

    if bias=="BULLISH" and buy_triggers>=3 and fvg=="BUY" and buy_confirm:
        signal_type="BUY ENTRY READY"
        preferred="BUY"

    if bias=="BEARISH" and sell_triggers>=3 and fvg=="SELL" and sell_confirm:
        signal_type="SELL ENTRY READY"
        preferred="SELL"

    entry = price

    if preferred=="BUY":
        sl = min(c["low"] for c in m15[-5:])
        risk = entry - sl
        tp1 = entry + risk*1.2
        tp2 = entry + risk*1.8

        h1_high = max(c["high"] for c in h1[-20:])
        tp_large = h1_high if (h1_high-entry)>risk*2 else entry+risk*2.2

    elif preferred=="SELL":
        sl = max(c["high"] for c in m15[-5:])
        risk = sl - entry
        tp1 = entry - risk*1.2
        tp2 = entry - risk*1.8

        h1_low = min(c["low"] for c in h1[-20:])
        tp_large = h1_low if (entry-h1_low)>risk*2 else entry-risk*2.2

    else:
        sl=tp1=tp2=tp_large=None

    return {
        "signal_type": signal_type,
        "preferred_side": preferred,
        "entry_price": entry,
        "sl_price": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp_large": tp_large,
        "buy_fvg": "YES" if fvg=="BUY" else "NO",
        "sell_fvg": "YES" if fvg=="SELL" else "NO",
        "buy_ob": "YES" if ob=="BUY" else "NO",
        "sell_ob": "YES" if ob=="SELL" else "NO",
        "buy_sweep": "YES" if sweep=="BUY" else "NO",
        "sell_sweep": "YES" if sweep=="SELL" else "NO",
        "stronger_magnet": "UP" if preferred=="BUY" else "DOWN",
        "fib_618": "-",
        "trigger_price": price,
        "signal_score": 90
    }
