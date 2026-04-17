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


# =========================================================
# DATA
# =========================================================

def get_forex_candles(symbol, interval):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": 150,
        "apikey": TWELVE_DATA_API_KEY,
    }
    r = requests.get(url, params=params, timeout=12).json()

    values = r.get("values", [])
    if not values:
        raise ValueError(f"No data returned for {symbol} {interval}: {r}")

    candles = []
    for c in reversed(values):
        candles.append({
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
        })
    return candles


def get_multi_timeframe_analysis(market, symbol):
    return {
        "m5": get_forex_candles(symbol, "5min"),
        "m15": get_forex_candles(symbol, "15min"),
        "h1": get_forex_candles(symbol, "1h"),
    }


# =========================================================
# HELPERS
# =========================================================

def sma(values, n):
    if len(values) < n:
        return sum(values) / max(len(values), 1)
    return sum(values[-n:]) / n


def recent_high(candles, count):
    return max(c["high"] for c in candles[-count:])


def recent_low(candles, count):
    return min(c["low"] for c in candles[-count:])


def get_bias(h1, m15):
    h1c = [c["close"] for c in h1]
    m15c = [c["close"] for c in m15]

    if sma(h1c, 5) > sma(h1c, 20) and sma(m15c, 5) > sma(m15c, 20):
        return "BULLISH"
    if sma(h1c, 5) < sma(h1c, 20) and sma(m15c, 5) < sma(m15c, 20):
        return "BEARISH"
    return "NEUTRAL"


# =========================================================
# CANDLES
# =========================================================

def bullish_candle(c):
    total = max(c["high"] - c["low"], 1e-9)
    body = c["close"] - c["open"]
    close_near_high = (c["high"] - c["close"]) <= total * 0.2
    return c["close"] > c["open"] and body >= total * 0.6 and close_near_high


def bearish_candle(c):
    total = max(c["high"] - c["low"], 1e-9)
    body = c["open"] - c["close"]
    close_near_low = (c["close"] - c["low"]) <= total * 0.2
    return c["close"] < c["open"] and body >= total * 0.6 and close_near_low


# =========================================================
# STRUCTURE
# =========================================================

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


def detect_fvg_zone(candles):
    if len(candles) < 3:
        return None
    c1 = candles[-3]
    c3 = candles[-1]

    if c3["low"] > c1["high"]:
        return {
            "side": "BUY",
            "zone_low": c1["high"],
            "zone_high": c3["low"],
        }

    if c3["high"] < c1["low"]:
        return {
            "side": "SELL",
            "zone_low": c3["high"],
            "zone_high": c1["low"],
        }

    return None


def detect_sweep(c):
    if len(c) < 2:
        return None

    prev = c[-2]
    last = c[-1]

    if last["low"] < prev["low"] and last["close"] > prev["low"]:
        return "BUY"
    if last["high"] > prev["high"] and last["close"] < prev["high"]:
        return "SELL"
    return None


def detect_bos(c):
    if len(c) < 6:
        return None
    highs = [x["high"] for x in c[-6:-1]]
    lows = [x["low"] for x in c[-6:-1]]

    if c[-1]["close"] > max(highs):
        return "BUY"
    if c[-1]["close"] < min(lows):
        return "SELL"
    return None


def detect_choch(c):
    if len(c) < 8:
        return None
    closes = [x["close"] for x in c[-8:]]

    if closes[-1] > max(closes[:-1]):
        return "BUY"
    if closes[-1] < min(closes[:-1]):
        return "SELL"
    return None


def detect_ob(c):
    if len(c) < 2:
        return None
    prev = c[-2]
    last = c[-1]

    if prev["close"] < prev["open"] and last["close"] > prev["high"]:
        return "BUY"
    if prev["close"] > prev["open"] and last["close"] < prev["low"]:
        return "SELL"
    return None


def detect_magnet(m15):
    return recent_high(m15, min(20, len(m15))), recent_low(m15, min(20, len(m15)))


# =========================================================
# SL
# =========================================================

def local_buy_sl(m15, entry):
    structure_low = min(c["low"] for c in m15[-10:])
    buffer = entry * 0.002
    return structure_low - buffer


def local_sell_sl(m15, entry):
    structure_high = max(c["high"] for c in m15[-10:])
    buffer = entry * 0.002
    return structure_high + buffer


def in_zone(price, zone_low, zone_high):
    return zone_low <= price <= zone_high


# =========================================================
# MAIN
# =========================================================

