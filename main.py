
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import requests
import numpy as np
import cv2
import base64
import uuid
import sqlite3
import secrets
from datetime import datetime

app = FastAPI(title="Trading Mentor App Final")

DB_PATH = "app.db"
TWELVE_DATA_API_KEY = "8f8f55c79aa54b789bd3177ce55e224e"

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_ADMIN_EMAIL = "abdisanatai@gmail.com"

DEFAULT_USER_USERNAME = "user"
DEFAULT_USER_PASSWORD = "user123"
DEFAULT_USER_EMAIL = "user@example.com"


def tr(lang: str, de_text: str, en_text: str) -> str:
    return en_text if lang == "en" else de_text


def base_head(title: str) -> str:
    return f"""
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{title}</title>
        <style>
            :root {{
                --bg: #0b0f19;
                --panel: rgba(20, 27, 39, 0.92);
                --line: #243042;
                --text: #edf2f7;
                --muted: #9fb0c3;
                --green: #00ff88;
                --green-2: #00c972;
                --red: #ff6b6b;
                --yellow: #ffd166;
                --blue: #5aa9ff;
                --shadow: 0 20px 40px rgba(0,0,0,0.35);
                --radius: 18px;
            }}
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                font-family: Inter, Arial, sans-serif;
                color: var(--text);
                background:
                    radial-gradient(circle at top left, rgba(0,255,136,0.08), transparent 30%),
                    radial-gradient(circle at top right, rgba(90,169,255,0.10), transparent 25%),
                    linear-gradient(180deg, #0a0e17 0%, #0b0f19 100%);
                min-height: 100vh;
            }}
            .container {{
                max-width: 1520px;
                margin: 0 auto;
                padding: 24px;
            }}
            .topbar {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 16px;
                margin-bottom: 18px;
                flex-wrap: wrap;
            }}
            .brand {{
                display: flex;
                flex-direction: column;
                gap: 4px;
            }}
            .brand-title {{
                font-size: 30px;
                font-weight: 800;
                color: var(--green);
            }}
            .brand-sub {{
                color: var(--muted);
                font-size: 14px;
            }}
            .actions {{
                display: flex;
                gap: 10px;
                align-items: center;
                flex-wrap: wrap;
            }}
            .chip {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 10px 14px;
                border: 1px solid var(--line);
                border-radius: 999px;
                background: rgba(255,255,255,0.03);
                color: var(--text);
                text-decoration: none;
                font-size: 14px;
            }}
            .chip:hover {{ border-color: var(--green); }}
            .grid {{ display: grid; gap: 20px; }}
            .grid-2 {{ grid-template-columns: 1fr 1fr; }}
            .grid-main {{ grid-template-columns: 1.15fr 0.85fr; }}
            .card {{
                background: var(--panel);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255,255,255,0.06);
                box-shadow: var(--shadow);
                border-radius: var(--radius);
                padding: 20px;
            }}
            .hero {{
                padding: 24px;
                border-radius: 24px;
                border: 1px solid rgba(255,255,255,0.06);
                background:
                    linear-gradient(135deg, rgba(0,255,136,0.10), rgba(90,169,255,0.08)),
                    var(--panel);
                box-shadow: var(--shadow);
                margin-bottom: 22px;
            }}
            .hero-title {{
                font-size: 34px;
                font-weight: 800;
                margin: 0 0 8px 0;
                color: white;
            }}
            .hero-sub {{
                font-size: 15px;
                color: var(--muted);
                max-width: 1100px;
                line-height: 1.6;
            }}
            label {{
                display: block;
                font-size: 14px;
                color: var(--muted);
                margin-bottom: 8px;
            }}
            input, textarea {{
                width: 100%;
                border: 1px solid #2b3b52;
                background: rgba(255,255,255,0.03);
                color: white;
                padding: 13px 14px;
                border-radius: 12px;
                outline: none;
                font-size: 15px;
            }}
            input:focus, textarea:focus {{
                border-color: var(--green);
                box-shadow: 0 0 0 3px rgba(0,255,136,0.10);
            }}
            textarea {{
                min-height: 120px;
                resize: vertical;
            }}
            .btn {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
                padding: 12px 18px;
                border: none;
                border-radius: 12px;
                cursor: pointer;
                text-decoration: none;
                font-weight: 700;
                color: #091018;
                background: linear-gradient(135deg, var(--green), var(--green-2));
                box-shadow: 0 10px 20px rgba(0, 255, 136, 0.18);
            }}
            .btn-secondary {{
                background: rgba(255,255,255,0.05);
                color: white;
                border: 1px solid var(--line);
                box-shadow: none;
            }}
            .btn-danger {{
                background: linear-gradient(135deg, #ff6b6b, #ff8e72);
                color: white;
                box-shadow: none;
            }}
            .btn-warning {{
                background: linear-gradient(135deg, #ffd166, #ffb347);
                color: #091018;
                box-shadow: none;
            }}
            .form-row {{ margin-bottom: 16px; }}
            .info-list {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
            }}
            .info-item {{
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 14px;
                padding: 14px;
            }}
            .info-label {{
                color: var(--muted);
                font-size: 13px;
                margin-bottom: 6px;
            }}
            .info-value {{
                font-size: 15px;
                font-weight: 700;
            }}
            .section-title {{
                font-size: 18px;
                color: var(--green);
                margin: 16px 0 10px;
                font-weight: 800;
            }}
            .banner {{
                padding: 14px 16px;
                border-radius: 14px;
                margin-bottom: 16px;
                border: 1px solid transparent;
            }}
            .banner-success {{
                background: rgba(0,255,136,0.08);
                border-color: rgba(0,255,136,0.18);
                color: #bff5d7;
            }}
            .banner-error {{
                background: rgba(255,107,107,0.10);
                border-color: rgba(255,107,107,0.20);
                color: #ffd0d0;
            }}
            .banner-warning {{
                background: rgba(255,209,102,0.10);
                border-color: rgba(255,209,102,0.22);
                color: #ffe7a6;
            }}
            .banner-blue {{
                background: rgba(90,169,255,0.10);
                border-color: rgba(90,169,255,0.22);
                color: #cfe6ff;
            }}
            .image-frame {{
                border-radius: 18px;
                overflow: hidden;
                border: 1px solid rgba(255,255,255,0.06);
                background: #0a0e16;
            }}
            .image-frame img {{
                width: 100%;
                display: block;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            th, td {{
                text-align: left;
                padding: 12px 10px;
                border-bottom: 1px solid #223044;
                vertical-align: top;
                font-size: 14px;
            }}
            th {{
                color: var(--muted);
                font-weight: 700;
                background: rgba(255,255,255,0.02);
            }}
            .login-wrap {{
                max-width: 540px;
                margin: 40px auto;
            }}
            .trend-up {{ color: var(--green); }}
            .trend-down {{ color: var(--red); }}
            .trend-neutral {{ color: var(--yellow); }}
            .footer-note {{
                margin-top: 20px;
                color: var(--muted);
                font-size: 13px;
                line-height: 1.6;
            }}
            @media (max-width: 980px) {{
                .grid-2, .grid-main, .info-list {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    """


def page(title: str, body: str) -> str:
    return f"""
    <html>
        {base_head(title)}
        <body>
            <div class="container">
                {body}
            </div>
        </body>
    </html>
    """


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.utcnow().isoformat()


def init_db():
    conn = db_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS access_requests (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            desired_username TEXT NOT NULL,
            message TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_username TEXT,
            created_password TEXT,
            created_at TEXT NOT NULL,
            decided_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS signal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market TEXT NOT NULL,
            symbol TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            signal_score REAL NOT NULL,
            signal_status TEXT NOT NULL,
            prep_price REAL,
            trigger_price REAL,
            entry_price REAL,
            sl_price REAL,
            tp1 REAL,
            tp2 REAL,
            tp_medium REAL,
            tp_large REAL,
            zone_low REAL,
            zone_high REAL,
            last_day_high REAL,
            last_day_low REAL,
            last_h1_high REAL,
            last_h1_low REAL,
            explanation TEXT,
            timeframe_note TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market TEXT NOT NULL,
            symbol TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            signal_status TEXT NOT NULL,
            signal_score REAL NOT NULL,
            entry_price REAL,
            sl_price REAL,
            tp1 REAL,
            tp2 REAL,
            tp_medium REAL,
            tp_large REAL,
            message TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("SELECT * FROM users WHERE username = ?", (DEFAULT_ADMIN_USERNAME,))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users (username, email, password, role, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            DEFAULT_ADMIN_USERNAME,
            DEFAULT_ADMIN_EMAIL,
            DEFAULT_ADMIN_PASSWORD,
            "admin",
            1,
            now_iso()
        ))

    cur.execute("SELECT * FROM users WHERE username = ?", (DEFAULT_USER_USERNAME,))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users (username, email, password, role, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            DEFAULT_USER_USERNAME,
            DEFAULT_USER_EMAIL,
            DEFAULT_USER_PASSWORD,
            "user",
            1,
            now_iso()
        ))

    conn.commit()
    conn.close()


init_db()


def format_price(price):
    if price is None:
        return "-"
    price = float(price)
    if abs(price) < 10:
        return f"{price:.5f}"
    if abs(price) < 1000:
        return f"{price:.2f}"
    return f"{price:,.2f}"


def to_base64_png(img: np.ndarray) -> str:
    ok, buffer = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("Bild konnte nicht erstellt werden")
    return base64.b64encode(buffer).decode("utf-8")


