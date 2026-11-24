import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import xml.etree.ElementTree as ET
from datetime import datetime
import re

try:
    import yfinance as yf
except Exception:
    yf = None

st.set_page_config(page_title="رادار التداول الاحترافي — 9 مدارس (USDT)", layout="wide")

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
    "breakeven_triggered": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

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
                    "close_time", "qav", "trades", "tbbav", "tbqav", "ignore"
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
                    "Low": "low", "Close": "close", "Volume": "volume"
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

    # 1. المتوسطات المتحركة
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    # 2. مؤشر القوة النسبية RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)

    # 3. مؤشر StochRSI
    rsi_min = rsi.rolling(window=14).min()
    rsi_max = rsi.rolling(window=14).max()
    stoch_rsi = (((rsi - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan)) * 100.0).fillna(50.0)

    # 4. الماكد MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - signal_line

    # 5. بولينجر باند
    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std().fillna(0.0)
    upper_band = sma20 + (std20 * 2.0)
    lower_band = sma20 - (std20 * 2.0)

    # 6. مؤشر السيولة MFI
    typical_price = (high + low + close) / 3.0
    raw_mf = typical_price * volume
    pos_mf = np.where(typical_price > typical_price.shift(1), raw_mf, 0.0)
    neg_mf = np.where(typical_price < typical_price.shift(1), raw_mf, 0.0)
    pos_mf_sum = pd.Series(pos_mf, index=df.index).rolling(window=14).sum()
    neg_mf_sum = pd.Series(neg_mf, index=df.index).rolling(window=14).sum().replace(0, np.nan)
    mfi = (100.0 - (100.0 / (1.0 + (pos_mf_sum / neg_mf_sum)))).fillna(50.0)

    # 7. مؤشر VWAP
    cum_vol = volume.rolling(window=48, min_periods=1).sum().replace(0, np.nan)
    cum_tp_vol = (typical_price * volume).rolling(window=48, min_periods=1).sum()
    vwap = (cum_tp_vol / cum_vol).fillna(close)

    # 8. إيشيموكو (تنكان وكيجون)
    tenkan = ((high.rolling(window=9).max() + low.rolling(window=9).min()) / 2.0).bfill()
    kijun = ((high.rolling(window=26).max() + low.rolling(window=26).min()) / 2.0).bfill()

    # 9. التقلب وقوة الاتجاه ATR و ADX
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).bfill()
    atr = tr.rolling(window=14, min_periods=1).mean().bfill()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_smooth = tr.rolling(window=14, min_periods=1).mean().replace(0, np.nan)
    plus_di = 100.0 * (pd.Series(plus_dm, index=df.index).rolling(window=14, min_periods=1).mean() / atr_smooth)
    minus_di = 100.0 * (pd.Series(minus_dm, index=df.index).rolling(window=14, min_periods=1).mean() / atr_smooth)
    dx = (100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(20.0)
    adx = dx.rolling(window=14, min_periods=1).mean().fillna(20.0)

    return pd.DataFrame({
        "close": close,
        "ema9": ema9,
        "ema21": ema21,
        "ema50": ema50,
        "rsi": rsi,
        "stoch_rsi": stoch_rsi,
        "macd": macd,
        "signal_line": signal_line,
        "macd_hist": macd_hist,
        "upper_band": upper_band,
        "lower_band": lower_band,
        "mfi": mfi,
        "vwap": vwap,
        "tenkan": tenkan,
        "kijun": kijun,
        "atr": atr,
        "adx": adx,
    })


def evaluate_nine_schools(ind_df, idx, news_info=None):
    if news_info is None:
        news_info = {"score": 0}

    price = float(ind_df["close"].iloc[idx])
    ema9 = float(ind_df["ema9"].iloc[idx])
    ema21 = float(ind_df["ema21"].iloc[idx])
    ema50 = float(ind_df["ema50"].iloc[idx])
    rsi = float(ind_df["rsi"].iloc[idx])
    s_rsi = float(ind_df["stoch_rsi"].iloc[idx])
    macd = float(ind_df["macd"].iloc[idx])
    sig = float(ind_df["signal_line"].iloc[idx])
    hist = float(ind_df["macd_hist"].iloc[idx])
    prev_hist = float(ind_df["macd_hist"].iloc[idx - 1]) if idx > 0 else hist
    upper_b = float(ind_df["upper_band"].iloc[idx]) if not pd.isna(ind_df["upper_band"].iloc[idx]) else price
    lower_b = float(ind_df["lower_band"].iloc[idx]) if not pd.isna(ind_df["lower_band"].iloc[idx]) else price
    mfi = float(ind_df["mfi"].iloc[idx])
    vwap = float(ind_df["vwap"].iloc[idx])
    tenkan = float(ind_df["tenkan"].iloc[idx])
    kijun = float(ind_df["kijun"].iloc[idx])
    adx = float(ind_df["adx"].iloc[idx])
    atr = float(ind_df["atr"].iloc[idx])

    score = 0
    bull_schools = 0
    bear_schools = 0
    reasons = []

    # 1. المتوسطات
    if ema9 > ema21 > ema50:
        score += 14
        bull_schools += 1
        reasons.append("1. المتوسطات: صاعد (EMA 9>21>50)")
    elif ema9 < ema21 < ema50:
        score -= 14
        bear_schools += 1
        reasons.append("1. المتوسطات: هابط (EMA 9<21<50)")
    else:
        reasons.append("1. المتوسطات: مختلط")

    # 2. RSI
    if rsi < 35:
        score += 11
        bull_schools += 1
        reasons.append(f"2. RSI: تشبع بيعي داعم للشراء ({rsi:.0f})")
    elif rsi > 65:
        score -= 11
        bear_schools += 1
        reasons.append(f"2. RSI: تشبع شرائي داعم للبيع ({rsi:.0f})")
    else:
        reasons.append(f"2. RSI: محايد ({rsi:.0f})")

    # 3. StochRSI
    if s_rsi < 25 and hist >= prev_hist:
        score += 10
        bull_schools += 1
        reasons.append("3. StochRSI: انعكاس صاعد")
    elif s_rsi > 75 and hist <= prev_hist:
        score -= 10
        bear_schools += 1
        reasons.append("3. StochRSI: انعكاس هابط")
    else:
        reasons.append("3. StochRSI: مستقر")

    # 4. الماكد
    if macd > sig and hist >= prev_hist:
        score += 12
        bull_schools += 1
        reasons.append("4. الماكد: زخم إيجابي")
    elif macd < sig and hist <= prev_hist:
        score -= 12
        bear_schools += 1
        reasons.append("4. الماكد: زخم سلبي")
    else:
        reasons.append("4. الماكد: متباطئ")

    # 5. بولينجر
    if lower_b > 0 and price <= lower_b * 1.004:
        score += 10
        bull_schools += 1
        reasons.append("5. بولينجر: قرب الحد السفلي")
    elif upper_b > 0 and price >= upper_b * 0.996:
        score -= 10
        bear_schools += 1
        reasons.append("5. بولينجر: قرب الحد العلوي")
    else:
        reasons.append("5. بولينجر: داخل النطاق")

    # 6. MFI
    if mfi < 32:
        score += 12
        bull_schools += 1
        reasons.append(f"6. MFI: دخول سيولة ({mfi:.0f})")
    elif mfi > 68:
        score -= 12
        bear_schools += 1
        reasons.append(f"6. MFI: خروج سيولة ({mfi:.0f})")
    else:
        reasons.append(f"6. MFI: متوازن ({mfi:.0f})")

    # 7. VWAP
    if price >= vwap:
        score += 11
        bull_schools += 1
        reasons.append("7. VWAP: أعلى المتوسط الحجمي")
    else:
        score -= 11
        bear_schools += 1
        reasons.append("7. VWAP: أدنى المتوسط الحجمي")

    # 8. إيشيموكو
    if price > tenkan > kijun:
        score += 10
        bull_schools += 1
        reasons.append("8. إيشيموكو: إيجابي")
    elif price < tenkan < kijun:
        score -= 10
        bear_schools += 1
        reasons.append("8. إيشيموكو: سلبي")
    else:
        reasons.append("8. إيشيموكو: متعادل")

    # 9. ADX + ATR
    if adx >= 22:
        score += 10 if score >= 0 else -10
        if score >= 0:
            bull_schools += 1
        else:
            bear_schools += 1
        reasons.append(f"9. ADX/ATR: اتجاه قوي ({adx:.1f})")
    else:
        score = int(score * 0.7)
        reasons.append(f"9. ADX/ATR: حركة هادئة ({adx:.1f})")

    n_score = int(news_info.get("score", 0))
    if n_score != 0:
        score += n_score
        reasons.append(f"الأخبار: ({n_score:+d})")

    score = max(-100, min(100, score))

    if score >= 30:
        decision = "BUY"
    elif score <= -30:
        decision = "SELL"
    else:
        decision = "NEUTRAL"

    return {
        "price": price,
        "rsi": rsi,
        "mfi": mfi,
        "adx": adx,
        "atr": atr,
        "vwap": vwap,
        "score": score,
        "decision": decision,
        "bull_schools": bull_schools,
        "bear_schools": bear_schools,
        "reasons": reasons,
    }


def render_glowing_alert(message, bg_color="#dc3545", glow_color="rgba(220, 53, 69, 0.95)"):
    st.markdown(f"""
    <style>
    @keyframes pulseGlow {{
        0% {{ box-shadow: 0 0 8px {glow_color}, 0 0 18px {glow_color}; }}
        50% {{ box-shadow: 0 0 22px {glow_color}, 0 0 36px {glow_color}; }}
        100% {{ box-shadow: 0 0 8px {glow_color}, 0 0 18px {glow_color}; }}
    }}
    .glow-exit-banner {{
        background: {bg_color};
        color: #ffffff;
        padding: 15px 18px;
        border-radius: 12px;
        border: 2px solid #fff3cd;
        font-size: 17px;
        font-weight: 800;
        text-align: center;
        margin: 10px 0;
        animation: pulseGlow 1.1s infinite ease-in-out;
    }}
    </style>
    <div class="glow-exit-banner">💡 {message}</div>
    """, unsafe_allow_html=True)


# الشريط الجانبي
st.sidebar.header("📡 رادار الفرص (USDT)")
timeframe = st.sidebar.selectbox("الإطار الزمني", options=["1m", "5m", "15m"], index=1)

if st.sidebar.button("🔍 ابحث عن أفضل عملة الآن", type="primary", use_container_width=True):
    ranked = []
    for coin in WATCHLIST_USDT:
        d_coin, _ = fetch_usdt_ohlcv(coin, interval=timeframe, limit=120)
        if d_coin is not None and len(d_coin) >= 35:
            ind_c = compute_nine_schools_indicators(d_coin)
            n_c = fetch_brief_news_signal(coin)
            res_c = evaluate_nine_schools(ind_c, len(ind_c) - 1, news_info=n_c)
            ranked.append({
                "العملة": coin,
                "القوة": res_c["score"],
                "الأخبار": n_c["score"],
                "ADX": round(res_c["adx"], 1),
                "abs_s": abs(res_c["score"]),
            })

    if ranked:
        rdf = pd.DataFrame(ranked).sort_values(by="abs_s", ascending=False).reset_index(drop=True)
        top_candidates = rdf.head(6).to_dict("records")
        prev_coins = [x["العملة"] for x in st.session_state.radar_candidates]
        curr_coins = [x["العملة"] for x in top_candidates]
        if prev_coins == curr_coins and len(top_candidates) > 1:
            next_idx = (st.session_state.radar_cycle_idx + 1) % len(top_candidates)
        else:
            next_idx = 0

        st.session_state.radar_candidates = top_candidates
        st.session_state.radar_cycle_idx = next_idx
        chosen = top_candidates[next_idx]
        st.session_state.selected_symbol = chosen["العملة"]
        st.session_state.radar_symbol = chosen["العملة"]
        st.session_state.radar_decision = "SELL" if chosen["القوة"] < 0 else "BUY"

        d_txt = "شراء 🟢" if chosen["القوة"] > 0 else "بيع 🔴"
        st.sidebar.success(
            f"🎯 **{chosen['العملة']}** ({next_idx + 1}/{len(top_candidates)}) — "
            f"{d_txt} ({int(chosen['abs_s'])}/100)"
        )
        st.sidebar.dataframe(rdf[["العملة", "القوة", "الأخبار"]], use_container_width=True, hide_index=True)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ إعدادات الصفقة")
raw_input = st.sidebar.text_input("رمز العملة (USDT)", value=st.session_state.selected_symbol)
symbol = normalize_symbol_to_usdt(raw_input)
if symbol != st.session_state.radar_symbol:
    st.session_state.radar_decision = ""
st.session_state.selected_symbol = symbol

capital_usdt = st.sidebar.number_input("رأس المال (USDT)", min_value=10.0, value=500.0, step=50.0)
max_risk_pct = st.sidebar.slider("المخاطرة القصوى (%)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)
sl_mode = st.sidebar.radio("حساب وقف الخسارة", options=["ذكي حسب التقلب (ATR)", "نسبة ثابتة (%)"], index=0)
fixed_sl_pct = st.sidebar.slider("نسبة الوقف الثابتة (%)", min_value=0.5, max_value=10.0, value=1.5, step=0.5)
auto_advance = st.sidebar.checkbox("تقدّم وتأمين الصفقة تلقائياً", value=True)

# العنوان والمنطقة الرئيسية
st.title("🧭 مكتب التداول الذكي — 9 مدارس احترافية (USDT)")

top_l, top_r = st.columns([4, 1])
with top_r:
    if st.button("🔄 تحديث البيانات", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

df, data_source = fetch_usdt_ohlcv(symbol, interval=timeframe, limit=120)
ind_df = compute_nine_schools_indicators(df)
news_info = fetch_brief_news_signal(symbol)
analysis = evaluate_nine_schools(ind_df, len(ind_df) - 1, news_info=news_info)

price = analysis["price"]
rsi = analysis["rsi"]
mfi = analysis["mfi"]
adx = analysis["adx"]
atr = analysis["atr"]
score = analysis["score"]

if st.session_state.radar_symbol == symbol and st.session_state.radar_decision in ["BUY", "SELL"]:
    decision = st.session_state.radar_decision
else:
    decision = analysis["decision"]

last_update = datetime.now().strftime("%H:%M:%S")

if sl_mode == "ذكي حسب التقلب (ATR)" and atr > 0:
    sl_dist = max(atr * 2.0, price * 0.005)
    sl_pct = (sl_dist / price) * 100.0
else:
    sl_pct = fixed_sl_pct
    sl_dist = price * (sl_pct / 100.0)

risk_usdt = capital_usdt * (max_risk_pct / 100.0)
pos_usdt = min(capital_usdt, risk_usdt / (sl_pct / 100.0))

if decision == "BUY":
    sig_label = f"شراء (BUY) 🟢 | {abs(score)}/100"
    sig_color = "#198754"
    btn_tag = "🟢 شراء"
    guidance = f"أفضلية شراء ({analysis['bull_schools']}/9 مدارس داعمة) — راقب الوقف والهدفين."
elif decision == "SELL":
    sig_label = f"بيع (SELL) 🔴 | {abs(score)}/100"
    sig_color = "#dc3545"
    btn_tag = "🔴 بيع"
    guidance = f"أفضلية بيع ({analysis['bear_schools']}/9 مدارس داعمة) — التزم بالوقف أعلى الدخول."
else:
    sig_label = f"ترقب ⏳ | {score}"
    sig_color = "#6c757d"
    btn_tag = "🟡 ترقب (دخول يدوي)"
    guidance = "الإشارة متوسطة أو متذبذبة — الانتظار أفضل من التسرع."

with top_l:
    st.caption(
        f"📡 **{data_source}** | تحديث: **{last_update}** | الفريم: **{timeframe}** | ADX: **{adx:.1f}**"
    )

st.markdown(f"""
<div style="background-color: {news_info['color']}; padding: 8px 14px; border-radius: 8px; color: white; font-weight: bold; margin-bottom: 10px;">
    📰 الأخبار: {news_info['status']} ({news_info['score']:+d})
</div>
""", unsafe_allow_html=True)

st.info(f"🧭 **توجيه القرار الآن:** {guidance}")

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"سعر {symbol}", format_price(price), f"VWAP: {format_price(analysis['vwap'])}")
c2.metric("MFI / RSI", f"{mfi:.0f} / {rsi:.0f}")
c3.metric("حجم الصفقة", f"{pos_usdt:,.2f} USDT", f"مخاطرة {risk_usdt:,.2f} USDT")

with c4:
    st.markdown(f"""
    <div style="background-color: {sig_color}; padding: 12px; border-radius: 10px; text-align: center; color: white; font-weight: bold; font-size: 15px;">
        {sig_label}
    </div>
    """, unsafe_allow_html=True)

with st.expander("📋 تفاصيل المدارس الـ 9 والأخبار", expanded=False):
    for r_item in analysis["reasons"]:
        st.write(f"• {r_item}")

st.markdown("---")

if not st.session_state.trade_active:
    st.subheader(f"🚀 صفقة جديدة — {symbol}")

    if decision == "SELL":
        is_sell = True
        sl_price = price + sl_dist
        tp1_price = price - (sl_dist * 1.5)
        tp2_price = price - (sl_dist * 2.5)
        sl_txt = f"+{sl_pct:.2f}%"
        tp1_txt = f"-{sl_pct * 1.5:.2f}%"
        tp2_txt = f"-{sl_pct * 2.5:.2f}%"
    elif decision == "BUY":
        is_sell = False
        sl_price = price - sl_dist
        tp1_price = price + (sl_dist * 1.5)
        tp2_price = price + (sl_dist * 2.5)
        sl_txt = f"-{sl_pct:.2f}%"
        tp1_txt = f"+{sl_pct * 1.5:.2f}%"
        tp2_txt = f"+{sl_pct * 2.5:.2f}%"
    else:
        st.warning("⏳ الإشارة الحالية **ترقب** — الأرقام أدناه توضيحية حتى تتضح إشارة شراء أو بيع.")
        is_sell = score < 0
        if is_sell:
            sl_price = price + sl_dist
            tp1_price = price - (sl_dist * 1.5)
            tp2_price = price - (sl_dist * 2.5)
            sl_txt = f"+{sl_pct:.2f}%"
            tp1_txt = f"-{sl_pct * 1.