def evaluate_signal_engine(mtf):
    m5 = mtf["m5"]
    m15 = mtf["m15"]
    h1 = mtf["h1"]

    bias = get_bias(h1, m15)
    price = m5[-1]["close"]

    m5_fvg = detect_fvg(m5)
    m15_fvg_zone = detect_fvg_zone(m15)
    sweep = detect_sweep(m5)
    bos = detect_bos(m5)
    choch = detect_choch(m5)
    ob = detect_ob(m5)

    magnet_up, magnet_down = detect_magnet(m15)

    last = m5[-1]

    signal_type = "NO CLEAR SETUP"
    signal_status = "WAIT"
    preferred_side = "WAIT"
    setup_mode = "NONE"

    entry = None
    sl = None
    tp1 = None
    tp2 = None
    tp_large = None

    wait_entry_price = None
    wait_zone_low = None
    wait_zone_high = None

    buy_fvg = "YES" if m5_fvg == "BUY" else "NO"
    sell_fvg = "YES" if m5_fvg == "SELL" else "NO"
    buy_ob = "YES" if ob == "BUY" else "NO"
    sell_ob = "YES" if ob == "SELL" else "NO"
    buy_sweep = "YES" if sweep == "BUY" else "NO"
    sell_sweep = "YES" if sweep == "SELL" else "NO"
    buy_bos = "YES" if bos == "BUY" else "NO"
    sell_bos = "YES" if bos == "SELL" else "NO"
    buy_choch = "YES" if choch == "BUY" else "NO"
    sell_choch = "YES" if choch == "SELL" else "NO"

    signal_score = 0

    # ---------------- BUY ----------------
    if bias == "BULLISH" and m15_fvg_zone and m15_fvg_zone["side"] == "BUY":
        zone_low = m15_fvg_zone["zone_low"]
        zone_high = m15_fvg_zone["zone_high"]
        planned_entry = (zone_low + zone_high) / 2

        extra_buy = sum([
            sweep == "BUY",
            bos == "BUY",
            choch == "BUY",
            ob == "BUY",
        ])

        if extra_buy >= 1:
            preferred_side = "BUY"
            wait_entry_price = planned_entry
            wait_zone_low = zone_low
            wait_zone_high = zone_high

            # WAIT mode first
            signal_type = "WAIT ENTRY BUY"
            signal_status = "WAIT"
            setup_mode = "FULL" if sweep == "BUY" else "SAFE"
            signal_score = 78 if sweep == "BUY" else 68

            # READY when price comes into zone and m5 candle confirms
            if in_zone(price, zone_low, zone_high) and bullish_candle(last):
                entry = price
                sl = local_buy_sl(m15, entry)
                risk = max(entry - sl, 1e-9)

                if sweep == "BUY":
                    tp1 = entry + risk * 1.2
                    tp2 = entry + risk * 2.0
                    tp_large = entry + risk * 3.0
                    setup_mode = "FULL"
                    signal_score = 95
                else:
                    tp1 = entry + risk * 1.0
                    tp2 = entry + risk * 1.4
                    tp_large = entry + risk * 1.8
                    setup_mode = "SAFE"
                    signal_score = 78

                signal_type = "BUY ENTRY READY"
                signal_status = "CONFIRMED BUY"

    # ---------------- SELL ----------------
    if bias == "BEARISH" and m15_fvg_zone and m15_fvg_zone["side"] == "SELL":
        zone_low = m15_fvg_zone["zone_low"]
        zone_high = m15_fvg_zone["zone_high"]
        planned_entry = (zone_low + zone_high) / 2

        extra_sell = sum([
            sweep == "SELL",
            bos == "SELL",
            choch == "SELL",
            ob == "SELL",
        ])

        if extra_sell >= 1:
            preferred_side = "SELL"
            wait_entry_price = planned_entry
            wait_zone_low = zone_low
            wait_zone_high = zone_high

            signal_type = "WAIT ENTRY SELL"
            signal_status = "WAIT"
            setup_mode = "FULL" if sweep == "SELL" else "SAFE"
            signal_score = 78 if sweep == "SELL" else 68

            if in_zone(price, zone_low, zone_high) and bearish_candle(last):
                entry = price
                sl = local_sell_sl(m15, entry)
                risk = max(sl - entry, 1e-9)

                if sweep == "SELL":
                    tp1 = entry - risk * 1.2
                    tp2 = entry - risk * 2.0
                    tp_large = entry - risk * 3.0
                    setup_mode = "FULL"
                    signal_score = 95
                else:
                    tp1 = entry - risk * 1.0
                    tp2 = entry - risk * 1.4
                    tp_large = entry - risk * 1.8
                    setup_mode = "SAFE"
                    signal_score = 78

                signal_type = "SELL ENTRY READY"
                signal_status = "CONFIRMED SELL"

    return {
        "signal_type": signal_type,
        "signal_status": signal_status,
        "preferred_side": preferred_side,
        "setup_mode": setup_mode,
        "entry_price": entry,
        "sl_price": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp_large": tp_large,
        "wait_entry_price": wait_entry_price,
        "wait_zone_low": wait_zone_low,
        "wait_zone_high": wait_zone_high,
        "buy_fvg": buy_fvg,
        "sell_fvg": sell_fvg,
        "buy_ob": buy_ob,
        "sell_ob": sell_ob,
        "buy_sweep": buy_sweep,
        "sell_sweep": sell_sweep,
        "buy_bos": buy_bos,
        "sell_bos": sell_bos,
        "buy_choch": buy_choch,
        "sell_choch": sell_choch,
        "stronger_magnet": "UP" if preferred_side == "BUY" else "DOWN",
        "fib_618": "-",
        "trigger_price": price,
        "signal_score": signal_score,
    }
