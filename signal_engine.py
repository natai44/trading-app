import requests

# =========================================
# FORMAT
# =========================================

def format_price(p):
    if p is None:
        return "-"
    return f"{p:.2f}"


# =========================================
# DATA
# =========================================

def get_crypto(symbol, interval):
    url = "https://api.binance.com/api/v3/klines"
    r = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": 100})
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


def get_forex(symbol, interval):
    url = "https://api.twelvedata.com/time_series"
    r = requests.get(url, params={
        "symbol": symbol,
        "interval": interval,
        "apikey": "8f8f55c79aa54b789bd3177ce55e224e"
    })
    data = r.json()

    candles = []
    for c in reversed(data["values"]):
        candles.append({
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
        })
    return candles


def get_multi_timeframe_analysis(market, symbol):
    if market == "crypto":
        return {
            "m5": get_crypto(symbol, "5m"),
            "m15": get_crypto(symbol, "15m"),
        }
    else:
        return {
            "m5": get_forex(symbol, "5min"),
            "m15": get_forex(symbol, "15min"),
        }


# =========================================
# LOGIC
# =========================================

def detect_fvg(c):
    if len(c) < 3:
        return False, False

    c1, c2, c3 = c[-3], c[-2], c[-1]

    bullish = c3["low"] > c1["high"]
    bearish = c3["high"] < c1["low"]

    return bullish, bearish


def detect_sweep(c):
    last = c[-1]
    prev = c[-2]

    upper = last["high"] > prev["high"] and last["close"] < prev["high"]
    lower = last["low"] < prev["low"] and last["close"] > prev["low"]

    return lower, upper


def detect_ob(c):
    last = c[-1]
    prev = c[-2]

    bullish = prev["close"] < prev["open"] and last["close"] > last["open"]
    bearish = prev["close"] > prev["open"] and last["close"] < last["open"]

    return bullish, bearish


def candle_confirm(c):
    last = c[-1]
    prev = c[-2]

    # 🔴 rote → BUY
    if prev["close"] < prev["open"] and last["close"] > last["high"] - (last["high"] - last["low"]) * 0.2:
        return "BUY"

    # 🟢 grüne → SELL
    if prev["close"] > prev["open"] and last["close"] < last["low"] + (last["high"] - last["low"]) * 0.2:
        return "SELL"

    return None


def evaluate_signal_engine(mtf):
    m5 = mtf["m5"]
    m15 = mtf["m15"]

    price = m5[-1]["close"]

    # =====================
    # DETECTION
    # =====================

    fvg_b, fvg_s = detect_fvg(m5)
    sweep_b, sweep_s = detect_sweep(m5)
    ob_b, ob_s = detect_ob(m5)

    confirm = candle_confirm(m5)

    # =====================
    # MAGNET (simple)
    # =====================

    highs = [c["high"] for c in m15[-20:]]
    lows = [c["low"] for c in m15[-20:]]

    magnet_up = max(highs)
    magnet_down = min(lows)

    # =====================
    # FIB
    # =====================

    fib_618 = (magnet_up + magnet_down) / 2

    # =====================
    # BUY LOGIC
    # =====================

    buy_triggers = sum([fvg_b, sweep_b, ob_b])
    sell_triggers = sum([fvg_s, sweep_s, ob_s])

    # =====================
    # ENTRY + SL
    # =====================

    sl_buy = min(c["low"] for c in m15[-5:])
    sl_sell = max(c["high"] for c in m15[-5:])

    risk_buy = price - sl_buy
    risk_sell = sl_sell - price

    tp_buy = price + risk_buy * 2
    tp_sell = price - risk_sell * 2

    # =====================
    # FINAL SIGNAL
    # =====================

    if confirm == "BUY" and buy_triggers >= 2:
        return {
            "signal_type": "BUY ENTRY READY",
            "preferred_side": "BUY",
            "entry_price": price,
            "sl_price": sl_buy,
            "tp1": tp_buy,
            "tp2": tp_buy,
            "tp_large": magnet_up,

            "buy_fvg": "YES" if fvg_b else "NO",
            "sell_fvg": "NO",
            "buy_ob": "YES" if ob_b else "NO",
            "sell_ob": "NO",
            "buy_sweep": "YES" if sweep_b else "NO",
            "sell_sweep": "NO",

            "stronger_magnet": "UP",
            "fib_618": fib_618,
        }

    if confirm == "SELL" and sell_triggers >= 2:
        return {
            "signal_type": "SELL ENTRY READY",
            "preferred_side": "SELL",
            "entry_price": price,
            "sl_price": sl_sell,
            "tp1": tp_sell,
            "tp2": tp_sell,
            "tp_large": magnet_down,

            "buy_fvg": "NO",
            "sell_fvg": "YES" if fvg_s else "NO",
            "buy_ob": "NO",
            "sell_ob": "YES" if ob_s else "NO",
            "buy_sweep": "NO",
            "sell_sweep": "YES" if sweep_s else "NO",

            "stronger_magnet": "DOWN",
            "fib_618": fib_618,
        }

    return {
        "signal_type": "NO SIGNAL",
        "preferred_side": "WAIT",
        "signal_score": 0
    }
