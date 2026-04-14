import requests


def format_price(p):
    if p is None:
        return "-"
    p = float(p)
    if abs(p) < 10:
        return f"{p:.5f}"
    if abs(p) < 1000:
        return f"{p:.2f}"
    return f"{p:,.2f}"


def get_crypto(symbol: str, interval: str, limit: int = 120):
    url = "https://api.binance.com/api/v3/klines"
    r = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10)
    r.raise_for_status()
    data = r.json()

    candles = []
    for c in data:
        candles.append({
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
        })
    return candles


def get_forex(symbol: str, interval: str, limit: int = 120):
    url = "https://api.twelvedata.com/time_series"
    r = requests.get(
        url,
        params={
            "symbol": symbol,
            "interval": interval,
            "outputsize": limit,
            "apikey": "8f8f55c79aa54b789bd3177ce55e224e",
            "format": "JSON",
        },
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()

    values = data.get("values", [])
    if not values:
        raise ValueError(f"No data for {symbol} {interval}: {data}")

    candles = []
    for c in reversed(values):
        candles.append({
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
        })
    return candles


def get_multi_timeframe_analysis(market: str, symbol: str):
    if market == "crypto":
        return {
            "m5": get_crypto(symbol, "5m"),
            "m15": get_crypto(symbol, "15m"),
            "m30": get_crypto(symbol, "30m"),
            "h1": get_crypto(symbol, "1h"),
            "d1": get_crypto(symbol, "1d"),
        }

    return {
        "m5": get_forex(symbol, "5min"),
        "m15": get_forex(symbol, "15min"),
        "m30": get_forex(symbol, "30min"),
        "h1": get_forex(symbol, "1h"),
        "d1": get_forex(symbol, "1day"),
    }


def get_bias(h1, d1):
    if len(h1) < 10 or len(d1) < 10:
        return "NEUTRAL"

    h1_up = h1[-1]["close"] > h1[-10]["close"]
    d1_up = d1[-1]["close"] > d1[-10]["close"]

    h1_down = h1[-1]["close"] < h1[-10]["close"]
    d1_down = d1[-1]["close"] < d1[-10]["close"]

    if h1_up and d1_up:
        return "BULLISH"
    if h1_down and d1_down:
        return "BEARISH"
    return "NEUTRAL"


def bullish_pattern(candles):
    if len(candles) < 2:
        return False

    prev = candles[-2]
    last = candles[-1]

    body = abs(last["close"] - last["open"])
    total = max(last["high"] - last["low"], 1e-9)

    strong_close = last["close"] > last["open"]
    close_near_high = (last["high"] - last["close"]) <= total * 0.20
    strong_body = body >= total * 0.50
    reclaim_prev = last["close"] > prev["high"] or last["close"] > prev["close"]

    return strong_close and close_near_high and strong_body and reclaim_prev


def bearish_pattern(candles):
    if len(candles) < 2:
        return False

    prev = candles[-2]
    last = candles[-1]

    body = abs(last["close"] - last["open"])
    total = max(last["high"] - last["low"], 1e-9)

    strong_close = last["close"] < last["open"]
    close_near_low = (last["close"] - last["low"]) <= total * 0.20
    strong_body = body >= total * 0.50
    break_prev = last["close"] < prev["low"] or last["close"] < prev["close"]

    return strong_close and close_near_low and strong_body and break_prev


def detect_fvg(candles):
    if len(candles) < 3:
        return None
    c1 = candles[-3]
    c3 = candles[-1]

    if c3["low"] > c1["high"]:
        return "BUY"
    if c3["high"] < c1["low"]:
        return "SELL"
    return None


def detect_sweep(candles):
    if len(candles) < 2:
        return None
    prev = candles[-2]
    last = candles[-1]

    if last["low"] < prev["low"] and last["close"] > prev["low"]:
        return "BUY"
    if last["high"] > prev["high"] and last["close"] < prev["high"]:
        return "SELL"
    return None


def detect_ob(candles):
    if len(candles) < 2:
        return None
    prev = candles[-2]
    last = candles[-1]

    if prev["close"] < prev["open"] and last["close"] > prev["high"]:
        return "BUY"
    if prev["close"] > prev["open"] and last["close"] < prev["low"]:
        return "SELL"
    return None


def detect_bos_choch(candles):
    if len(candles) < 6:
        return None

    highs = [c["high"] for c in candles[-6:]]
    lows = [c["low"] for c in candles[-6:]]
    last = candles[-1]["close"]

    if last > max(highs[:-1]):
        return "BUY"
    if last < min(lows[:-1]):
        return "SELL"
    return None


def detect_magnet(m15):
    highs = [c["high"] for c in m15[-20:]]
    lows = [c["low"] for c in m15[-20:]]
    if not highs or not lows:
        return "NEUTRAL", None, None
    return "RANGE", max(highs), min(lows)


def fib_618_value(h1):
    highs = [c["high"] for c in h1[-20:]]
    lows = [c["low"] for c in h1[-20:]]
    high = max(highs)
    low = min(lows)
    return high - (high - low) * 0.618


def local_buy_sl(m15, m30, entry):
    lows = [
        min(c["low"] for c in m15[-5:]),
        min(c["low"] for c in m30[-5:]),
    ]
    below = [x for x in lows if x < entry]
    return max(below) if below else min(lows)


def local_sell_sl(m15, m30, entry):
    highs = [
        max(c["high"] for c in m15[-5:]),
        max(c["high"] for c in m30[-5:]),
    ]
    above = [x for x in highs if x > entry]
    return min(above) if above else max(highs)


def evaluate_signal_engine(mtf):
    m5 = mtf["m5"]
    m15 = mtf["m15"]
    m30 = mtf["m30"]
    h1 = mtf["h1"]
    d1 = mtf["d1"]

    bias = get_bias(h1, d1)
    last5 = m5[-1]
    price = last5["close"]

    fvg = detect_fvg(m5)
    sweep = detect_sweep(m5)
    ob = detect_ob(m5)
    bos = detect_bos_choch(m5)

    magnet_mode, magnet_up, magnet_down = detect_magnet(m15)
    fib_618 = fib_618_value(h1)

    buy_pattern = bullish_pattern(m5)
    sell_pattern = bearish_pattern(m5)

    buy_triggers = 0
    sell_triggers = 0

    if fvg == "BUY":
        buy_triggers += 1
    if fvg == "SELL":
        sell_triggers += 1

    if sweep == "BUY":
        buy_triggers += 1
    if sweep == "SELL":
        sell_triggers += 1

    if ob == "BUY":
        buy_triggers += 1
    if ob == "SELL":
        sell_triggers += 1

    if bos == "BUY":
        buy_triggers += 1
    if bos == "SELL":
        sell_triggers += 1

    if magnet_up and price < magnet_up:
        buy_triggers += 1
    if magnet_down and price > magnet_down:
        sell_triggers += 1

    if fib_618 is not None:
        if price <= fib_618:
            buy_triggers += 1
        else:
            sell_triggers += 1

    signal_type = "NO CLEAR SETUP"
    signal_status = "WAIT"
    preferred_side = "WAIT"
    signal_score = 0

    entry_price = None
    sl_price = None
    tp1 = None
    tp2 = None
    tp_large = None

    buy_fvg = "YES" if fvg == "BUY" else "NO"
    sell_fvg = "YES" if fvg == "SELL" else "NO"
    buy_ob = "YES" if ob == "BUY" else "NO"
    sell_ob = "YES" if ob == "SELL" else "NO"
    buy_sweep = "YES" if sweep == "BUY" else "NO"
    sell_sweep = "YES" if sweep == "SELL" else "NO"

    stronger_magnet = "UP" if buy_triggers > sell_triggers else "DOWN"

    if bias == "BULLISH" and buy_triggers >= 1:
        preferred_side = "BUY"
        signal_type = "BUY ENTRY READY"
        signal_status = "CONFIRMED BUY"
        entry_price = price
        sl_price = local_buy_sl(m15, m30, entry_price)
        risk = max(entry_price - sl_price, 1e-9)
        tp1 = entry_price + risk * 1.2
        tp2 = entry_price + risk * 1.8
        tp_large = max(c["high"] for c in h1[-10:])
        signal_score = 80 + min(buy_triggers * 3, 15)

    elif bias == "BEARISH" and sell_triggers >= 1:
        preferred_side = "SELL"
        signal_type = "SELL ENTRY READY"
        signal_status = "CONFIRMED SELL"
        entry_price = price
        sl_price = local_sell_sl(m15, m30, entry_price)
        risk = max(sl_price - entry_price, 1e-9)
        tp1 = entry_price - risk * 1.2
        tp2 = entry_price - risk * 1.8
        tp_large = min(c["low"] for c in h1[-10:])
        signal_score = 80 + min(sell_triggers * 3, 15)

    return {
        "signal_type": signal_type,
        "signal_status": signal_status,
        "preferred_side": preferred_side,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp1": tp1,
        "tp2": tp2,
        "tp_large": tp_large,
        "buy_fvg": buy_fvg,
        "sell_fvg": sell_fvg,
        "buy_ob": buy_ob,
        "sell_ob": sell_ob,
        "buy_sweep": buy_sweep,
        "sell_sweep": sell_sweep,
        "stronger_magnet": stronger_magnet,
        "fib_618": fib_618,
        "trigger_price": price,
        "signal_score": signal_score,
    }
