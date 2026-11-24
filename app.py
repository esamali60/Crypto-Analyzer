import re
import xml.etree.ElementTree as ET
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None

st.set_page_config(page_title="مكتب التداول الذكي — 9 مدارس (USDT)", layout="wide")

DEFAULTS = {
    "trade_active": False,
    "entry_price": 0.0,
    "stop_loss": 0.0,
    "take_profit_1": 0.0,
    "take_profit_2": 0.0,
    "position_size_usdt": 0.0,
    "coins_bought": 0.0,
    "trade_symbol": "",
    "trade_type": "شراء",
    "selected_symbol": "BTCUSDT",
    "radar_symbol": "",
    "radar_decision": "",
    "radar_candidates": [],
    "radar_cycle_idx": 0,
    "trade_history": [],
    "breakeven_triggered": False,
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

WATCHLIST_USDT = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
    "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "NEARUSDT", "SUIUSDT", "DOTUSDT",
]

BULLISH_KEYWORDS = [
    "approval", "approved", "etf", "surge", "rally", "bull", "bullish", "adopt", "adoption",
    "rate cut", "cut rates", "inflow", "breakout", "partnership", "launch", "record high", "all-time high",
]

BEARISH_KEYWORDS = [
    "hack", "hacked", "exploit", "lawsuit", "sec", "ban", "banned", "crash", "plunge",
    "bear", "bearish", "rate hike", "hike rates", "inflation", "outflow", "liquidation", "fraud", "delist",
]


def format_price(val):
    return f"{val:,.4f} USDT" if abs(val) < 10 else f"{val:,.2f} USDT"


def normalize_symbol_to_usdt(raw_sym):
    s = str(raw_sym or "").strip().upper().replace("-USD", "").replace("/USDT", "").replace("-", "")
    if not s:
        return "BTCUSDT"
    if not s.endswith("USDT"):
        s = f"{s}USDT"
    return s


def fallback_synthetic_ohlcv(symbol_usdt, limit=120):
    seed_val = sum(ord(ch) for ch in normalize_symbol_to_usdt(symbol_usdt)) % 1000 + 42
    rng = np.random.default_rng(seed_val)
    base_price = 68000.0 if "BTC" in symbol_usdt else (2600.0 if "ETH" in symbol_usdt else 1.45)
    returns = rng.normal(0.0, 0.0025, size=limit)
    closes = base_price * np.cumprod(1.0 + returns)
    opens = np.roll(closes, 1)
    opens[0] = base_price
    spread = np.abs(rng.normal(0.002, 0.001, size=limit)) * closes
    highs = np.maximum(opens, closes) + spread
    lows = np.minimum(opens, closes) - spread
    volumes = rng.integers(500, 8000, size=limit).astype(float)
    timestamps = pd.date_range(end=datetime.now(), periods=limit, freq="5min")
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


