import streamlit as st
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import plotly.express as px
import xml.etree.ElementTree as ET
from datetime import datetime
import re

st.set_page_config(page_title="مكتب التداول الذكي — USDT", layout="wide")

defaults = {
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
    "breakeven_triggered": False
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.title("🧭 مكتب التداول الذكي — تنبيهات خروج مضيئة وتبديل الفرص (USDT)")

WATCHLIST_USDT = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
    "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "NEARUSDT", "SUIUSDT", "DOTUSDT"
]

BULLISH_KEYWORDS = [
    "approval", "approved", "etf", "surge", "rally", "bull", "bullish", "adopt", "adoption",
    "rate cut", "cut rates", "inflow", "breakout", "partnership", "launch", "record high", "all-time high"
]

BEARISH_KEYWORDS = [
    "hack", "hacked", "exploit", "lawsuit", "sec", "ban", "banned", "crash", "plunge",
    "bear", "bearish", "rate hike", "hike rates", "inflation", "outflow", "liquidation", "fraud", "delist"
]

def format_price(val):
    return f"{val:,.4f} USDT" if abs(val) < 10 else f"{val:,.2f} USDT"

def normalize_symbol_to_usdt(raw_sym):
    s = str(raw_sym).strip().upper().replace("-USD", "").replace("/USDT", "").replace("-", "")
    if not s:
        return "BTCUSDT"
    if not s.endswith("USDT"):
        s = f"{s}USDT"
    return s

@st.cache_data(ttl=180)
def fetch_brief_news_signal(symbol_usdt):
    base_coin = symbol_usdt.replace("USDT", "").lower()
    feeds = [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss"
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
    elif score < 0:
        return {"score": score, "status": "سالبة للبيع 🔴", "color": "#dc3545"}
    else:
        return {"score": 0, "status": "متعادلة ⚪", "color": "#6c757d"}

@st.cache_data(ttl=15)
def fetch_usdt_ohlcv(symbol_usdt, interval="5m", limit=120):
    sym = normalize_symbol_to_usdt(symbol_usdt)

    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 20:
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'qav', 'trades', 'tbbav', 'tbqav', 'ignore'
                ])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].dropna().reset_index(drop=True)
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
                df = pd.DataFrame(raw, columns=['timestamp', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
                df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='s')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].dropna().reset_index(drop=True)
                if len(df) >= 35:
                    return df, "KuCoin"
    except Exception:
        pass

    try:
        base = sym.replace("USDT", "")
        yf_pair = f"{base}-USD"
        period = "5d" if interval in ["5m", "15m", "1h"] else "1d"
        df = yf.download(yf_pair, period=period, interval=interval, progress=False, timeout=4)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            time_col = 'Datetime' if 'Datetime' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
            df = df.rename(columns={
                time_col: 'timestamp', 'Open': 'open', 'High': 'high',
                'Low': 'low', 'Close': 'close', 'Volume': 'volume'
            })
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].dropna().tail(limit).reset_index(drop=True)
            if len(df) >= 35:
                return df, "Yahoo Finance"
    except Exception:
        pass

    return None, None

def compute_expert_indicators(df):
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume'].fillna(0)

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi_min = rsi.rolling(window=14).min()
    rsi_max = rsi.rolling(window=14).max()
    stoch_rsi = ((rsi - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan)) * 100

    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - signal_line

    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    upper_band = sma20 + (std20 * 2)
    lower_band = sma20 - (std20 * 2)

    typical_price = (high + low + close) / 3.0
    cum_vol = volume.rolling(window=48, min_periods=1).sum().replace(0, np.nan)
    cum_tp_vol = (typical_price * volume).rolling(window=48, min_periods=1).sum()
    vwap = (cum_tp_vol / cum_vol).fillna(close)

    raw_mf = typical_price * volume
    pos_mf = np.where(typical_price > typical_price.shift(1), raw_mf, 0.0)
    neg_mf = np.where(typical_price < typical_price.shift(1), raw_mf, 0.0)
    pos_mf_sum = pd.Series(pos_mf, index=df.index).rolling(window=14).sum()
    neg_mf_sum = pd.Series(neg_mf, index=df.index).rolling(window=14).sum().replace(0, np.nan)
    mfi = 100 - (100 / (1 + (pos_mf_sum / neg_mf_sum)))

    tenkan = (high.rolling(window=9).max() + low.rolling(window=9).min()) / 2.0
    kijun = (high.rolling(window=26).max() + low.rolling(window=26).min()) / 2.0

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean().bfill()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_smooth = tr.rolling(window=14).mean().replace(0, np.nan)
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(window=14).mean() / atr_smooth)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(window=14).mean() / atr_smooth)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.rolling(window=14).mean().fillna(20.0)

    vol_sma20 = volume.rolling(window=20).mean().replace(0, np.nan)
    vol_ratio = (volume / vol_sma20).fillna(1.0)

    return pd.DataFrame({
        "close": close, "rsi": rsi, "stoch_rsi": stoch_rsi,
        "ema9": ema9, "ema21": ema21, "ema50": ema50,
        "macd": macd, "signal_line": signal_line, "macd_hist": macd_hist,
        "upper_band": upper_band, "lower_band": lower_band,
        "vwap": vwap, "mfi": mfi, "tenkan": tenkan, "kijun": kijun,
        "atr": atr, "adx": adx, "vol_ratio": vol_ratio
    })

