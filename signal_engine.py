import requests


TWELVE_DATA_API_KEY = "8f8f55c79aa54b789bd3177ce55e224e"


def format_price(value):
    if value is None:
        return "-"
    value = float(value)
    if abs(value) < 10:
        return f"{value:.5f}"
    if abs(value) < 1000:
        return f"{value:.2f}"
    return f"{value:,.2f}"


def get_crypto_candles(symbol: str, interval: str, limit: int = 150):
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol.upper().strip(),
        "interval": interval,
        "limit": limit,
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    candles = []
    for row in data:
        candles.append({
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
        })
    return candles


def get_forex_candles(symbol: str, interval: str, outputsize: int = 150):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol.upper().strip(),
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_API_KEY,
        "format": "JSON",
    }
    r = requests.get(url, params=params, timeout=12)
    r.raise_for_status()
    data = r.json()

    values = data.get("values", [])
    if not values:
        raise ValueError(f"No data returned for {symbol} {interval}: {data}")

    candles = []
    for row in reversed(values):
        candles.append({
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })
    return candles


def get_multi_timeframe_analysis(market: str, symbol: str):
    market = market.strip().lower()

    if market == "crypto":
        return {
            "m5": get_crypto_candles(symbol, "5m"),
            "m15": get_crypto_candles(symbol, "15m"),
            "h1": get_crypto_candles(symbol, "1h"),
        }

    if market == "forex":
        return {
            "m5": get_forex_candles(symbol, "5min"),
            "m15": get_forex_candles(symbol, "15min"),
            "h1": get_forex_candles(symbol, "1h"),
        }

    raise ValueError(f"Unsupported market: {market}")


def sma(values, period: int):
    if len(values) < period:
        return sum(values) / max(len(values), 1)
    return sum(values[-period:]) / period


def recent_high(candles, count: int):
    return max(c["high"] for c in candles[-count:])


def recent_low(candles, count: int):
    return min(c["low"] for c in candles[-count:])


def get_bias(h1, m15):
    h1_closes = [c["close"] for c in h1]
    m15_closes = [c["close"] for c in m15]

    h1_fast = sma(h1_closes, 5)
    h1_slow = sma(h1_closes, 20)
    m15_fast = sma(m15_closes, 5)
    m15_slow = sma(m15_closes, 20)

    if h1_fast > h1_slow and m15_fast > m15_slow:
        return "BULLISH"
    if h1_fast < h1_slow and m15_fast < m15_slow:
        return "BEARISH"
    return "NEUTRAL"


def strong_bullish_candle(candle):
    total = max(candle["high"] - candle["low"], 1e-9)
    body = abs(candle["close"] - candle["open"])
    close_near_high = (candle["high"] - candle["close"]) <= total * 0.15
    no_big_upper_wick = (candle["high"] - candle["close"]) <= body * 0.35
    return candle["close"] > candle["open"] and body >= total * 0.60 and close_near_high and no_big_upper_wick


def strong_bearish_candle(candle):
    total = max(candle["high"] - candle["low"], 1e-9)
    body = abs(candle["close"] - candle["open"])
    close_near_low = (candle["close"] - candle["low"]) <= total * 0.15
    no_big_lower_wick = (candle["close"] - candle["low"]) <= body * 0.35
    return candle["close"] < candle["open"] and body >= total * 0.60 and close_near_low and no_big_lower_wick


def bullish_candle_pattern(candles):
    if len(candles) < 2:
        return False

    prev = candles[-2]
    last = candles[-1]

    return strong_bullish_candle(last) and last["close"] > prev["high"]


def bearish_candle_pattern(candles):
    if len(candles) < 2:
        return False

    prev = candles[-2]
    last = candles[-1]

    return strong_bearish_candle(last) and last["close"] < prev["low"]


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


def detect_order_block(candles):
    if len(candles) < 2:
        return None

    prev = candles[-2]
    last = candles[-1]

    if prev["close"] < prev["open"] and last["close"] > prev["high"]:
        return "BUY"
    if prev["close"] > prev["open"] and last["close"] < prev["low"]:
        return "SELL"
    return None


