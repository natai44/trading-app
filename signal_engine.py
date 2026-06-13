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


def trend_1h(c1h):
    if len(c1h) < 20:
        return None

    last = c1h[0]["close"]
    prev = c1h[10]["close"]

    if last > prev:
        return "BUY"
    if last < prev:
        return "SELL"
    return None


def detect_fvg(c15):
    if len(c15) < 5:
        return None

    c1 = c15[2]
    c2 = c15[1]
    c3 = c15[0]

    total = c2["high"] - c2["low"]
    impulse = abs(c2["close"] - c2["open"])

    if total <= 0:
        return None

    if impulse / total < 0.35:
        return None

    if c1["high"] < c3["low"]:
        return ("BUY", c1["high"], c3["low"])

    if c1["low"] > c3["high"]:
        return ("SELL", c3["high"], c1["low"])

    return None


def detect_bos(c15):
    if len(c15) < 15:
        return None

    last = c15[0]
    prev_high = recent_high(c15, 1, 12)
    prev_low = recent_low(c15, 1, 12)

    if prev_high is None or prev_low is None:
        return None

    if last["close"] > prev_high:
        return "BUY"
    if last["close"] < prev_low:
        return "SELL"

    return None


def detect_choch(c15, c1h):
    if len(c15) < 20 or len(c1h) < 20:
        return None

    htf = trend_1h(c1h)
    bos = detect_bos(c15)

    if htf and bos and htf != bos:
        return bos

    return bos


def detect_sweep(c15):
    if len(c15) < 8:
        return None

    last = c15[0]
    prev_high = recent_high(c15, 1, 8)
    prev_low = recent_low(c15, 1, 8)

    if prev_high is None or prev_low is None:
        return None

    if last["high"] > prev_high and last["close"] < prev_high:
        return "SELL"

    if last["low"] < prev_low and last["close"] > prev_low:
        return "BUY"

    return None


def candle_confirm(c, side):
    if side == "BUY":
        return c["close"] > c["open"]
    if side == "SELL":
        return c["close"] < c["open"]
    return False


def make_targets(entry, sl, side):
    risk = abs(entry - sl)

    if side == "BUY":
        return entry + risk * 1.0, entry + risk * 1.7, entry + risk * 2.5

    if side == "SELL":
        return entry - risk * 1.0, entry - risk * 1.7, entry - risk * 2.5

    return None, None, None


def valid_risk(entry, sl):
    risk = abs(entry - sl)

    # Gold Schutz: kein Mini-SL und kein riesiger SL
    if risk < 8:
        return False
    if risk > 55:
        return False

    return True


def get_structure_sl(c15, c1h, side, zone_low, zone_high):
    if side == "BUY":
        sl_15 = recent_low(c15, 0, 8)
        sl_1h = recent_low(c1h, 0, 4)

        if sl_15 is None or sl_1h is None:
            return None

        return min(sl_15, zone_low)

    if side == "SELL":
        sl_15 = recent_high(c15, 0, 8)
        sl_1h = recent_high(c1h, 0, 4)

        if sl_15 is None or sl_1h is None:
            return None

        return max(sl_15, zone_high)

    return None


def build_signal(side, price, sl, tp1, tp2, tp_large, score, triggers, fvg, sweep, bos, choch, magnet):
    return {
        "signal_type": f"{side} ENTRY READY",
        "preferred_side": side,
        "entry_price": price,
        "sl_price": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp_large": tp_large,
        "trigger_price": price,
        "setup_mode": "ACTIVE",
        "signal_score": score,
        "trigger_count": triggers,
        "fvg": fvg,
        "ob": False,
        "sweep": sweep,
        "bos": bos,
        "choch": choch,
        "magnet": magnet,
    }


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

    if len(c15) < 30 or len(c1h) < 20:
        return no_setup(None)

    price = c15[0]["close"]
    last = c15[0]

    htf = trend_1h(c1h)
    fvg = detect_fvg(c15)
    bos_side = detect_bos(c15)
    choch_side = detect_choch(c15, c1h)
    sweep_side = detect_sweep(c15)

    if not htf or not fvg:
        return no_setup(price)

    fvg_side, zone_low, zone_high = fvg

    magnet = "UP" if htf == "BUY" else "DOWN"

    # Hauptseite: Magnet + FVG müssen passen
    if fvg_side != htf:
        return no_setup(price)

    side = htf

    # Preis muss nahe/innerhalb FVG sein
    buffer = price * 0.0007
    in_zone = (zone_low - buffer) <= price <= (zone_high + buffer)

    if not in_zone:
        return no_setup(price)

    if not candle_confirm(last, side):
        return no_setup(price)

    triggers = 0

    fvg_yes = True
    bos_yes = bos_side == side
    choch_yes = choch_side == side
    sweep_yes = sweep_side == side

    if fvg_yes:
        triggers += 1
    if bos_yes:
        triggers += 1
    if choch_yes:
        triggers += 1
    if sweep_yes:
        triggers += 1
    if magnet in ["UP", "DOWN"]:
        triggers += 1

    # Mindestens 3 Trigger, Sweep nicht Pflicht
    if triggers < 3:
        return no_setup(price)

    sl = get_structure_sl(c15, c1h, side, zone_low, zone_high)

    if sl is None:
        return no_setup(price)

    if side == "BUY" and sl >= price:
        return no_setup(price)

    if side == "SELL" and sl <= price:
        return no_setup(price)

    if not valid_risk(price, sl):
        return no_setup(price)

    tp1, tp2, tp_large = make_targets(price, sl, side)

    if tp1 == tp2 or tp2 == tp_large:
        return no_setup(price)

    score = 80 + triggers * 4
    score = min(score, 100)

    return build_signal(
        side=side,
        price=price,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        tp_large=tp_large,
        score=score,
        triggers=triggers,
        fvg=True,
        sweep=sweep_yes,
        bos=bos_yes,
        choch=choch_yes,
        magnet=magnet,
    )