def veteran_expert_decision(ind_df, idx, htf_bias=0, news_info=None):
    if news_info is None:
        news_info = {"score": 0}

    price = float(ind_df['close'].iloc[idx])
    rsi = float(ind_df['rsi'].iloc[idx]) if not pd.isna(ind_df['rsi'].iloc[idx]) else 50.0
    s_rsi = float(ind_df['stoch_rsi'].iloc[idx]) if not pd.isna(ind_df['stoch_rsi'].iloc[idx]) else 50.0
    mfi = float(ind_df['mfi'].iloc[idx]) if not pd.isna(ind_df['mfi'].iloc[idx]) else 50.0
    ema9 = float(ind_df['ema9'].iloc[idx])
    ema21 = float(ind_df['ema21'].iloc[idx])
    ema50 = float(ind_df['ema50'].iloc[idx])
    macd = float(ind_df['macd'].iloc[idx])
    sig = float(ind_df['signal_line'].iloc[idx])
    hist = float(ind_df['macd_hist'].iloc[idx])
    prev_hist = float(ind_df['macd_hist'].iloc[idx - 1]) if idx > 0 else hist
    vwap = float(ind_df['vwap'].iloc[idx])
    tenkan = float(ind_df['tenkan'].iloc[idx]) if not pd.isna(ind_df['tenkan'].iloc[idx]) else price
    kijun = float(ind_df['kijun'].iloc[idx]) if not pd.isna(ind_df['kijun'].iloc[idx]) else price
    adx = float(ind_df['adx'].iloc[idx])
    atr = float(ind_df['atr'].iloc[idx])
    vol_ratio = float(ind_df['vol_ratio'].iloc[idx])
    upper_b = ind_df['upper_band'].iloc[idx]
    lower_b = ind_df['lower_band'].iloc[idx]

    score = 0
    bull_conf = 0
    bear_conf = 0
    reasons = []

    if ema9 > ema21 > ema50:
        score += 18
        bull_conf += 1
        reasons.append("ترتيب متوسطات صاعد (EMA 9>21>50)")
    elif ema9 < ema21 < ema50:
        score -= 18
        bear_conf += 1
        reasons.append("ترتيب متوسطات هابط (EMA 9<21<50)")
    elif ema9 > ema21:
        score += 9
        reasons.append("تقاطع صاعد سريع (EMA9 > EMA21)")
    else:
        score -= 9
        reasons.append("تقاطع هابط سريع (EMA9 < EMA21)")

    if price > tenkan > kijun:
        score += 14
        bull_conf += 1
        reasons.append("توازن إيشيموكو إيجابي")
    elif price < tenkan < kijun:
        score -= 14
        bear_conf += 1
        reasons.append("توازن إيشيموكو سلبي")

    if mfi < 28 or rsi < 32:
        score += 16
        bull_conf += 1
        reasons.append(f"تجميع سيولة ذكية (MFI={mfi:.0f}, RSI={rsi:.0f})")
    elif mfi > 72 or rsi > 68:
        score -= 16
        bear_conf += 1
        reasons.append(f"تصريف سيولة وتشبع (MFI={mfi:.0f}, RSI={rsi:.0f})")

    if s_rsi < 20 and hist > prev_hist:
        score += 10
        bull_conf += 1
        reasons.append("انعكاس صاعد مبكر (StochRSI)")
    elif s_rsi > 80 and hist < prev_hist:
        score -= 10
        bear_conf += 1
        reasons.append("انعكاس هابط مبكر (StochRSI)")

    if macd > sig and hist > prev_hist:
        score += 14
        bull_conf += 1
        reasons.append("تسارع إيجابي للماكد")
    elif macd < sig and hist < prev_hist:
        score -= 14
        bear_conf += 1
        reasons.append("تسارع سلبي للماكد")

    if price > vwap:
        score += 12
        bull_conf += 1
        reasons.append("فوق سيولة المؤسسات VWAP")
    else:
        score -= 12
        bear_conf += 1
        reasons.append("تحت ضغط سيولة VWAP")

    if vol_ratio >= 1.6:
        reasons.append(f"قفزة سيولة ({vol_ratio:.1f}x)")
        score += 8 if score > 0 else -8

    if not pd.isna(lower_b) and price <= float(lower_b) * 1.003:
        score += 10
        reasons.append("قاع بولينجر")
    elif not pd.isna(upper_b) and price >= float(upper_b) * 0.997:
        score -= 10
        reasons.append("قمة بولينجر")

    if htf_bias > 0:
        score += 12
        bull_conf += 1
        reasons.append("دعم فريم الساعة الصاعد")
    elif htf_bias < 0:
        score -= 12
        bear_conf += 1
        reasons.append("دعم فريم الساعة الهابط")

    n_score = news_info.get("score", 0)
    if n_score > 0:
        score += n_score
        bull_conf += 1
        reasons.append(f"أخبار موجبة للشراء ({n_score:+d})")
    elif n_score < 0:
        score += n_score
        bear_conf += 1
        reasons.append(f"أخبار سالبة للبيع ({n_score:+d})")

    if adx < 18:
        score = int(score * 0.65)
        reasons.append(f"ترند عرضي (ADX={adx:.1f})")
    elif adx >= 25:
        reasons.append(f"ترند قوي (ADX={adx:.1f})")

    score = max(-100, min(100, score))

    if score >= 35:
        decision = "BUY"
    elif score <= -35:
        decision = "SELL"
    else:
        decision = "NEUTRAL"

    return {
        "price": price, "rsi": rsi, "mfi": mfi, "adx": adx, "atr": atr, "vwap": vwap,
        "score": score, "decision": decision,
        "bull_conf": bull_conf, "bear_conf": bear_conf