def detect_bos(candles):
    if len(candles) < 6:
        return None

    last_close = candles[-1]["close"]
    highs = [c["high"] for c in candles[-6:-1]]
    lows = [c["low"] for c in candles[-6:-1]]

    if last_close > max(highs):
        return "BUY"
    if last_close < min(lows):
        return "SELL"
    return None


def calculate_fib_618(h1):
    hi = recent_high(h1, min(20, len(h1)))
    lo = recent_low(h1, min(20, len(h1)))
    return hi - (hi - lo) * 0.618


def detect_magnet(m15):
    hi = recent_high(m15, min(20, len(m15)))
    lo = recent_low(m15, min(20, len(m15)))
    return hi, lo


def local_buy_sl(m15, entry):
    candidates = [
        recent_low(m15, min(5, len(m15))),
        recent_low(m15, min(8, len(m15))),
    ]
    below = [x for x in candidates if x < entry]
    return max(below) if below else min(candidates)


def local_sell_sl(m15, entry):
    candidates = [
        recent_high(m15, min(5, len(m15))),
        recent_high(m15, min(8, len(m15))),
    ]
    above = [x for x in candidates if x > entry]
    return min(above) if above else max(candidates)


def evaluate_signal_engine(mtf):
    m5 = mtf["m5"]
    m15 = mtf["m15"]
    h1 = mtf["h1"]

    bias = get_bias(h1, m15)
    price = m5[-1]["close"]

    fvg = detect_fvg(m5)
    sweep = detect_sweep(m5)
    ob = detect_order_block(m5)
    bos = detect_bos(m5)

    fib_618 = calculate_fib_618(h1)
    magnet_up, magnet_down = detect_magnet(m15)

    buy_pattern = bullish_candle_pattern(m5)
    sell_pattern = bearish_candle_pattern(m5)

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

    if price < magnet_up:
        buy_triggers += 1
    if price > magnet_down:
        sell_triggers += 1

    if price <= fib_618:
        buy_triggers += 1
    else:
        sell_triggers += 1

    signal_type = "NO CLEAR SETUP"
    signal_status = "WAIT"
    preferred_side = "WAIT"
    entry_price = None
    sl_price = None
    tp1 = None
    tp2 = None
    tp_large = None
    signal_score = 0

    buy_fvg = "YES" if fvg == "BUY" else "NO"
    sell_fvg = "YES" if fvg == "SELL" else "NO"
    buy_ob = "YES" if ob == "BUY" else "NO"
    sell_ob = "YES" if ob == "SELL" else "NO"
    buy_sweep = "YES" if sweep == "BUY" else "NO"
    sell_sweep = "YES" if sweep == "SELL" else "NO"

    if bias == "BULLISH" and buy_triggers >= 3 and fvg == "BUY" and buy_pattern:
        preferred_side = "BUY"
        signal_type = "BUY ENTRY READY"
        signal_status = "CONFIRMED BUY"
        entry_price = price
        sl_price = local_buy_sl(m15, entry_price)
        risk = max(entry_price - sl_price, 1e-9)

        tp1 = entry_price + risk * 1.2
        tp2 = entry_price + risk * 1.8

        h1_high = recent_high(h1, min(20, len(h1)))
        if h1_high - entry_price > risk * 2:
            tp_large = h1_high
        else:
            tp_large = entry_price + risk * 2.2

        signal_score = 80 + min(buy_triggers * 3, 15)

    elif bias == "BEARISH" and sell_triggers >= 3 and fvg == "SELL" and sell_pattern:
        preferred_side = "SELL"
        signal_type = "SELL ENTRY READY"
        signal_status = "CONFIRMED SELL"
        entry_price = price
        sl_price = local_sell_sl(m15, entry_price)
        risk = max(sl_price - entry_price, 1e-9)

        tp1 = entry_price - risk * 1.2
        tp2 = entry_price - risk * 1.8

        h1_low = recent_low(h1, min(20, len(h1)))
        if entry_price - h1_low > risk * 2:
            tp_large = h1_low
        else:
            tp_large = entry_price - risk * 2.2

        signal_score = 80 + min(sell_triggers * 3, 15)

    stronger_magnet = "UP" if preferred_side == "BUY" else "DOWN"

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
