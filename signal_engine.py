import requests
import time

# =========================================
# PRICE FORMAT
# =========================================

def format_price(price):
    if price is None:
        return "-"
    if abs(price) < 10:
        return f"{price:.5f}"
    if abs(price) < 1000:
        return f"{price:.2f}"
    return f"{price:,.2f}"


# =========================================
# DATA FETCH
# =========================================

def get_crypto_candles(symbol="BTCUSDT", interval="5m", limit=150):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=8)
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


def get_gold_forex(symbol="XAU/USD", interval="5min"):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": "8f8f55c79aa54b789bd3177ce55e224e"
    }
    r = requests.get(url, params=params, timeout=8)
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


# =========================================
# BASIC ANALYSIS
# =========================================

def get_multi_timeframe_analysis(market, symbol):
    if market == "crypto":
        m5 = get_crypto_candles(symbol, "5m")
        m15 = get_crypto_candles(symbol, "15m")
    else:
        m5 = get_gold_forex(symbol, "5min")
        m15 = get_gold_forex(symbol, "15min")

    return {
        "M5": m5,
        "M15": m15
    }


# =========================================
# SIMPLE SIGNAL LOGIC
# =========================================

def evaluate_signal_engine(mtf):
    m5 = mtf["M5"]
    m15 = mtf["M15"]

    last = m5[-1]
    prev = m5[-2]

    price = last["close"]

    # Simple confirmation candle
    bullish = last["close"] > last["open"] and prev["close"] < prev["open"]
    bearish = last["close"] < last["open"] and prev["close"] > prev["open"]

    # Local SL (small)
    sl_buy = min(c["low"] for c in m15[-5:])
    sl_sell = max(c["high"] for c in m15[-5:])

    risk_buy = price - sl_buy
    risk_sell = sl_sell - price

    tp_buy = price + risk_buy * 1.5
    tp_sell = price - risk_sell * 1.5

    if bullish:
        return {
            "signal_type": "BUY ENTRY READY",
            "preferred_side": "BUY",
            "entry_price": price,
            "sl_price": sl_buy,
            "tp1": tp_buy,
            "tp2": tp_buy,
            "signal_score": 70
        }

    if bearish:
        return {
            "signal_type": "SELL ENTRY READY",
            "preferred_side": "SELL",
            "entry_price": price,
            "sl_price": sl_sell,
            "tp1": tp_sell,
            "tp2": tp_sell,
            "signal_score": 70
        }

    return {
        "signal_type": "NO SIGNAL",
        "signal_score": 0
    }