@st.cache_data(ttl=180)
def fetch_brief_news_signal(symbol_usdt):
    base_coin = normalize_symbol_to_usdt(symbol_usdt).replace("USDT", "").lower()
    feeds = [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss",
    ]
    raw_score = 0.0

    for feed_url in feeds:
        try:
            resp = requests.get(feed_url, timeout=3, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and resp.text:
                root = ET.fromstring(resp.text)
                for item in root.findall(".//item")[:10]:
                    title_el = item.find("title")
                    if title_el is not None and title_el.text:
                        title = re.sub(r"\s+", " ", title_el.text.strip()).lower()
                        weight = 1.5 if (base_coin in title or "bitcoin" in title or "crypto" in title) else 0.8
                        p_hits = sum(1 for w in BULLISH_KEYWORDS if w in title)
                        n_hits = sum(1 for w in BEARISH_KEYWORDS if w in title)
                        raw_score += (p_hits - n_hits) * 4.0 * weight
        except Exception:
            continue

    score = int(max(-20, min(20, round(raw_score))))
    if score > 0:
        return {"score": score, "status": "موجبة للشراء 🟢", "color": "#198754"}
    if score < 0:
        return {"score": score, "status": "سالبة للبيع 🔴", "color": "#dc3545"}
    return {"score": 0, "status": "متعادلة ⚪", "color": "#6c757d"}


@st.cache_data(ttl=15)
def fetch_usdt_ohlcv(symbol_usdt, interval="5m", limit=120):
    sym = normalize_symbol_to_usdt(symbol_usdt)

    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) >= 35:
                df = pd.DataFrame(data, columns=[
                    "timestamp", "open", "high", "low", "close", "volume",
                    "close_time", "qav", "trades", "tbbav", "tbqav", "ignore",
                ])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df[["timestamp", "open", "high", "low", "close", "volume"]].dropna().reset_index(drop=True)
                if len(df) >= 35:
                    return df, "Binance"
    except Exception:
        pass

    try:
        base = sym.replace("USDT", "")
        kc_pair = f"{base}-USDT"
        kc_map = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1hour"}
        kc_tf = kc_map.get(interval, "5min")
        url_kc = f"https://api.kucoin.com/api/v1/market/candles?type={kc_tf}&symbol={kc_pair}"
        r_kc = requests.get(url_kc, timeout=3)
        if r_kc.status_code == 200:
            res_json = r_kc.json()
            if res_json.get("code") == "200000" and res_json.get("data"):
                raw = res_json["data"][:limit][::-1]
                df = pd.DataFrame(raw, columns=["timestamp", "open", "close", "high", "low", "volume", "turnover"])
                df["timestamp"] = pd.to_datetime(pd.to_numeric(df["timestamp"]), unit="s")
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df[["timestamp", "open", "high", "low", "close", "volume"]].dropna().reset_index(drop=True)
                if len(df) >= 35:
                    return df, "KuCoin"
    except Exception:
        pass

    if yf is not None:
        try:
            base = sym.replace("USDT", "")
            yf_pair = f"{base}-USD"
            period = "5d" if interval in ["5m", "15m", "1h"] else "1d"
            df = yf.download(yf_pair, period=period, interval=interval, progress=False, timeout=4)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df.reset_index()
                time_col = "Datetime" if "Datetime" in df.columns else ("Date" if "Date" in df.columns else df.columns[0])
                df = df.rename(columns={
                    time_col: "timestamp", "Open": "open", "High": "high",
                    "Low": "low", "Close": "close", "Volume": "volume",
                })
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df[["timestamp", "open", "high", "low", "close", "volume"]].dropna().tail(limit).reset_index(drop=True)
                if len(df) >= 35:
                    return df, "Yahoo Finance"
        except Exception:
            pass

    return fallback_synthetic_ohlcv(sym, limit=limit), "محاكاة احتياطية"


def compute_nine_schools_indicators(df):
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"].fillna(0)

    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)

    rsi_min = rsi.rolling(window=14).min()
    rsi_max = rsi.rolling(window=14).max()
    stoch_rsi = (((rsi - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan)) * 100.0).fillna(50.0)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - signal_line

    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std().fillna(0.0)
    upper_band = sma20 + (std20 * 2.0)
    lower_band = sma20 - (std20 * 2.0)

    typical_price = (high + low + close) / 3.0
    raw_mf = typical_price * volume
    pos_mf = np.where(typical_price > typical_price.shift(1), raw_mf, 0.0)
    neg_mf = np.where(typical_price < typical_price.shift(1), raw_mf, 0.0)
    pos_mf_sum = pd.Series(pos_mf, index=df.index).rolling(window=14).sum()
    neg_mf_sum = pd.Series(neg_mf, index=df.index).rolling(window=14).sum().replace(0, np.nan)
    mfi = (100.0 - (100.0 / (1.0 + (pos_mf_sum / neg_mf_sum)))).fillna(50.0)

    cum_vol = volume.rolling(window=48, min_periods=1).sum().replace(0, np.nan)
    cum_tp_vol = (typical_price * volume).rolling(window=48, min_periods=1).sum()
    vwap = (cum_tp_vol / cum_vol).fillna(close)

    tenkan = ((high.rolling(window=9).max() + low.rolling