def generate_password(length: int = 10) -> str:
    return secrets.token_hex(length // 2 + 1)[:length]


def get_user(username: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row


def get_current_user(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None

    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sessions WHERE token = ?", (session_token,))
    session_row = cur.fetchone()
    if not session_row:
        conn.close()
        return None

    cur.execute("SELECT * FROM users WHERE username = ?", (session_row["username"],))
    user = cur.fetchone()
    conn.close()

    if not user or int(user["active"]) != 1:
        return None

    return {
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "active": bool(user["active"])
    }


def require_login(request: Request):
    return get_current_user(request)


def require_admin(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return None
    return user


def create_session(username: str):
    token = str(uuid.uuid4())
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sessions (token, username, created_at) VALUES (?, ?, ?)",
        (token, username, now_iso())
    )
    conn.commit()
    conn.close()
    return token


def delete_session(token: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def trend_class(trend: str) -> str:
    if trend == "BULLISH":
        return "trend-up"
    if trend == "BEARISH":
        return "trend-down"
    return "trend-neutral"


def topbar(lang: str, user=None, show_profile=True, show_admin=False):
    auth = ""
    if user:
        profile_link = f'<a class="chip" href="/profile?lang={lang}">{tr(lang, "Profil", "Profile")}</a>' if show_profile else ""
        admin_link = f'<a class="chip" href="/admin?lang={lang}">Admin</a>' if show_admin else ""
        auth = f"""
        <div class="actions">
            <span class="chip">{tr(lang, "Eingeloggt als", "Logged in as")}: <b>{user['username']}</b> ({user['role']})</span>
            {profile_link}
            {admin_link}
            <a class="chip" href="/logout?lang={lang}">{tr(lang, "Logout", "Logout")}</a>
        </div>
        """
    return f"""
    <div class="topbar">
        <div class="brand">
            <div class="brand-title">Trading Mentor App</div>
            <div class="brand-sub">Last H1 SL / Last D & H1 targets</div>
        </div>
        <div class="actions">
            <a class="chip" href="?lang=de">Deutsch</a>
            <a class="chip" href="?lang=en">English</a>
        </div>
        {auth}
    </div>
    """


def get_crypto_candles(symbol: str = "BTCUSDT", interval: str = "5m", limit: int = 200):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol.upper().strip(), "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=8)
    r.raise_for_status()
    data = r.json()

    if not isinstance(data, list) or not data:
        raise ValueError("Crypto-Daten konnten nicht geladen werden")

    candles = []
    for row in data:
        candles.append({
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
        })
    return candles


def get_forex_or_gold_candles(symbol: str = "XAU/USD", interval: str = "5min", outputsize: int = 200):
    if not TWELVE_DATA_API_KEY:
        raise ValueError("Twelve Data API Key fehlt")

    api_symbol = normalize_twelve_symbol(symbol)

    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": api_symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_API_KEY,
        "format": "JSON",
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    if "values" not in data or not data["values"]:
        raise ValueError(data.get("message", f"Forex/Gold-Daten konnten nicht geladen werden: {api_symbol}"))

    values = list(reversed(data["values"]))
    candles = []
    for row in values:
        candles.append({
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })
    return candles


def normalize_twelve_symbol(symbol: str) -> str:
    raw = symbol.strip().upper().replace(" ", "")
    mapping = {
        "EURUSD": "EUR/USD",
        "GBPUSD": "GBP/USD",
        "USDJPY": "USD/JPY",
        "USDCHF": "USD/CHF",
        "USDCAD": "USD/CAD",
        "AUDUSD": "AUD/USD",
        "NZDUSD": "NZD/USD",
        "XAUUSD": "XAU/USD",
        "XAGUSD": "XAG/USD",
        "EUR/USD": "EUR/USD",
        "GBP/USD": "GBP/USD",
        "USD/JPY": "USD/JPY",
        "USD/CHF": "USD/CHF",
        "USD/CAD": "USD/CAD",
        "AUD/USD": "AUD/USD",
        "NZD/USD": "NZD/USD",
        "XAU/USD": "XAU/USD",
        "XAG/USD": "XAG/USD",
    }
    return mapping.get(raw, raw)


def calculate_fibonacci(last_high, last_low):
    diff = max(last_high - last_low, 1e-9)
    return {
        "fib_50": last_high - diff * 0.500,
        "fib_618": last_high - diff * 0.618,
        "fib_786": last_high - diff * 0.786,
    }


def detect_order_blocks(candles):
    bullish_ob = None
    bearish_ob = None
    for i in range(2, len(candles) - 2):
        c0 = candles[i]
        c1 = candles[i + 1]
        c2 = candles[i + 2]

        if c0["close"] < c0["open"] and c1["close"] > c1["open"] and c2["close"] > c2["open"] and c2["close"] > c0["high"]:
            bullish_ob = (c0["low"], c0["high"])

        if c0["close"] > c0["open"] and c1["close"] < c1["open"] and c2["close"] < c2["open"] and c2["close"] < c0["low"]:
            bearish_ob = (c0["low"], c0["high"])
    return bullish_ob, bearish_ob


def detect_liquidity_sweeps(candles, ref_high, ref_low):
    if len(candles) < 2:
        return {"upper_sweep": False, "lower_sweep": False}
    last = candles[-1]
    upper_sweep = last["high"] > ref_high and last["close"] < ref_high
    lower_sweep = last["low"] < ref_low and last["close"] > ref_low
    return {"upper_sweep": upper_sweep, "lower_sweep": lower_sweep}


def get_session_context():
    from datetime import datetime, timezone
    hour = datetime.now(timezone.utc).hour
    if 0 <= hour < 7:
        return "Asia Session"
    if 7 <= hour < 12:
        return "London Open Window"
    if 12 <= hour < 17:
        return "London / New York Overlap"
    if 17 <= hour < 22:
        return "New York Session"
    return "Late NY / Rollover"


def find_swings(highs, lows, lookback=2):
    swing_highs = []
    swing_lows = []
    for i in range(lookback, len(highs) - lookback):
        is_high = all(highs[i] > highs[j] for j in range(i - lookback, i + lookback + 1) if j != i)
        is_low = all(lows[i] < lows[j] for j in range(i - lookback, i + lookback + 1) if j != i)
        if is_high:
            swing_highs.append((i, highs[i]))
        if is_low:
            swing_lows.append((i, lows[i]))
    return swing_highs, swing_lows


def detect_fvg(candles):
    bullish_fvg = None
    bearish_fvg = None
    for i in range(2, len(candles)):
        c1 = candles[i - 2]
        c3 = candles[i]
        if c3["low"] > c1["high"]:
            bullish_fvg = (c1["high"], c3["low"])
        if c3["high"] < c1["low"]:
            bearish_fvg = (c3["high"], c1["low"])
    return bullish_fvg, bearish_fvg


def detect_equal_highs_lows(highs, lows, tolerance_ratio=0.0015):
    eq_high = None
    eq_low = None

    for i in range(len(highs) - 1, 1, -1):
        for j in range(i - 1, max(i - 8, 0), -1):
            avg_h = (highs[i] + highs[j]) / 2
            if avg_h > 0 and abs(highs[i] - highs[j]) / avg_h <= tolerance_ratio:
                eq_high = avg_h
                break
        if eq_high is not None:
            break

    for i in range(len(lows) - 1, 1, -1):
        for j in range(i - 1, max(i - 8, 0), -1):
            avg_l = (lows[i] + lows[j]) / 2
            if avg_l > 0 and abs(lows[i] - lows[j]) / avg_l <= tolerance_ratio:
                eq_low = avg_l
                break
        if eq_low is not None:
            break

    return eq_high, eq_low


def calc_atr(candles, period=14):
    if len(candles) < period + 1:
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        return max(max(highs) - min(lows), 1e-9)

    trs = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    recent = trs[-period:]
    return max(sum(recent) / len(recent), 1e-9)


def analyze_single_timeframe(candles, label: str):
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    current_price = closes[-1]
    sma_5 = sum(closes[-5:]) / 5
    sma_20 = sum(closes[-20:]) / 20
    atr = calc_atr(candles, 14)

    recent_high = max(highs[-30:])
    recent_low = min(lows[-30:])

    swing_highs, swing_lows = find_swings(highs, lows, lookback=2)
    bullish_fvg, bearish_fvg = detect_fvg(candles)
    eq_high, eq_low = detect_equal_highs_lows(highs[-30:], lows[-30:])
    bullish_ob, bearish_ob = detect_order_blocks(candles)

    last_swing_high = swing_highs[-1][1] if swing_highs else recent_high
    last_swing_low = swing_lows[-1][1] if swing_lows else recent_low

    if sma_5 > sma_20:
        trend = "BULLISH"
    elif sma_5 < sma_20:
        trend = "BEARISH"
    else:
        trend = "SIDEWAYS"

    bos = "NONE"
    if current_price > last_swing_high:
        bos = "BULLISH BOS"
    elif current_price < last_swing_low:
        bos = "BEARISH BOS"

    choch = "NONE"
    if trend == "BULLISH" and current_price < last_swing_low:
        choch = "BEARISH CHOCH"
    elif trend == "BEARISH" and current_price > last_swing_high:
        choch = "BULLISH CHOCH"

    support = min(lows[-15:])
    resistance = max(highs[-15:])
    buy_side_liquidity = recent_high
    sell_side_liquidity = recent_low

    premium_mid = recent_low + (recent_high - recent_low) * 0.5
    discount_zone = recent_low + (recent_high - recent_low) * 0.25
    premium_zone = recent_low + (recent_high - recent_low) * 0.75

    sweeps = detect_liquidity_sweeps(candles, last_swing_high, last_swing_low)

    if trend == "BULLISH":
        fvg = bullish_fvg
    elif trend == "BEARISH":
        fvg = bearish_fvg
    else:
        fvg = None

    if fvg:
        fvg_text = f"{format_price(fvg[0])} - {format_price(fvg[1])}"
    else:
        fvg_text = "Keine klare FVG"

    return {
        "label": label,
        "trend": trend,
        "bos": bos,
        "choch": choch,
        "current_price": current_price,
        "support": support,
        "resistance": resistance,
        "buy_side_liquidity": buy_side_liquidity,
        "sell_side_liquidity": sell_side_liquidity,
        "fvg_text": fvg_text,
        "recent_high": recent_high,
        "recent_low": recent_low,
        "eq_high": eq_high,
        "eq_low": eq_low,
        "premium_mid": premium_mid,
        "discount_zone": discount_zone,
        "premium_zone": premium_zone,
        "atr": atr,
        "last_swing_high": last_swing_high,
        "last_swing_low": last_swing_low,
        "bullish_fvg": bullish_fvg,
        "bearish_fvg": bearish_fvg,
        "bullish_ob": bullish_ob,
        "bearish_ob": bearish_ob,
        "upper_sweep": sweeps["upper_sweep"],
        "lower_sweep": sweeps["lower_sweep"],
    }



def extract_last_daily_info(daily_candles):
    if len(daily_candles) >= 2:
        last_closed = daily_candles[-2]
        today = daily_candles[-1]
    else:
        last_closed = daily_candles[-1]
        today = daily_candles[-1]

    return {
        "last_day_high": last_closed["high"],
        "last_day_low": last_closed["low"],
        "last_day_open": last_closed["open"],
        "last_day_close": last_closed["close"],
        "today_open": today["open"],
        "today_high_now": today["high"],
        "today_low_now": today["low"],
        "today_close_now": today["close"],
    }


def get_multi_timeframe_analysis(market: str, symbol: str):
    if market == "crypto":
        tf_map = {
            "M5": "5m",
            "M15": "15m",
            "H1": "1h",
            "H4": "4h",
            "D1": "1d",
        }
        fetcher = get_crypto_candles
        fetch_kwargs = {"symbol": symbol, "limit": 200}
    else:
        tf_map = {
            "M5": "5min",
            "M15": "15min",
            "H1": "1h",
            "H4": "4h",
            "D1": "1day",
        }
        fetcher = get_forex_or_gold_candles
        fetch_kwargs = {"symbol": symbol, "outputsize": 200}

    result = {}
    for name, tf in tf_map.items():
        candles = fetcher(interval=tf, **fetch_kwargs)
        result[name] = {
            "interval": tf,
            "candles": candles,
            "analysis": analyze_single_timeframe(candles, name)
        }

    result["daily_info"] = extract_last_daily_info(result["D1"]["candles"])
    return result


def combine_bias(mtf):
    trends = [
        mtf["M15"]["analysis"]["trend"],
        mtf["H1"]["analysis"]["trend"],
        mtf["H4"]["analysis"]["trend"],
        mtf["D1"]["analysis"]["trend"]
    ]
    bulls = trends.count("BULLISH")
    bears = trends.count("BEARISH")

    if bulls >= 3:
        return "BULLISH DAY BIAS", "groessere Aufwaertsbewegung moeglich"
    if bears >= 3:
        return "BEARISH DAY BIAS", "groessere Abwaertsbewegung moeglich"
    return "MIXED / RANGE", "unklar oder Range"


def evaluate_signal_engine(mtf):
    m5 = mtf["M5"]["analysis"]
    m15 = mtf["M15"]["analysis"]
    h1 = mtf["H1"]["analysis"]
    h4 = mtf["H4"]["analysis"]
    d1 = mtf["D1"]["analysis"]
    daily_info = mtf["daily_info"]

    current_price = m5["current_price"]
    last_day_high = daily_info["last_day_high"]
    last_day_low = daily_info["last_day_low"]
    today_open = daily_info["today_open"]

    last_h1_high = h1["recent_high"]
    last_h1_low = h1["recent_low"]
    fib = calculate_fibonacci(last_h1_high, last_h1_low)

    reasons = []
    day_range = max(last_day_high - last_day_low, h1["atr"], 1e-9)

    # Main zones from previous logic remain
    buy_zone_low = min(last_day_low + day_range * 0.10, h1["support"])
    buy_zone_high = min(last_day_low + day_range * 0.28, h1["support"] + h1["atr"] * 0.50)
    buy_entry = (buy_zone_low + buy_zone_high) / 2

    sell_zone_low = max(last_day_high - day_range * 0.28, h1["resistance"] - h1["atr"] * 0.50)
    sell_zone_high = max(last_day_high - day_range * 0.10, h1["resistance"])
    sell_entry = (sell_zone_low + sell_zone_high) / 2

    # user rules
    buy_sl = last_h1_low
    buy_tp_medium = last_h1_high
    buy_tp_large = last_day_high

    sell_sl = last_h1_high
    sell_tp_medium = last_h1_low
    sell_tp_large = last_day_low

    buy_risk = max(buy_entry - buy_sl, m5["atr"] * 1.0, 1e-9)
    sell_risk = max(sell_sl - sell_entry, m5["atr"] * 1.0, 1e-9)

    buy_tp1 = buy_entry + buy_risk * 1.0
    buy_tp2 = buy_entry + buy_risk * 1.5
    sell_tp1 = sell_entry - sell_risk * 1.0
    sell_tp2 = sell_entry - sell_risk * 1.5

    # Smart money confluence
    buy_fvg = m5["bullish_fvg"] or m15["bullish_fvg"] or h1["bullish_fvg"]
    sell_fvg = m5["bearish_fvg"] or m15["bearish_fvg"] or h1["bearish_fvg"]
    buy_ob = h1["bullish_ob"] or m15["bullish_ob"] or m5["bullish_ob"]
    sell_ob = h1["bearish_ob"] or m15["bearish_ob"] or m5["bearish_ob"]

    h1_sweep_sell = h1["upper_sweep"] or d1["upper_sweep"]
    h1_sweep_buy = h1["lower_sweep"] or d1["lower_sweep"]
    m5_sweep_sell = m5["upper_sweep"] or m15["upper_sweep"]
    m5_sweep_buy = m5["lower_sweep"] or m15["lower_sweep"]

    # both 5m sides always visible
    m5_buy_entry = current_price
    m5_buy_sl = last_h1_low
    m5_buy_risk = max(m5_buy_entry - m5_buy_sl, m5["atr"] * 1.2, 1e-9)
    m5_buy_tp1 = m5_buy_entry + m5_buy_risk * 1.0
    m5_buy_tp2 = m5_buy_entry + m5_buy_risk * 1.5
    m5_buy_status = "5M BUY PREPARATION"
    if m5_sweep_buy:
        m5_buy_status = "5M BUY SWEEP READY"
    if m5["trend"] == "BULLISH" and (m5["bos"] == "BULLISH BOS" or m5["choch"] == "BULLISH CHOCH"):
        m5_buy_status = "5M BUY ENTRY READY"

    m5_sell_entry = current_price
    m5_sell_sl = last_h1_high
    m5_sell_risk = max(m5_sell_sl - m5_sell_entry, m5["atr"] * 1.2, 1e-9)
    m5_sell_tp1 = m5_sell_entry - m5_sell_risk * 1.0
    m5_sell_tp2 = m5_sell_entry - m5_sell_risk * 1.5
    m5_sell_status = "5M SELL PREPARATION"
    if m5_sweep_sell:
        m5_sell_status = "5M SELL SWEEP READY"
    if m5["trend"] == "BEARISH" and (m5["bos"] == "BEARISH BOS" or m5["choch"] == "BEARISH CHOCH"):
        m5_sell_status = "5M SELL ENTRY READY"

    # both 15m sides always visible
    m15_buy_entry = current_price
    m15_buy_sl = last_h1_low
    m15_buy_risk = max(m15_buy_entry - m15_buy_sl, m15["atr"] * 1.2, 1e-9)
    m15_buy_tp1 = m15_buy_entry + m15_buy_risk * 1.0
    m15_buy_tp2 = m15_buy_entry + m15_buy_risk * 1.5
    m15_buy_status = "15M BUY PREPARATION"
    if h1_sweep_buy:
        m15_buy_status = "15M BUY SWEEP READY"
    if m15["trend"] == "BULLISH" and (m15["bos"] == "BULLISH BOS" or m15["choch"] == "BULLISH CHOCH"):
        m15_buy_status = "15M BUY ENTRY READY"

    m15_sell_entry = current_price
    m15_sell_sl = last_h1_high
    m15_sell_risk = max(m15_sell_sl - m15_sell_entry, m15["atr"] * 1.2, 1e-9)
    m15_sell_tp1 = m15_sell_entry - m15_sell_risk * 1.0
    m15_sell_tp2 = m15_sell_entry - m15_sell_risk * 1.5
    m15_sell_status = "15M SELL PREPARATION"
    if h1_sweep_sell:
        m15_sell_status = "15M SELL SWEEP READY"
    if m15["trend"] == "BEARISH" and (m15["bos"] == "BEARISH BOS" or m15["choch"] == "BEARISH CHOCH"):
        m15_sell_status = "15M SELL ENTRY READY"

    buy_score = 0
    sell_score = 0

    # keep daily/h1 checks
    if d1["trend"] == "BULLISH":
        buy_score += 20
        reasons.append("Last Daily trend bullish.")
    elif d1["trend"] == "BEARISH":
        sell_score += 20
        reasons.append("Last Daily trend bearish.")

    if h1["trend"] == "BULLISH":
        buy_score += 25
        reasons.append("Last H1 trend bullish.")
    elif h1["trend"] == "BEARISH":
        sell_score += 25
        reasons.append("Last H1 trend bearish.")

    if h4["trend"] == "BULLISH":
        buy_score += 10
    elif h4["trend"] == "BEARISH":
        sell_score += 10

    if current_price > today_open:
        buy_score += 5
    elif current_price < today_open:
        sell_score += 5

    # zone location
    if buy_zone_low <= current_price <= buy_zone_high:
        buy_score += 18
        reasons.append("Preis ist in/nahe Buy Zone.")
    if sell_zone_low <= current_price <= sell_zone_high:
        sell_score += 18
        reasons.append("Preis ist in/nahe Sell Zone.")

    # fibonacci confluence
    if buy_zone_low <= fib["fib_618"] <= buy_zone_high or buy_zone_low <= fib["fib_786"] <= buy_zone_high:
        buy_score += 10
        reasons.append("Buy Zone + Fibonacci Confluence.")
    if sell_zone_low <= fib["fib_50"] <= sell_zone_high or sell_zone_low <= fib["fib_618"] <= sell_zone_high:
        sell_score += 10
        reasons.append("Sell Zone + Fibonacci Confluence.")

    # FVG / OB
    if buy_fvg:
        buy_score += 8
        reasons.append("Bullish FVG vorhanden.")
    if sell_fvg:
        sell_score += 8
        reasons.append("Bearish FVG vorhanden.")
    if buy_ob:
        buy_score += 8
        reasons.append("Bullish Order Block vorhanden.")
    if sell_ob:
        sell_score += 8
        reasons.append("Bearish Order Block vorhanden.")

    # sweeps
    if h1_sweep_buy or m5_sweep_buy:
        buy_score += 12
        reasons.append("Liquidity sweep unter Low -> Buy Reaction moeglich.")
    if h1_sweep_sell or m5_sweep_sell:
        sell_score += 12
        reasons.append("Liquidity sweep ueber High -> Sell Reaction moeglich.")

    # entry accuracy from lower TF
    if "READY" in m5_buy_status:
        buy_score += 10
    if "READY" in m5_sell_status:
        sell_score += 10
    if "READY" in m15_buy_status:
        buy_score += 7
    if "READY" in m15_sell_status:
        sell_score += 7

    if buy_score > sell_score + 8:
        preferred_side = "BUY"
    elif sell_score > buy_score + 8:
        preferred_side = "SELL"
    else:
        preferred_side = "RANGE / WAIT"

    signal_type = "BOTH ZONES VISIBLE"
    signal_status = "WAIT - WATCH BOTH SIDES"
    zone_low = None
    zone_high = None
    entry_price = None
    sl_price = None
    tp1 = None
    tp2 = None
    tp_medium = None
    tp_large = None

    if preferred_side == "BUY":
        signal_type = "BUY SIDE PREPARATION"
        signal_status = "WATCH BUY ZONE"
        zone_low = buy_zone_low
        zone_high = buy_zone_high
        entry_price = buy_entry
        sl_price = buy_sl
        tp1 = buy_tp1
        tp2 = buy_tp2
        tp_medium = buy_tp_medium
        tp_large = buy_tp_large
        if buy_zone_low <= current_price <= buy_zone_high:
            signal_type = "BUY ZONE ACTIVE"
            signal_status = "WAIT REACTION / CONFIRMATION"
        if "ENTRY READY" in m5_buy_status or "ENTRY READY" in m15_buy_status:
            signal_type = "BUY ENTRY READY"
            signal_status = "ENTRY POSSIBLE"

    elif preferred_side == "SELL":
        signal_type = "SELL SIDE PREPARATION"
        signal_status = "WATCH SELL ZONE"
        zone_low = sell_zone_low
        zone_high = sell_zone_high
        entry_price = sell_entry
        sl_price = sell_sl
        tp1 = sell_tp1
        tp2 = sell_tp2
        tp_medium = sell_tp_medium
        tp_large = sell_tp_large
        if sell_zone_low <= current_price <= sell_zone_high:
            signal_type = "SELL ZONE ACTIVE"
            signal_status = "WAIT REACTION / CONFIRMATION"
        if "ENTRY READY" in m5_sell_status or "ENTRY READY" in m15_sell_status:
            signal_type = "SELL ENTRY READY"
            signal_status = "ENTRY POSSIBLE"

    explanation = " | ".join(reasons)

    return {
        "signal_type": signal_type,
        "signal_status": signal_status,
        "signal_score": max(buy_score, sell_score),
        "preferred_side": preferred_side,

        "prep_price": entry_price,
        "trigger_price": current_price,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp1": tp1,
        "tp2": tp2,
        "tp_medium": tp_medium,
        "tp_large": tp_large,
        "zone_low": zone_low,
        "zone_high": zone_high,

        "last_day_high": last_day_high,
        "last_day_low": last_day_low,
        "last_h1_high": last_h1_high,
        "last_h1_low": last_h1_low,

        "buy_score": buy_score,
        "buy_zone_low": buy_zone_low,
        "buy_zone_high": buy_zone_high,
        "buy_entry": buy_entry,
        "buy_sl": buy_sl,
        "buy_tp1": buy_tp1,
        "buy_tp2": buy_tp2,
        "buy_tp_medium": buy_tp_medium,
        "buy_tp_large": buy_tp_large,

        "sell_score": sell_score,
        "sell_zone_low": sell_zone_low,
        "sell_zone_high": sell_zone_high,
        "sell_entry": sell_entry,
        "sell_sl": sell_sl,
        "sell_tp1": sell_tp1,
        "sell_tp2": sell_tp2,
        "sell_tp_medium": sell_tp_medium,
        "sell_tp_large": sell_tp_large,

        "fib_50": fib["fib_50"],
        "fib_618": fib["fib_618"],
        "fib_786": fib["fib_786"],

        "buy_fvg": f"{format_price(buy_fvg[0])} - {format_price(buy_fvg[1])}" if buy_fvg else "-",
        "sell_fvg": f"{format_price(sell_fvg[0])} - {format_price(sell_fvg[1])}" if sell_fvg else "-",
        "buy_ob": f"{format_price(buy_ob[0])} - {format_price(buy_ob[1])}" if buy_ob else "-",
        "sell_ob": f"{format_price(sell_ob[0])} - {format_price(sell_ob[1])}" if sell_ob else "-",
        "buy_sweep": "YES" if (h1_sweep_buy or m5_sweep_buy) else "NO",
        "sell_sweep": "YES" if (h1_sweep_sell or m5_sweep_sell) else "NO",

        "m5_buy_status": m5_buy_status,
        "m5_buy_entry": m5_buy_entry,
        "m5_buy_sl": m5_buy_sl,
        "m5_buy_tp1": m5_buy_tp1,
        "m5_buy_tp2": m5_buy_tp2,
        "m5_sell_status": m5_sell_status,
        "m5_sell_entry": m5_sell_entry,
        "m5_sell_sl": m5_sell_sl,
        "m5_sell_tp1": m5_sell_tp1,
        "m5_sell_tp2": m5_sell_tp2,

        "m15_buy_status": m15_buy_status,
        "m15_buy_entry": m15_buy_entry,
        "m15_buy_sl": m15_buy_sl,
        "m15_buy_tp1": m15_buy_tp1,
        "m15_buy_tp2": m15_buy_tp2,
        "m15_sell_status": m15_sell_status,
        "m15_sell_entry": m15_sell_entry,
        "m15_sell_sl": m15_sell_sl,
        "m15_sell_tp1": m15_sell_tp1,
        "m15_sell_tp2": m15_sell_tp2,

        "session_name": get_session_context(),
        "news_filter": "Manual check recommended before high-impact news",
        "explanation": explanation,
        "timeframe_note": "D1 + H1 = main direction | 15m + 5m = both-side preparation | Fib + OB + FVG + Sweep = confluence",
    }



def get_latest_signal(market: str, symbol: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM signal_history
        WHERE market = ? AND symbol = ?
        ORDER BY id DESC
        LIMIT 1
    """, (market, symbol))
    row = cur.fetchone()
    conn.close()
    return row


def store_signal_if_changed(market: str, symbol: str, signal):
    latest = get_latest_signal(market, symbol)
    changed = True

    if latest:
        same_type = latest["signal_type"] == signal["signal_type"]
        same_status = latest["signal_status"] == signal["signal_status"]
        score_diff_small = abs(float(latest["signal_score"]) - float(signal["signal_score"])) < 5
        if same_type and same_status and score_diff_small:
            changed = False

    if changed:
        conn = db_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO signal_history (
                market, symbol, signal_type, signal_score, signal_status,
                prep_price, trigger_price, entry_price, sl_price,
                tp1, tp2, tp_medium, tp_large,
                zone_low, zone_high, last_day_high, last_day_low,
                last_h1_high, last_h1_low, explanation, timeframe_note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            market,
            symbol,
            signal["signal_type"],
            signal["signal_score"],
            signal["signal_status"],
            signal["prep_price"],
            signal["trigger_price"],
            signal["entry_price"],
            signal["sl_price"],
            signal["tp1"],
            signal["tp2"],
            signal["tp_medium"],
            signal["tp_large"],
            signal["zone_low"],
            signal["zone_high"],
            signal["last_day_high"],
            signal["last_day_low"],
            signal["last_h1_high"],
            signal["last_h1_low"],
            signal["explanation"],
            signal["timeframe_note"],
            now_iso()
        ))
        conn.commit()
        conn.close()

    return changed


def get_signal_history(market: str, symbol: str, limit: int = 12):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM signal_history
        WHERE market = ? AND symbol = ?
        ORDER BY id DESC
        LIMIT ?
    """, (market, symbol, limit))
    rows = cur.fetchall()
    conn.close()
    return rows



def draw_chart(candles, analysis, signal, symbol: str, market: str):
    width = 1420
    height = 1030
    chart_top = 70
    chart_bottom = 500
    left_pad = 70
    right_pad = 30

    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (11, 14, 20)

    # show fewer candles so bodies stay visible
    view_candles = candles[-80:] if len(candles) > 80 else candles
    highs = [c["high"] for c in view_candles]
    lows = [c["low"] for c in view_candles]

    extra_prices = list(highs + lows)
    for p in [
        signal.get("zone_low"), signal.get("zone_high"),
        signal.get("entry_price"), signal.get("sl_price"),
        signal.get("tp1"), signal.get("tp2"),
        signal.get("tp_medium"), signal.get("tp_large"),
        signal.get("last_day_high"), signal.get("last_day_low"),
        signal.get("last_h1_high"), signal.get("last_h1_low"),
        signal.get("fib_50"), signal.get("fib_618"), signal.get("fib_786"),
        analysis.get("buy_side_liquidity"), analysis.get("sell_side_liquidity"),
        analysis.get("support"), analysis.get("resistance"),
        analysis.get("premium_zone"), analysis.get("discount_zone"),
    ]:
        if p is not None:
            extra_prices.append(p)

    max_price = max(extra_prices)
    min_price = min(extra_prices)
    price_range = max(max_price - min_price, 1e-9)

    def price_to_y(price):
        usable_h = chart_bottom - chart_top
        return int(chart_bottom - ((price - min_price) / price_range) * usable_h)

    n = len(view_candles)
    usable_w = width - left_pad - right_pad
    candle_step = max(usable_w // max(n, 1), 12)
    candle_w = max(6, min(14, candle_step - 3))

    overlay = img.copy()

    y_discount = price_to_y(analysis["discount_zone"])
    y_premium = price_to_y(analysis["premium_zone"])
    cv2.rectangle(overlay, (left_pad, y_premium), (width - right_pad, chart_bottom), (20, 60, 20), -1)
    cv2.rectangle(overlay, (left_pad, chart_top), (width - right_pad, y_discount), (80, 20, 20), -1)

    if signal.get("buy_zone_low") is not None and signal.get("buy_zone_high") is not None:
        zy_top = price_to_y(signal["buy_zone_high"])
        zy_bottom = price_to_y(signal["buy_zone_low"])
        cv2.rectangle(overlay, (left_pad, zy_top), (width - right_pad, zy_bottom), (0, 70, 0), -1)

    if signal.get("sell_zone_low") is not None and signal.get("sell_zone_high") is not None:
        zy_top = price_to_y(signal["sell_zone_high"])
        zy_bottom = price_to_y(signal["sell_zone_low"])
        cv2.rectangle(overlay, (left_pad, zy_top), (width - right_pad, zy_bottom), (70, 0, 0), -1)

    cv2.addWeighted(overlay, 0.12, img, 0.88, 0, img)

    for i in range(7):
        y = chart_top + int((chart_bottom - chart_top) * i / 6)
        cv2.line(img, (left_pad, y), (width - right_pad, y), (45, 50, 60), 1)

    # real candles
    for i, c in enumerate(view_candles):
        x = left_pad + i * candle_step + candle_step // 2
        y_open = price_to_y(c["open"])
        y_close = price_to_y(c["close"])
        y_high = price_to_y(c["high"])
        y_low = price_to_y(c["low"])

        bullish = c["close"] >= c["open"]
        color = (0, 200, 120) if bullish else (0, 70, 255)

        cv2.line(img, (x, y_high), (x, y_low), color, 1)
        top = min(y_open, y_close)
        bottom = max(y_open, y_close)
        if bottom - top < 4:
            bottom = top + 4
        cv2.rectangle(img, (x - candle_w // 2, top), (x + candle_w // 2, bottom), color, -1)

    levels = [
        ("LAST D HIGH", signal.get("last_day_high"), (255, 255, 255)),
        ("LAST D LOW", signal.get("last_day_low"), (220, 220, 220)),
        ("LAST H1 HIGH", signal.get("last_h1_high"), (255, 170, 170)),
        ("LAST H1 LOW", signal.get("last_h1_low"), (170, 220, 255)),
        ("FIB 0.5", signal.get("fib_50"), (255, 220, 120)),
        ("FIB 0.618", signal.get("fib_618"), (255, 200, 80)),
        ("FIB 0.786", signal.get("fib_786"), (255, 180, 40)),
        ("BSL", analysis.get("buy_side_liquidity"), (255, 120, 0)),
        ("SSL", analysis.get("sell_side_liquidity"), (180, 0, 255)),
        ("SUPPORT", analysis.get("support"), (120, 200, 255)),
        ("RESIST", analysis.get("resistance"), (255, 80, 80)),
        ("PREMIUM", analysis.get("premium_zone"), (160, 120, 255)),
        ("DISCOUNT", analysis.get("discount_zone"), (80, 255, 180)),
    ]

    if signal.get("entry_price") is not None:
        levels.append(("ENTRY", signal["entry_price"], (0, 255, 0)))
    if signal.get("sl_price") is not None:
        levels.append(("SL", signal["sl_price"], (0, 0, 255)))
    if signal.get("tp1") is not None:
        levels.append(("TP1", signal["tp1"], (0, 255, 255)))
    if signal.get("tp2") is not None:
        levels.append(("TP2", signal["tp2"], (255, 220, 0)))
    if signal.get("tp_medium") is not None:
        levels.append(("TP MED", signal["tp_medium"], (255, 180, 0)))
    if signal.get("tp_large") is not None:
        levels.append(("TP LARGE", signal["tp_large"], (255, 140, 0)))

    for label, price, color in levels:
        if price is None:
            continue
        y = price_to_y(price)
        cv2.line(img, (left_pad, y), (width - right_pad, y), color, 1)
        cv2.putText(img, f"{label}: {format_price(price)}", (left_pad + 10, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    cv2.putText(
        img,
        f"{market.upper()} | {symbol.upper()} | Signal: {signal.get('signal_type', '')} | Trend M5: {analysis.get('trend', '')} | BOS: {analysis.get('bos', '')} | CHOCH: {analysis.get('choch', '')}",
        (25, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (255, 255, 255),
        2
    )

    cv2.rectangle(img, (0, 540), (width, height), (20, 24, 30), -1)
    cv2.line(img, (0, 540), (width, 540), (0, 255, 120), 2)

    info_lines = [
        f"Signal: {signal.get('signal_type', '-')} | Status: {signal.get('signal_status', '-')}",
        f"Buy Zone: {format_price(signal.get('buy_zone_low'))} - {format_price(signal.get('buy_zone_high'))}",
        f"Sell Zone: {format_price(signal.get('sell_zone_low'))} - {format_price(signal.get('sell_zone_high'))}",
        f"Entry: {format_price(signal.get('entry_price'))} | SL: {format_price(signal.get('sl_price'))}",
        f"TP1: {format_price(signal.get('tp1'))} | TP2: {format_price(signal.get('tp2'))}",
        f"TP Medium: {format_price(signal.get('tp_medium'))} | TP Large: {format_price(signal.get('tp_large'))}",
        f"Fib 0.5 / 0.618 / 0.786: {format_price(signal.get('fib_50'))} / {format_price(signal.get('fib_618'))} / {format_price(signal.get('fib_786'))}",
        f"Last D High/Low: {format_price(signal.get('last_day_high'))} / {format_price(signal.get('last_day_low'))}",
        f"Last H1 High/Low: {format_price(signal.get('last_h1_high'))} / {format_price(signal.get('last_h1_low'))}",
        f"Trend: {analysis.get('trend')} | BOS: {analysis.get('bos')} | CHOCH: {analysis.get('choch')}",
        f"Liquidity: {format_price(analysis.get('buy_side_liquidity'))} / {format_price(analysis.get('sell_side_liquidity'))}",
        f"Support / Resistance: {format_price(analysis.get('support'))} / {format_price(analysis.get('resistance'))}",
        f"FVG: {analysis.get('fvg_text', '-')}",
    ]

    y = 575
    for line in info_lines:
        cv2.putText(img, line[:155], (25, y), cv2.FONT_HERSHEY_SIMPLEX, 0.53, (235, 235, 235), 1)
        y += 24

    return img




def safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=8)
    except Exception:
        pass


def build_alert_type_and_severity(signal: dict):
    signal_type = signal.get("signal_type", "")
    score = safe_float(signal.get("signal_score")) or 0

    if signal_type in ["BUY ENTRY READY", "BUY 5M SETUP"] and score >= 55:
        return "BUY_SETUP_READY", "high"
    if signal_type in ["SELL ENTRY READY", "SELL 5M SETUP"] and score >= 55:
        return "SELL_SETUP_READY", "high"
    if signal_type == "BUY ZONE ACTIVE" and score >= 45:
        return "BUY_ZONE_ACTIVE", "medium"
    if signal_type == "SELL ZONE ACTIVE" and score >= 45:
        return "SELL_ZONE_ACTIVE", "medium"
    if signal_type in ["BUY SIDE PREPARATION", "SELL SIDE PREPARATION", "BOTH ZONES VISIBLE"] and score >= 35:
        return "MARKET_PREPARATION", "low"
    return None, None


def build_alert_message(market: str, symbol: str, signal: dict, alert_type: str):
    preferred = signal.get("preferred_side", "-")
    entry = format_price(signal.get("entry_price"))
    sl = format_price(signal.get("sl_price"))
    tp1 = format_price(signal.get("tp1"))
    tp2 = format_price(signal.get("tp2"))
    tp_medium = format_price(signal.get("tp_medium"))
    tp_large = format_price(signal.get("tp_large"))
    buy_zone = f"{format_price(signal.get('buy_zone_low'))} - {format_price(signal.get('buy_zone_high'))}"
    sell_zone = f"{format_price(signal.get('sell_zone_low'))} - {format_price(signal.get('sell_zone_high'))}"
    score = signal.get("signal_score", 0)

    if alert_type == "BUY_SETUP_READY":
        title = "🚀 BUY SETUP READY"
    elif alert_type == "SELL_SETUP_READY":
        title = "🔥 SELL SETUP READY"
    elif alert_type == "BUY_ZONE_ACTIVE":
        title = "⚠️ BUY ZONE ACTIVE"
    elif alert_type == "SELL_ZONE_ACTIVE":
        title = "⚠️ SELL ZONE ACTIVE"
    else:
        title = "🧭 MARKET PREPARATION"

    return (
        f"{title}\n"
        f"Market: {market.upper()} | Symbol: {symbol}\n"
        f"Signal: {signal.get('signal_type', '-')}\n"
        f"Preferred: {preferred} | Score: {score}\n"
        f"Buy Zone: {buy_zone}\n"
        f"Sell Zone: {sell_zone}\n"
        f"Entry: {entry}\n"
        f"SL: {sl}\n"
        f"TP1 / TP2: {tp1} / {tp2}\n"
        f"TP M / L: {tp_medium} / {tp_large}"
    )


def store_alert_if_new(market: str, symbol: str, signal: dict):
    alert_type, severity = build_alert_type_and_severity(signal)
    if not alert_type:
        return None

    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM alert_history
        WHERE market = ? AND symbol = ?
        ORDER BY id DESC
        LIMIT 1
    """, (market, symbol))
    latest = cur.fetchone()

    changed = True
    if latest:
        same_type = latest["alert_type"] == alert_type
        same_signal = latest["signal_type"] == signal.get("signal_type")
        same_status = latest["signal_status"] == signal.get("signal_status")
        score_diff_small = abs(float(latest["signal_score"]) - float(signal.get("signal_score", 0))) < 4
        if same_type and same_signal and same_status and score_diff_small:
            changed = False

    if not changed:
        conn.close()
        return None

    message = build_alert_message(market, symbol, signal, alert_type)
    cur.execute("""
        INSERT INTO alert_history (
            market, symbol, alert_type, severity, signal_type, signal_status, signal_score,
            entry_price, sl_price, tp1, tp2, tp_medium, tp_large, message, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market, symbol, alert_type, severity, signal.get("signal_type", "-"), signal.get("signal_status", "-"),
        signal.get("signal_score", 0), signal.get("entry_price"), signal.get("sl_price"),
        signal.get("tp1"), signal.get("tp2"), signal.get("tp_medium"), signal.get("tp_large"),
        message, now_iso()
    ))
    conn.commit()
    conn.close()
    return {"alert_type": alert_type, "severity": severity, "message": message}


def maybe_send_telegram_alert(market: str, symbol: str, alert_obj):
    if not alert_obj:
        return
    if symbol.strip().upper() not in ["BTCUSDT", "XAU/USD", "XAUUSD"]:
        return

    key = f"{market}:{symbol}:{alert_obj['alert_type']}"
    now = time.time()
    last_sent = LAST_TELEGRAM_ALERTS.get(key, 0)
    if now - last_sent < TELEGRAM_ALERT_COOLDOWN:
        return

    send_telegram_message(alert_obj["message"])
    LAST_TELEGRAM_ALERTS[key] = now


def get_alert_history(limit: int = 20):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM alert_history
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def alert_scan_loop():
    while True:
        try:
            for market, symbol in ALERT_SYMBOLS:
                try:
                    mtf = get_multi_timeframe_analysis(market, symbol)
                    signal = evaluate_signal_engine(mtf)
                    store_signal_if_changed(market, symbol, signal)
                    alert_obj = store_alert_if_new(market, symbol, signal)
                    maybe_send_telegram_alert(market, symbol, alert_obj)
                except Exception:
                    pass
            time.sleep(ALERT_SCAN_SECONDS)
        except Exception:
            time.sleep(ALERT_SCAN_SECONDS)


def ensure_alert_thread():
    global ALERT_THREAD_STARTED
    if ALERT_THREAD_STARTED:
        return
    t = threading.Thread(target=alert_scan_loop, daemon=True)
    t.start()
    ALERT_THREAD_STARTED = True


@app.get("/login", response_class=HTMLResponse)
def login_page(lang: str = "de", error: str = "", msg: str = ""):
    ensure_alert_thread()
    error_html = f'<div class="banner banner-error">{error}</div>' if error else ""
    msg_html = f'<div class="banner banner-success">{msg}</div>' if msg else ""

    body = f"""
    {topbar(lang)}

    <div class="login-wrap">
        <div class="card">
            <h1>{tr(lang, "Login", "Login")}</h1>
            {error_html}
            {msg_html}
            <form method="post" action="/login">
                <input type="hidden" name="lang" value="{lang}">
                <div class="form-row">
                    <label>{tr(lang, "Benutzername", "Username")}</label>
                    <input name="username">
                </div>
                <div class="form-row">
                    <label>{tr(lang, "Passwort", "Password")}</label>
                    <input type="password" name="password">
                </div>
                <button class="btn" type="submit">{tr(lang, "Einloggen", "Log in")}</button>
            </form>

            <div style="height:14px;"></div>
            <a class="btn btn-secondary" href="/request-access?lang={lang}">{tr(lang, "Zugang anfragen", "Request access")}</a>

            <div class="footer-note">
                Admin: admin / admin123<br>
                User: user / user123
            </div>
        </div>
    </div>
    """
    return page("Login", body)


@app.post("/login")
def login_submit(username: str = Form(...), password: str = Form(...), lang: str = Form("de")):
    user = get_user(username)
    if not user or user["password"] != password or int(user["active"]) != 1:
        return RedirectResponse(
            url=f"/login?lang={lang}&error={tr(lang, 'Login fehlgeschlagen', 'Login failed')}",
            status_code=303
        )
    token = create_session(username)
    response = RedirectResponse(url=f"/?lang={lang}", status_code=303)
    response.set_cookie("session_token", token, httponly=True)
    return response


@app.get("/logout")
def logout(lang: str = "de", request: Request = None):
    if request:
        token = request.cookies.get("session_token")
        if token:
            delete_session(token)
    response = RedirectResponse(url=f"/login?lang={lang}", status_code=303)
    response.delete_cookie("session_token")
    return response


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, lang: str = "de", msg: str = ""):
    user = require_login(request)
    if not user:
        return RedirectResponse(url=f"/login?lang={lang}", status_code=303)

    msg_html = f'<div class="banner banner-success">{msg}</div>' if msg else ""
    body = f"""
    {topbar(lang, user, True, user['role'] == 'admin')}
    <div class="card">
        <a class="chip" href="/?lang={lang}">⬅ {tr(lang, "Zurueck", "Back")}</a>
        <h1 style="margin-top:18px;">{tr(lang, "Profil", "Profile")}</h1>
        {msg_html}

        <div class="info-list">
            <div class="info-item"><div class="info-label">{tr(lang, "Benutzername", "Username")}</div><div class="info-value">{user['username']}</div></div>
            <div class="info-item"><div class="info-label">Email</div><div class="info-value">{user['email'] or ''}</div></div>
            <div class="info-item"><div class="info-label">{tr(lang, "Rolle", "Role")}</div><div class="info-value">{user['role']}</div></div>
            <div class="info-item"><div class="info-label">Status</div><div class="info-value">active</div></div>
        </div>

        <div class="section-title">{tr(lang, "Email aendern", "Change email")}</div>
        <form method="post" action="/profile/update-email">
            <input type="hidden" name="lang" value="{lang}">
            <div class="form-row">
                <label>Email</label>
                <input name="email" value="{user['email'] or ''}">
            </div>
            <button class="btn" type="submit">{tr(lang, "Email speichern", "Save email")}</button>
        </form>

        <div class="section-title">{tr(lang, "Passwort aendern", "Change password")}</div>
        <form method="post" action="/profile/change-password">
            <input type="hidden" name="lang" value="{lang}">
            <div class="form-row">
                <label>{tr(lang, "Altes Passwort", "Old password")}</label>
                <input type="password" name="old_password">
            </div>
            <div class="form-row">
                <label>{tr(lang, "Neues Passwort", "New password")}</label>
                <input type="password" name="new_password">
            </div>
            <button class="btn" type="submit">{tr(lang, "Passwort speichern", "Save password")}</button>
        </form>
    </div>
    """
    return page("Profile", body)


@app.post("/profile/update-email")
def update_email(request: Request, email: str = Form(...), lang: str = Form("de")):
    user = require_login(request)
    if not user:
        return RedirectResponse(url=f"/login?lang={lang}", status_code=303)
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET email = ? WHERE username = ?", (email.strip(), user["username"]))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/profile?lang={lang}&msg={tr(lang, 'Email gespeichert', 'Email saved')}", status_code=303)


@app.post("/profile/change-password")
def change_password(request: Request, old_password: str = Form(...), new_password: str = Form(...), lang: str = Form("de")):
    user = require_login(request)
    if not user:
        return RedirectResponse(url=f"/login?lang={lang}", status_code=303)
    db_user = get_user(user["username"])
    if not db_user or db_user["password"] != old_password:
        return RedirectResponse(url=f"/profile?lang={lang}&msg={tr(lang, 'Altes Passwort falsch', 'Old password wrong')}", status_code=303)
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password = ? WHERE username = ?", (new_password.strip(), user["username"]))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/profile?lang={lang}&msg={tr(lang, 'Passwort geaendert', 'Password changed')}", status_code=303)


@app.get("/request-access", response_class=HTMLResponse)
def request_access_page(lang: str = "de", msg: str = ""):
    msg_html = f'<div class="banner banner-success">{msg}</div>' if msg else ""
    body = f"""
    {topbar(lang)}
    <div class="login-wrap" style="max-width:700px;">
        <div class="card">
            <a class="chip" href="/login?lang={lang}">⬅ {tr(lang, "Zurueck zum Login", "Back to login")}</a>
            <h1 style="margin-top:18px;">{tr(lang, "Zugang anfragen", "Request access")}</h1>
            {msg_html}
            <form method="post" action="/request-access">
                <input type="hidden" name="lang" value="{lang}">
                <div class="form-row"><label>{tr(lang, "Name", "Name")}</label><input name="name"></div>
                <div class="form-row"><label>Email</label><input name="email"></div>
                <div class="form-row"><label>{tr(lang, "Gewuenschter Benutzername", "Desired username")}</label><input name="desired_username"></div>
                <div class="form-row"><label>{tr(lang, "Nachricht", "Message")}</label><textarea name="message"></textarea></div>
                <button class="btn" type="submit">{tr(lang, "Anfrage senden", "Send request")}</button>
            </form>
        </div>
    </div>
    """
    return page("Request Access", body)


@app.post("/request-access")
def request_access_submit(name: str = Form(...), email: str = Form(...), desired_username: str = Form(...), message: str = Form(""), lang: str = Form("de")):
    if not name.strip() or not email.strip() or not desired_username.strip():
        return RedirectResponse(url=f"/request-access?lang={lang}&msg={tr(lang, 'Bitte alle Pflichtfelder ausfuellen', 'Please fill all required fields')}", status_code=303)

    conn = db_conn()
    cur = conn.cursor()
    req_id = str(uuid.uuid4())[:8]
    cur.execute("""
        INSERT INTO access_requests (
            id, name, email, desired_username, message, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (req_id, name.strip(), email.strip(), desired_username.strip(), message.strip(), "pending", now_iso()))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/login?lang={lang}&msg={tr(lang, 'Anfrage gesendet', 'Request sent')}", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, lang: str = "de", msg: str = ""):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url=f"/login?lang={lang}", status_code=303)

    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY id ASC")
    users = cur.fetchall()
    cur.execute("SELECT * FROM access_requests ORDER BY created_at DESC")
    reqs = cur.fetchall()
    conn.close()

    msg_html = f'<div class="banner banner-success">{msg}</div>' if msg else ""

    user_rows = ""
    for u in users:
        if u["username"] == admin["username"]:
            actions = "<span class='muted'>current admin</span>"
        else:
            actions = f"""
            <form method="post" action="/admin/toggle-user" style="display:inline;">
                <input type="hidden" name="lang" value="{lang}">
                <input type="hidden" name="username" value="{u['username']}">
                <button class="btn btn-warning" type="submit">{tr(lang, "Sperren/Freigeben", "Block/Allow")}</button>
            </form>
            <form method="post" action="/admin/delete-user" style="display:inline; margin-left:8px;">
                <input type="hidden" name="lang" value="{lang}">
                <input type="hidden" name="username" value="{u['username']}">
                <button class="btn btn-danger" type="submit">{tr(lang, "Loeschen", "Delete")}</button>
            </form>
            """
        user_rows += f"""
        <tr>
            <td>{u['username']}</td>
            <td>{u['email'] or ''}</td>
            <td>{u['role']}</td>
            <td>{'active' if int(u['active']) == 1 else 'inactive'}</td>
            <td>{actions}</td>
        </tr>
        """

    req_rows = ""
    for r in reqs:
        if r["status"] == "pending":
            actions = f"""
            <form method="post" action="/admin/approve-request" style="display:inline;">
                <input type="hidden" name="lang" value="{lang}">
                <input type="hidden" name="request_id" value="{r['id']}">
                <button class="btn" type="submit">{tr(lang, "Freigeben", "Approve")}</button>
            </form>
            <form method="post" action="/admin/reject-request" style="display:inline; margin-left:8px;">
                <input type="hidden" name="lang" value="{lang}">
                <input type="hidden" name="request_id" value="{r['id']}">
                <button class="btn btn-danger" type="submit">{tr(lang, "Ablehnen", "Reject")}</button>
            </form>
            """
        else:
            actions = "<span class='muted'>done</span>"

        req_rows += f"""
        <tr>
            <td>{r['name']}</td>
            <td>{r['email']}</td>
            <td>{r['desired_username']}</td>
            <td>{r['message'] or ''}</td>
            <td>{r['status']}</td>
            <td>{r['created_username'] or ''}</td>
            <td>{r['created_password'] or ''}</td>
            <td>{actions}</td>
        </tr>
        """

    body = f"""
    {topbar(lang, admin, True, True)}
    <div class="card">
        <a class="chip" href="/?lang={lang}">⬅ {tr(lang, "Zurueck", "Back")}</a>
        <h1 style="margin-top:18px;">Admin</h1>
        {msg_html}

        <div class="section-title">{tr(lang, "Anfrage History", "Request history")}</div>
        <table>
            <tr><th>Name</th><th>Email</th><th>Desired Username</th><th>Message</th><th>Status</th><th>Created User</th><th>Password</th><th>Action</th></tr>
            {req_rows if req_rows else "<tr><td colspan='8'>Keine Requests</td></tr>"}
        </table>

        <div class="section-title">{tr(lang, "Aktive Nutzer", "Active users")}</div>
        <table>
            <tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Action</th></tr>
            {user_rows}
        </table>
    </div>
    """
    return page("Admin", body)


@app.post("/admin/approve-request")
def admin_approve_request(request: Request, request_id: str = Form(...), lang: str = Form("de")):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url=f"/login?lang={lang}", status_code=303)

    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM access_requests WHERE id = ?", (request_id,))
    r = cur.fetchone()
    if not r or r["status"] != "pending":
        conn.close()
        return RedirectResponse(url=f"/admin?lang={lang}&msg={tr(lang, 'Anfrage nicht gefunden', 'Request not found')}", status_code=303)

    username = r["desired_username"]
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    exists = cur.fetchone()
    if exists:
        username = f"{username}_{r['id']}"

    password = generate_password()
    cur.execute("""
        INSERT INTO users (username, email, password, role, active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (username, r["email"], password, "user", 1, now_iso()))

    cur.execute("""
        UPDATE access_requests
        SET status = ?, created_username = ?, created_password = ?, decided_at = ?
        WHERE id = ?
    """, ("approved", username, password, now_iso(), request_id))

    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin?lang={lang}&msg=User erstellt", status_code=303)


@app.post("/admin/reject-request")
def admin_reject_request(request: Request, request_id: str = Form(...), lang: str = Form("de")):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url=f"/login?lang={lang}", status_code=303)
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE access_requests SET status = ?, decided_at = ? WHERE id = ?", ("rejected", now_iso(), request_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin?lang={lang}&msg=Request abgelehnt", status_code=303)


@app.post("/admin/toggle-user")
def admin_toggle_user(request: Request, username: str = Form(...), lang: str = Form("de")):
    admin = require_admin(request)
    if not admin or username == admin["username"]:
        return RedirectResponse(url=f"/admin?lang={lang}", status_code=303)
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cur.fetchone()
    if user:
        new_active = 0 if int(user["active"]) == 1 else 1
        cur.execute("UPDATE users SET active = ? WHERE username = ?", (new_active, username))
        if new_active == 0:
            cur.execute("DELETE FROM sessions WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin?lang={lang}&msg=Status geaendert", status_code=303)


@app.post("/admin/delete-user")
def admin_delete_user(request: Request, username: str = Form(...), lang: str = Form("de")):
    admin = require_admin(request)
    if not admin or username == admin["username"]:
        return RedirectResponse(url=f"/admin?lang={lang}", status_code=303)
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username = ?", (username,))
    cur.execute("DELETE FROM sessions WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin?lang={lang}&msg=User geloescht", status_code=303)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, lang: str = "de"):
    ensure_alert_thread()
    user = require_login(request)
    if not user:
        return RedirectResponse(url=f"/login?lang={lang}", status_code=303)

    body = f"""
    {topbar(lang, user, True, user['role'] == 'admin')}

    <div class="hero">
        <div class="hero-title">{tr(lang, "Trading Mentor Dashboard", "Trading Mentor Dashboard")}</div>
        <div class="hero-sub">
            {tr(lang,
                "Jetzt gilt: Buy SL = letztes H1 Low, Sell SL = letztes H1 High. TP1/TP2 = 5m, TP mittel = letztes H1 High/Low, TP gross = letztes Daily High/Low.",
                "Now: Buy SL = last H1 low, Sell SL = last H1 high. TP1/TP2 = 5m, TP medium = last H1 high/low, TP large = last daily high/low."
            )}
        </div>
    </div>

    <div class="grid grid-2">
        <div class="card">
            <h2>Crypto</h2>
            <form action="/analyze" method="get">
                <input type="hidden" name="market" value="crypto">
                <input type="hidden" name="lang" value="{lang}">
                <div class="form-row">
                    <label>Symbol</label>
                    <input name="symbol" value="BTCUSDT">
                </div>
                <button class="btn" type="submit">{tr(lang, "Crypto analysieren", "Analyze crypto")}</button>
            </form>
            <div class="footer-note">BTCUSDT, ETHUSDT, SOLUSDT</div>
        </div>

        <div class="card">
            <h2>Forex / Gold</h2>
            <form action="/analyze" method="get">
                <input type="hidden" name="market" value="forex">
                <input type="hidden" name="lang" value="{lang}">
                <div class="form-row">
                    <label>Symbol</label>
                    <input name="symbol" value="XAU/USD">
                </div>
                <button class="btn" type="submit">{tr(lang, "Forex / Gold analysieren", "Analyze forex / gold")}</button>
            </form>
            <div class="footer-note">EUR/USD, GBP/USD, USD/JPY, XAU/USD</div>
        </div>
    </div>
    """
    return page("Home", body)


@app.get("/analyze", response_class=HTMLResponse)
def analyze(request: Request, market: str, symbol: str, lang: str = "de"):
    ensure_alert_thread()
    user = require_login(request)
    if not user:
        return RedirectResponse(url=f"/login?lang={lang}", status_code=303)

    try:
        market = market.strip().lower()
        symbol = symbol.strip()
        if market not in ["crypto", "forex"]:
            raise ValueError("Ungueltiger Markt")

        mtf = get_multi_timeframe_analysis(market, symbol)
        overall_bias, move_size = combine_bias(mtf)

        m5 = mtf["M5"]["analysis"]
        h1 = mtf["H1"]["analysis"]
        h4 = mtf["H4"]["analysis"]
        d1 = mtf["D1"]["analysis"]
        daily_info = mtf["daily_info"]

        signal = evaluate_signal_engine(mtf)
        changed = store_signal_if_changed(market, symbol, signal)
        alert_obj = store_alert_if_new(market, symbol, signal)
        maybe_send_telegram_alert(market, symbol, alert_obj)
        history = get_signal_history(market, symbol, limit=12)
        alert_history_rows = get_alert_history(limit=20)

        chart = draw_chart(mtf["M5"]["candles"], m5, signal, symbol, market)
        img_b64 = to_base64_png(chart)

        sig = signal["signal_type"]
        if sig == "BUY 5M SETUP":
            signal_banner = f'<div class="banner banner-success">🟢 BUY 5M SETUP | Entry: {format_price(signal["entry_price"])} | SL: {format_price(signal["sl_price"])} | TP1: {format_price(signal["tp1"])} | TP2: {format_price(signal["tp2"])} | TP MED: {format_price(signal["tp_medium"])} | TP LARGE: {format_price(signal["tp_large"])}</div>'
        elif sig == "SELL 5M SETUP":
            signal_banner = f'<div class="banner banner-error">🔴 SELL 5M SETUP | Entry: {format_price(signal["entry_price"])} | SL: {format_price(signal["sl_price"])} | TP1: {format_price(signal["tp1"])} | TP2: {format_price(signal["tp2"])} | TP MED: {format_price(signal["tp_medium"])} | TP LARGE: {format_price(signal["tp_large"])}</div>'
        elif "BUY ZONE" in sig:
            signal_banner = f'<div class="banner banner-success">🟢 {sig} | Zone: {format_price(signal["zone_low"])} - {format_price(signal["zone_high"])} | Last H1 Low SL: {format_price(signal["last_h1_low"])}</div>'
        elif "SELL ZONE" in sig:
            signal_banner = f'<div class="banner banner-error">🔴 {sig} | Zone: {format_price(signal["zone_low"])} - {format_price(signal["zone_high"])} | Last H1 High SL: {format_price(signal["last_h1_high"])}</div>'
        else:
            signal_banner = f'<div class="banner banner-blue">📊 BOTH ZONES VISIBLE | Preferred: {signal["preferred_side"]} | Buy Zone: {format_price(signal["buy_zone_low"])} - {format_price(signal["buy_zone_high"])} | Sell Zone: {format_price(signal["sell_zone_low"])} - {format_price(signal["sell_zone_high"])} </div>'

        if changed:
            signal_banner += '<div class="banner banner-blue">📌 Neues Signal-Update gespeichert.</div>'
        if alert_obj:
            signal_banner += f'<div class="banner banner-success">🔔 ALERT: {alert_obj["alert_type"]} | {alert_obj["severity"].upper()}</div>'

        history_rows = ""
        for row in history:
            history_rows += f"""
            <tr>
                <td>{row['created_at'][:19].replace('T', ' ')}</td>
                <td>{row['signal_type']}</td>
                <td>{row['signal_status']}</td>
                <td>{row['signal_score']:.0f}</td>
                <td>{format_price(row['zone_low'])}</td>
                <td>{format_price(row['zone_high'])}</td>
                <td>{format_price(row['entry_price'])}</td>
                <td>{format_price(row['sl_price'])}</td>
                <td>{format_price(row['tp1'])}</td>
                <td>{format_price(row['tp2'])}</td>
                <td>{format_price(row['tp_medium'])}</td>
                <td>{format_price(row['tp_large'])}</td>
            </tr>
            """


        alert_table_rows = ""
        for a in alert_history_rows:
            alert_table_rows += f"""
            <tr>
                <td>{a['created_at'][:19].replace('T', ' ')}</td>
                <td>{a['market'].upper()}</td>
                <td>{a['symbol']}</td>
                <td>{a['alert_type']}</td>
                <td>{a['severity']}</td>
                <td>{a['signal_type']}</td>
                <td>{a['signal_status']}</td>
                <td>{a['signal_score']:.0f}</td>
                <td>{format_price(a['entry_price'])}</td>
                <td>{format_price(a['sl_price'])}</td>
                <td>{format_price(a['tp1'])}</td>
                <td>{format_price(a['tp2'])}</td>
            </tr>
            """
        body = f"""
        {topbar(lang, user, True, user['role'] == 'admin')}

        <a class="chip" href="/?lang={lang}">⬅ {tr(lang, "Zurueck zur Startseite", "Back to home")}</a>

        <div class="hero" style="margin-top:18px;">
            <div class="hero-title">{symbol.upper()} - {market.upper()}</div>
            <div class="hero-sub">
                {tr(lang,
                    "Korrigierte Logik: Buy SL = letztes H1 Low, Sell SL = letztes H1 High. TP1/TP2 kommen aus 5m, TP mittel aus letztem H1 High/Low, TP gross aus letztem Daily High/Low.",
                    "Corrected logic: Buy SL = last H1 low, Sell SL = last H1 high. TP1/TP2 come from 5m, TP medium from last H1 high/low, TP large from last daily high/low."
                )}
            </div>
        </div>

        {signal_banner}

        <div class="grid grid-main">
            <div class="card">
                <div class="section-title">Market Chart</div>
                <div class="image-frame">
                    <img src="data:image/png;base64,{img_b64}" alt="Market Chart" style="width:100%; height:auto; display:block;">
                </div>

                <div class="section-title">Signal Center</div>
                <div class="info-list">
                    <div class="info-item"><div class="info-label">Signal</div><div class="info-value">{signal['signal_type']}</div></div>
                    <div class="info-item"><div class="info-label">Status</div><div class="info-value">{signal['signal_status']}</div></div>
                    <div class="info-item"><div class="info-label">Score</div><div class="info-value">{signal['signal_score']:.0f}</div></div>
                    <div class="info-item"><div class="info-label">Zone Low</div><div class="info-value">{format_price(signal['zone_low'])}</div></div>
                    <div class="info-item"><div class="info-label">Zone High</div><div class="info-value">{format_price(signal['zone_high'])}</div></div>
                    <div class="info-item"><div class="info-label">Entry</div><div class="info-value">{format_price(signal['entry_price'])}</div></div>
                    <div class="info-item"><div class="info-label">SL</div><div class="info-value">{format_price(signal['sl_price'])}</div></div>
                    <div class="info-item"><div class="info-label">TP1</div><div class="info-value">{format_price(signal['tp1'])}</div></div>
                    <div class="info-item"><div class="info-label">TP2</div><div class="info-value">{format_price(signal['tp2'])}</div></div>
                    <div class="info-item"><div class="info-label">TP Medium</div><div class="info-value">{format_price(signal['tp_medium'])}</div></div>
                    <div class="info-item"><div class="info-label">TP Large</div><div class="info-value">{format_price(signal['tp_large'])}</div></div>
                    <div class="info-item"><div class="info-label">Last D High</div><div class="info-value">{format_price(signal['last_day_high'])}</div></div>
                    <div class="info-item"><div class="info-label">Last D Low</div><div class="info-value">{format_price(signal['last_day_low'])}</div></div>
                    <div class="info-item"><div class="info-label">Last H1 High</div><div class="info-value">{format_price(signal['last_h1_high'])}</div></div>
                    <div class="info-item"><div class="info-label">Last H1 Low</div><div class="info-value">{format_price(signal['last_h1_low'])}</div></div>
                </div>

                
                
                <div class="section-title">Fibonacci Levels</div>
                <div class="info-list">
                    <div class="info-item"><div class="info-label">Fib 0.5</div><div class="info-value">{format_price(signal['fib_50'])}</div></div>
                    <div class="info-item"><div class="info-label">Fib 0.618</div><div class="info-value">{format_price(signal['fib_618'])}</div></div>
                    <div class="info-item"><div class="info-label">Fib 0.786</div><div class="info-value">{format_price(signal['fib_786'])}</div></div>
                    <div class="info-item"><div class="info-label">Based On</div><div class="info-value">Last H1 High / Last H1 Low</div></div>
                </div>

<div class="section-title">Smart Money Confluence / Fibonacci</div>
                <div class="info-list">
                    <div class="info-item"><div class="info-label">Preferred Side</div><div class="info-value">{signal['preferred_side']}</div></div>
                    <div class="info-item"><div class="info-label">Session</div><div class="info-value">{signal['session_name']}</div></div>
                    <div class="info-item"><div class="info-label">Fib 0.5</div><div class="info-value">{format_price(signal['fib_50'])}</div></div>
                    <div class="info-item"><div class="info-label">Fib 0.618</div><div class="info-value">{format_price(signal['fib_618'])}</div></div>
                    <div class="info-item"><div class="info-label">Fib 0.786</div><div class="info-value">{format_price(signal['fib_786'])}</div></div>
                    <div class="info-item"><div class="info-label">News Filter</div><div class="info-value">{signal['news_filter']}</div></div>
                    <div class="info-item"><div class="info-label">BUY FVG</div><div class="info-value">{signal['buy_fvg']}</div></div>
                    <div class="info-item"><div class="info-label">SELL FVG</div><div class="info-value">{signal['sell_fvg']}</div></div>
                    <div class="info-item"><div class="info-label">BUY Order Block</div><div class="info-value">{signal['buy_ob']}</div></div>
                    <div class="info-item"><div class="info-label">SELL Order Block</div><div class="info-value">{signal['sell_ob']}</div></div>
                    <div class="info-item"><div class="info-label">BUY Sweep</div><div class="info-value">{signal['buy_sweep']}</div></div>
                    <div class="info-item"><div class="info-label">SELL Sweep</div><div class="info-value">{signal['sell_sweep']}</div></div>
                </div>

                <div class="section-title">Both Sides Entry Preparation</div>
                <div class="info-list">
                    <div class="info-item"><div class="info-label">BUY Zone</div><div class="info-value">{format_price(signal['buy_zone_low'])} - {format_price(signal['buy_zone_high'])}</div></div>
                    <div class="info-item"><div class="info-label">SELL Zone</div><div class="info-value">{format_price(signal['sell_zone_low'])} - {format_price(signal['sell_zone_high'])}</div></div>
                    <div class="info-item"><div class="info-label">BUY Entry / SL</div><div class="info-value">{format_price(signal['buy_entry'])} / {format_price(signal['buy_sl'])}</div></div>
                    <div class="info-item"><div class="info-label">SELL Entry / SL</div><div class="info-value">{format_price(signal['sell_entry'])} / {format_price(signal['sell_sl'])}</div></div>
                    <div class="info-item"><div class="info-label">BUY TP1 / TP2</div><div class="info-value">{format_price(signal['buy_tp1'])} / {format_price(signal['buy_tp2'])}</div></div>
                    <div class="info-item"><div class="info-label">SELL TP1 / TP2</div><div class="info-value">{format_price(signal['sell_tp1'])} / {format_price(signal['sell_tp2'])}</div></div>
                    <div class="info-item"><div class="info-label">BUY TP M / L</div><div class="info-value">{format_price(signal['buy_tp_medium'])} / {format_price(signal['buy_tp_large'])}</div></div>
                    <div class="info-item"><div class="info-label">SELL TP M / L</div><div class="info-value">{format_price(signal['sell_tp_medium'])} / {format_price(signal['sell_tp_large'])}</div></div>
                </div>

                <div class="section-title">5m / 15m Both Sides</div>
                <div class="info-list">
                    <div class="info-item"><div class="info-label">5M BUY</div><div class="info-value">{signal['m5_buy_status']}</div></div>
                    <div class="info-item"><div class="info-label">5M SELL</div><div class="info-value">{signal['m5_sell_status']}</div></div>
                    <div class="info-item"><div class="info-label">5M BUY Entry/SL</div><div class="info-value">{format_price(signal['m5_buy_entry'])} / {format_price(signal['m5_buy_sl'])}</div></div>
                    <div class="info-item"><div class="info-label">5M SELL Entry/SL</div><div class="info-value">{format_price(signal['m5_sell_entry'])} / {format_price(signal['m5_sell_sl'])}</div></div>
                    <div class="info-item"><div class="info-label">5M BUY TP1 / TP2</div><div class="info-value">{format_price(signal['m5_buy_tp1'])} / {format_price(signal['m5_buy_tp2'])}</div></div>
                    <div class="info-item"><div class="info-label">5M SELL TP1 / TP2</div><div class="info-value">{format_price(signal['m5_sell_tp1'])} / {format_price(signal['m5_sell_tp2'])}</div></div>
                    <div class="info-item"><div class="info-label">15M BUY</div><div class="info-value">{signal['m15_buy_status']}</div></div>
                    <div class="info-item"><div class="info-label">15M SELL</div><div class="info-value">{signal['m15_sell_status']}</div></div>
                    <div class="info-item"><div class="info-label">15M BUY Entry/SL</div><div class="info-value">{format_price(signal['m15_buy_entry'])} / {format_price(signal['m15_buy_sl'])}</div></div>
                    <div class="info-item"><div class="info-label">15M SELL Entry/SL</div><div class="info-value">{format_price(signal['m15_sell_entry'])} / {format_price(signal['m15_sell_sl'])}</div></div>
                    <div class="info-item"><div class="info-label">15M BUY TP1 / TP2</div><div class="info-value">{format_price(signal['m15_buy_tp1'])} / {format_price(signal['m15_buy_tp2'])}</div></div>
                    <div class="info-item"><div class="info-label">15M SELL TP1 / TP2</div><div class="info-value">{format_price(signal['m15_sell_tp1'])} / {format_price(signal['m15_sell_tp2'])}</div></div>
                </div>

<div class="section-title">Signal Erklaerung</div>
                <div class="card" style="background:rgba(255,255,255,0.02); box-shadow:none;">
                    <div class="muted">{signal['explanation']}</div>
                </div>


                <div class="section-title">Alert History</div>
                <table>
                    <tr>
                        <th>Zeit</th>
                        <th>Market</th>
                        <th>Symbol</th>
                        <th>Alert</th>
                        <th>Severity</th>
                        <th>Signal</th>
                        <th>Status</th>
                        <th>Score</th>
                        <th>Entry</th>
                        <th>SL</th>
                        <th>TP1</th>
                        <th>TP2</th>
                    </tr>
                    {alert_table_rows if alert_table_rows else "<tr><td colspan='12'>Keine Alerts</td></tr>"}
                </table>

                <div class="section-title">Signal History</div>
                <table>
                    <tr>
                        <th>Zeit</th>
                        <th>Signal</th>
                        <th>Status</th>
                        <th>Score</th>
                        <th>Zone Low</th>
                        <th>Zone High</th>
                        <th>Entry</th>
                        <th>SL</th>
                        <th>TP1</th>
                        <th>TP2</th>
                        <th>TP M</th>
                        <th>TP L</th>
                    </tr>
                    {history_rows if history_rows else "<tr><td colspan='12'>Keine History</td></tr>"}
                </table>
            </div>

            <div class="card">
                <h2>{tr(lang, "Gesamtbild", "Overall view")}</h2>

                <div class="info-list">
                    <div class="info-item"><div class="info-label">Overall Bias</div><div class="info-value">{overall_bias}</div></div>
                    <div class="info-item"><div class="info-label">{tr(lang, "Moegliche Groesse der Bewegung", "Possible size of movement")}</div><div class="info-value">{move_size}</div></div>
                </div>

                <div class="section-title">Last Daily Check</div>
                <div class="info-list">
                    <div class="info-item"><div class="info-label">Last D High</div><div class="info-value">{format_price(daily_info['last_day_high'])}</div></div>
                    <div class="info-item"><div class="info-label">Last D Low</div><div class="info-value">{format_price(daily_info['last_day_low'])}</div></div>
                    <div class="info-item"><div class="info-label">Last D Open</div><div class="info-value">{format_price(daily_info['last_day_open'])}</div></div>
                    <div class="info-item"><div class="info-label">Last D Close</div><div class="info-value">{format_price(daily_info['last_day_close'])}</div></div>
                    <div class="info-item"><div class="info-label">Today Open</div><div class="info-value">{format_price(daily_info['today_open'])}</div></div>
                    <div class="info-item"><div class="info-label">Today High now</div><div class="info-value">{format_price(daily_info['today_high_now'])}</div></div>
                    <div class="info-item"><div class="info-label">Today Low now</div><div class="info-value">{format_price(daily_info['today_low_now'])}</div></div>
                    <div class="info-item"><div class="info-label">Today Close now</div><div class="info-value">{format_price(daily_info['today_close_now'])}</div></div>
                </div>

                <div class="section-title">D1 / H1 Hauptlogik</div>
                <div class="info-list">
                    <div class="info-item"><div class="info-label">D1 Trend</div><div class="info-value {trend_class(d1['trend'])}">{d1['trend']}</div></div>
                    <div class="info-item"><div class="info-label">D1 BOS</div><div class="info-value">{d1['bos']}</div></div>
                    <div class="info-item"><div class="info-label">H1 Trend</div><div class="info-value {trend_class(h1['trend'])}">{h1['trend']}</div></div>
                    <div class="info-item"><div class="info-label">H1 BOS</div><div class="info-value">{h1['bos']}</div></div>
                    <div class="info-item"><div class="info-label">Last H1 High</div><div class="info-value">{format_price(h1['recent_high'])}</div></div>
                    <div class="info-item"><div class="info-label">Last H1 Low</div><div class="info-value">{format_price(h1['recent_low'])}</div></div>
                    <div class="info-item"><div class="info-label">H1 Support</div><div class="info-value">{format_price(h1['support'])}</div></div>
                    <div class="info-item"><div class="info-label">H1 Resistance</div><div class="info-value">{format_price(h1['resistance'])}</div></div>
                </div>

                <div class="section-title">5m Entry Check</div>
                <div class="info-list">
                    <div class="info-item"><div class="info-label">M5 Trend</div><div class="info-value {trend_class(m5['trend'])}">{m5['trend']}</div></div>
                    <div class="info-item"><div class="info-label">M5 BOS</div><div class="info-value">{m5['bos']}</div></div>
                    <div class="info-item"><div class="info-label">M5 CHOCH</div><div class="info-value">{m5['choch']}</div></div>
                    <div class="info-item"><div class="info-label">M5 ATR</div><div class="info-value">{format_price(m5['atr'])}</div></div>
                    <div class="info-item"><div class="info-label">FVG</div><div class="info-value">{m5['fvg_text']}</div></div>
                    <div class="info-item"><div class="info-label">Equal High</div><div class="info-value">{format_price(m5['eq_high']) if m5['eq_high'] else 'keine'}</div></div>
                    <div class="info-item"><div class="info-label">Equal Low</div><div class="info-value">{format_price(m5['eq_low']) if m5['eq_low'] else 'keine'}</div></div>
                </div>

                <div class="section-title">Trading Tools</div>
                <div class="info-list">
                    <div class="info-item"><div class="info-label">Buy-Side Liquidity</div><div class="info-value">{format_price(m5['buy_side_liquidity'])}</div></div>
                    <div class="info-item"><div class="info-label">Sell-Side Liquidity</div><div class="info-value">{format_price(m5['sell_side_liquidity'])}</div></div>
                    <div class="info-item"><div class="info-label">Support</div><div class="info-value">{format_price(m5['support'])}</div></div>
                    <div class="info-item"><div class="info-label">Resistance</div><div class="info-value">{format_price(m5['resistance'])}</div></div>
                    <div class="info-item"><div class="info-label">Premium Zone</div><div class="info-value">{format_price(m5['premium_zone'])}</div></div>
                    <div class="info-item"><div class="info-label">Discount Zone</div><div class="info-value">{format_price(m5['discount_zone'])}</div></div>
                    <div class="info-item"><div class="info-label">H4 Trend</div><div class="info-value {trend_class(h4['trend'])}">{h4['trend']}</div></div>
                    <div class="info-item"><div class="info-label">H4 BOS</div><div class="info-value">{h4['bos']}</div></div>
                </div>

                <div class="section-title">{tr(lang, "Mentor Erklaerung", "Mentor explanation")}</div>
                <div class="footer-note">
                    <b>BUY:</b> SL = letztes H1 Low, TP1/TP2 = 5m, TP mittel = letztes H1 High, TP gross = letztes Daily High.<br><br>
                    <b>SELL:</b> SL = letztes H1 High, TP1/TP2 = 5m, TP mittel = letztes H1 Low, TP gross = letztes Daily Low.<br><br>
                    <b>Daily + H1:</b> geben die Richtung und Zone.<br><br>
                    <b>5m:</b> prueft nur, ob ein besserer Entry moeglich ist.
                </div>
            </div>
        </div>
        """
        return page("Analyse", body)

    except Exception as e:
        body = f"""
        {topbar(lang, user, True, user['role'] == 'admin')}
        <div class="card">
            <a class="chip" href="/?lang={lang}">⬅ {tr(lang, "Zurueck zur Startseite", "Back to home")}</a>
            <h1 style="margin-top:18px;">{tr(lang, "Fehler", "Error")}</h1>
            <div class="banner banner-error">{str(e)}</div>
        </div>
        """
        return page("Fehler", body)
