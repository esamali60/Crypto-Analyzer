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

st.set_page_config(page_title="مكتب التداول الذكي — 9 مدارس + أخبار (USDT)", layout="wide")

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

    tenkan = ((high.rolling(window=9).max() + low.rolling(window=9).min()) / 2.0).bfill()
    kijun = ((high.rolling(window=26).max() + low.rolling(window=26).min()) / 2.0).bfill()

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

    tech_score = 0
    bull_schools = 0
    bear_schools = 0
    reasons = []

    if ema9 > ema21 > ema50:
        tech_score += 14
        bull_schools += 1
        reasons.append("1. المتوسطات: صاعد (EMA 9>21>50)")
    elif ema9 < ema21 < ema50:
        tech_score -= 14
        bear_schools += 1
        reasons.append("1. المتوسطات: هابط (EMA 9<21<50)")
    else:
        reasons.append("1. المتوسطات: مختلط")

    if rsi < 35:
        tech_score += 11
        bull_schools += 1
        reasons.append(f"2. RSI: تشبع بيعي ({rsi:.0f})")
    elif rsi > 65:
        tech_score -= 11
        bear_schools += 1
        reasons.append(f"2. RSI: تشبع شرائي ({rsi:.0f})")
    else:
        reasons.append(f"2. RSI: محايد ({rsi:.0f})")

    if s_rsi < 25 and hist >= prev_hist:
        tech_score += 10
        bull_schools += 1
        reasons.append("3. StochRSI: انعكاس صاعد")
    elif s_rsi > 75 and hist <= prev_hist:
        tech_score -= 10
        bear_schools += 1
        reasons.append("3. StochRSI: انعكاس هابط")
    else:
        reasons.append("3. StochRSI: مستقر")

    if macd > sig and hist >= prev_hist:
        tech_score += 12
        bull_schools += 1
        reasons.append("4. الماكد: زخم إيجابي")
    elif macd < sig and hist <= prev_hist:
        tech_score -= 12
        bear_schools += 1
        reasons.append("4. الماكد: زخم سلبي")
    else:
        reasons.append("4. الماكد: متباطئ")

    if lower_b > 0 and price <= lower_b * 1.004:
        tech_score += 10
        bull_schools += 1
        reasons.append("5. بولينجر: قرب الحد السفلي")
    elif upper_b > 0 and price >= upper_b * 0.996:
        tech_score -= 10
        bear_schools += 1
        reasons.append("5. بولينجر: قرب الحد العلوي")
    else:
        reasons.append("5. بولينجر: داخل النطاق")

    if mfi < 32:
        tech_score += 12
        bull_schools += 1
        reasons.append(f"6. MFI: دخول سيولة ({mfi:.0f})")
    elif mfi > 68:
        tech_score -= 12
        bear_schools += 1
        reasons.append(f"6. MFI: خروج سيولة ({mfi:.0f})")
    else:
        reasons.append(f"6. MFI: متوازن ({mfi:.0f})")

    if price >= vwap:
        tech_score += 11
        bull_schools += 1
        reasons.append("7. VWAP: أعلى المتوسط الحجمي")
    else:
        tech_score -= 11
        bear_schools += 1
        reasons.append("7. VWAP: أدنى المتوسط الحجمي")

    if price > tenkan > kijun:
        tech_score += 10
        bull_schools += 1
        reasons.append("8. إيشيموكو: إيجابي")
    elif price < tenkan < kijun:
        tech_score -= 10
        bear_schools += 1
        reasons.append("8. إيشيموكو: سلبي")
    else:
        reasons.append("8. إيشيموكو: متعادل")

    if adx >= 22:
        if tech_score >= 0:
            tech_score += 10
            bull_schools += 1
        else:
            tech_score -= 10
            bear_schools += 1
        reasons.append(f"9. ADX/ATR: اتجاه قوي ({adx:.1f})")
    else:
        tech_score = int(tech_score * 0.7)
        reasons.append(f"9. ADX/ATR: حركة هادئة ({adx:.1f})")

    n_score = int(news_info.get("score", 0))
    if n_score != 0:
        reasons.append(f"الأخبار: ({n_score:+d})")

    # دمج ذكي يوازن بين المدارس الـ 9 والأخبار ويمنع الاندفاع عند التعارض
    conflict = (tech_score > 0 and n_score < 0) or (tech_score < 0 and n_score > 0)
    aligned = (tech_score > 0 and n_score > 0) or (tech_score < 0 and n_score < 0)

    total_score = max(-100, min(100, tech_score + n_score))

    if conflict:
        # في حال تعارض الأخبار مع المدارس، نشترط أغلبية واضحة (5/9 مدارس فأكثر) وقوة كافية
        if total_score >= 38 and bull_schools >= 5:
            decision = "BUY"
            verdict_note = f"أفضلية شراء فنية ({bull_schools}/9 مدارس) رغم سلبية الأخبار — التزم بالوقف."
        elif total_score <= -38 and bear_schools >= 5:
            decision = "SELL"
            verdict_note = f"أفضلية بيع فنية ({bear_schools}/9 مدارس) رغم إيجابية الأخبار — التزم بالوقف."
        else:
            decision = "NEUTRAL"
            verdict_note = (
                f"⚠️ تعارض بين الأخبار ({n_score:+d}) والمدارس الـ 9 ({bull_schools} شراء / {bear_schools} بيع) "
                "— الأفضلية للترقب أو الدخول بحذر."
            )
    else:
        if total_score >= 30 and bull_schools >= 4:
            decision = "BUY"
            tag = "توافق قوي (مدارس + أخبار)" if aligned else "أفضلية شراء فنية"
            verdict_note = f"{tag}: {bull_schools}/9 مدارس داعمة للشراء."
        elif total_score <= -30 and bear_schools >= 4:
            decision = "SELL"
            tag = "توافق قوي (مدارس + أخبار)" if aligned else "أفضلية بيع فنية"
            verdict_note = f"{tag}: {bear_schools}/9 مدارس داعمة للبيع."
        else:
            decision = "NEUTRAL"
            verdict_note = "الإشارة متوسطة أو متذبذبة — الانتظار أفضل من التسرع."

    return {
        "price": price,
        "rsi": rsi,
        "mfi": mfi,
        "adx": adx,
        "atr": atr,
        "vwap": vwap,
        "tech_score": tech_score,
        "score": total_score,
        "decision": decision,
        "bull_schools": bull_schools,
        "bear_schools": bear_schools,
        "conflict": conflict,
        "aligned": aligned,
        "verdict_note": verdict_note,
        "reasons": reasons,
    }


def render_glowing_alert(message, bg_color="#dc3545", glow_color="rgba(220, 53, 69, 0.95)"):
    st.markdown(
        f"""
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
        """,
        unsafe_allow_html=True,
    )


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
            # أولوية أعلى للفرص المتوافقة بين المدارس والأخبار
            priority = abs(res_c["score"]) + (15 if res_c["aligned"] else (-10 if res_c["conflict"] else 0))
            ranked.append({
                "العملة": coin,
                "القوة": res_c["score"],
                "الأخبار": n_c["score"],
                "التوافق": "✅ متوافق" if res_c["aligned"] else ("⚠️ تعارض" if res_c["conflict"] else "➖ محايد"),
                "priority": priority,
                "decision": res_c["decision"],
            })

    if ranked:
        rdf = pd.DataFrame(ranked).sort_values(by="priority", ascending=False).reset_index(drop=True)
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
        st.session_state.radar_decision = chosen["decision"] if chosen["decision"] in ["BUY", "SELL"] else ""

        d_txt = "شراء 🟢" if chosen["القوة"] > 0 else "بيع 🔴"
        st.sidebar.success(
            f"🎯 **{chosen['العملة']}** ({next_idx + 1}/{len(top_candidates)}) — "
            f"{d_txt} ({int(abs(chosen['القوة']))}/100) | {chosen['التوافق']}"
        )
        st.sidebar.dataframe(rdf[["العملة", "القوة", "الأخبار", "التوافق"]], use_container_width=True, hide_index=True)

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

# اللوحة الرئيسية
st.title("🧭 مكتب التداول الذكي — 9 مدارس احترافية + تصفية الأخبار (USDT)")

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
elif decision == "SELL":
    sig_label = f"بيع (SELL) 🔴 | {abs(score)}/100"
    sig_color = "#dc3545"
else:
    sig_label = f"ترقب ⏳ | {score:+d}"
    sig_color = "#6c757d"

with top_l:
    st.caption(f"📡 **{data_source}** | تحديث: **{last_update}** | الفريم: **{timeframe}** | ADX: **{adx:.1f}**")

st.markdown(
    f'<div style="background-color: {news_info["color"]}; padding: 8px 14px; border-radius: 8px; '
    f'color: white; font-weight: bold; margin-bottom: 10px;">'
    f'📰 الأخبار: {news_info["status"]} ({news_info["score"]:+d}) | '
    f'📊 المدارس الفنية: {analysis["bull_schools"]} شراء / {analysis["bear_schools"]} بيع ({analysis["tech_score"]:+d})</div>',
    unsafe_allow_html=True,
)

if analysis["conflict"]:
    st.warning(f"⚖️ **خلاصة الأفضلية للتداول:** {analysis['verdict_note']}")
elif analysis["aligned"]:
    st.success(f"✅ **خلاصة الأفضلية للتداول:** {analysis['verdict_note']}")
else:
    st.info(f"🧭 **خلاصة الأفضلية للتداول:** {analysis['verdict_note']}")

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"سعر {symbol}", format_price(price), f"VWAP: {format_price(analysis['vwap'])}")
c2.metric("MFI / RSI", f"{mfi:.0f} / {rsi:.0f}")
c3.metric("حجم الصفقة", f"{pos_usdt:,.2f} USDT", f"مخاطرة {risk_usdt:,.2f} USDT")

with c4:
    st.markdown(
        f'<div style="background-color: {sig_color}; padding: 12px; border-radius: 10px; '
        f'text-align: center; color: white; font-weight: bold; font-size: 15px;">{sig_label}</div>',
        unsafe_allow_html=True,
    )

with st.expander("📋 تفاصيل المدارس الـ 9 والأخبار", expanded=False):
    for r_item in analysis["reasons"]:
        st.write(f"• {r_item}")

st.markdown("---")

if not st.session_state.trade_active:
    st.subheader(f"🚀 إعداد وتنفيذ الصفقة — {symbol}")

    # زر التبديل اليدوي بين التلقائي / شراء / بيع
    trade_override = st.radio(
        "🔄 اختر اتجاه الصفقة (يمكنك تغييره يدوياً بين شراء أو بيع):",
        options=["🤖 تلقائي حسب البوت", "🟢 شراء (BUY)", "🔴 بيع (SELL)"],
        horizontal=True,
        key=f"dir_override_{symbol}",
    )

    if trade_override == "🟢 شراء (BUY)":
        is_sell = False
        exec_tag = "🟢 شراء (تحديد يدوي)"
    elif trade_override == "🔴 بيع (SELL)":
        is_sell = True
        exec_tag = "🔴 بيع (تحديد يدوي)"
    else:
        is_sell = (decision == "SELL") or (decision == "NEUTRAL" and score < 0)
        if decision == "BUY":
            exec_tag = "🟢 شراء (توصية البوت)"
        elif decision == "SELL":
            exec_tag = "🔴 بيع (توصية البوت)"
        else:
            exec_tag = "🔴 بيع (ترقب)" if is_sell else "🟢 شراء (ترقب)"

    if is_sell:
        sl_price = price + sl_dist
        tp1_price = price - (sl_dist * 1.5)
        tp2_price = price - (sl_dist * 2.5)
        sl_txt = f"+{sl_pct:.2f}%"
        tp1_txt = f"-{sl_pct * 1.5:.2f}%"
        tp2_txt = f"-{sl_pct * 2.5:.2f}%"
    else:
        sl_price = price - sl_dist
        tp1_price = price + (sl_dist * 1.5)
        tp2_price = price + (sl_dist * 2.5)
        sl_txt = f"-{sl_pct:.2f}%"
        tp1_txt = f"+{sl_pct * 1.5:.2f}%"
        tp2_txt = f"+{sl_pct * 2.5:.2f}%"

    coins_est = pos_usdt / price if price > 0 else 0.0
    est_loss = abs(price - sl_price) * coins_est
    est_tp1 = abs(tp1_price - price) * coins_est
    est_tp2 = abs(tp2_price - price) * coins_est

    p1, p2, p3, p4 = st.columns(4)
    p1.info(f"**الدخول ({'بيع 🔴' if is_sell else 'شراء 🟢'}):**\n\n{format_price(price)}")
    p2.warning(f"**الوقف ({sl_txt}):**\n\n{format_price(sl_price)}\n\nخسارة محتملة: -{est_loss:,.2f} USDT")
    p3.success(f"**الهدف 1 ({tp1_txt}):**\n\n{format_price(tp1_price)}\n\nربح محتمل: +{est_tp1:,.2f} USDT")
    p4.success(f"**الهدف 2 ({tp2_txt}):**\n\n{format_price(tp2_price)}\n\nربح محتمل: +{est_tp2:,.2f} USDT")

    if st.button(f"✅ بدء الصفقة ({exec_tag}) — {pos_usdt:,.2f} USDT", type="primary", use_container_width=True):
        st.session_state.trade_active = True
        st.session_state.entry_price = price
        st.session_state.stop_loss = sl_price
        st.session_state.take_profit_1 = tp1_price
        st.session_state.take_profit_2 = tp2_price
        st.session_state.position_size_usdt = pos_usdt
        st.session_state.coins_bought = pos_usdt / price
        st.session_state.trade_symbol = symbol
        st.session_state.trade_type = "بيع" if is_sell else "شراء"
        st.session_state.breakeven_triggered = False
        st.rerun()

else:
    t_type = st.session_state.trade_type
    entry = st.session_state.entry_price
    coins = st.session_state.coins_bought
    pos_usdt = st.session_state.position_size_usdt
    tp1 = st.session_state.take_profit_1
    tp2 = st.session_state.take_profit_2

    active_sym = st.session_state.trade_symbol or symbol
    if active_sym == symbol:
        live_price = price
        live_decision = decision
    else:
        adf, _ = fetch_usdt_ohlcv(active_sym, interval=timeframe, limit=120)
        aind = compute_nine_schools_indicators(adf)
        anews = fetch_brief_news_signal(active_sym)
        ares = evaluate_nine_schools(aind, len(aind) - 1, news_info=anews)
        live_price = ares["price"]
        live_decision = ares["decision"]

    if auto_advance:
        if t_type == "شراء":
            if live_price >= entry + (tp1 - entry) * 0.55 and not st.session_state.breakeven_triggered:
                st.session_state.stop_loss = max(st.session_state.stop_loss, entry * 1.001)
                st.session_state.breakeven_triggered = True
            if live_price >= tp1 and live_price > entry:
                st.session_state.stop_loss = max(st.session_state.stop_loss, live_price - (sl_dist * 0.85))
        else:
            if live_price <= entry - (entry - tp1) * 0.55 and not st.session_state.breakeven_triggered:
                st.session_state.stop_loss = min(st.session_state.stop_loss, entry * 0.999)
                st.session_state.breakeven_triggered = True
            if live_price <= tp1 and live_price < entry:
                st.session_state.stop_loss = min(st.session_state.stop_loss, live_price + (sl_dist * 0.85))

    sl = st.session_state.stop_loss

    if t_type == "بيع":
        pnl_usdt = (entry - live_price) * coins
        pnl_pct = ((entry - live_price) / entry) * 100.0 if entry > 0 else 0.0
        hit_sl = live_price >= sl
        hit_tp1 = live_price <= tp1
        hit_tp2 = live_price <= tp2
        opp_sig = live_decision == "BUY"
    else:
        pnl_usdt = (live_price - entry) * coins
        pnl_pct = ((live_price - entry) / entry) * 100.0 if entry > 0 else 0.0
        hit_sl = live_price <= sl
        hit_tp1 = live_price >= tp1
        hit_tp2 = live_price >= tp2
        opp_sig = live_decision == "SELL"

    st.subheader(f"📡 متابعة الصفقة النشطة: {active_sym} ({t_type}) | {pos_usdt:,.2f} USDT")

    if hit_sl:
        render_glowing_alert(
            "تنبيه خروج فوري: السعر وصل إلى وقف الخسارة! اضغط (خروج الآن) لإغلاق الصفقة.",
            bg_color="#dc3545",
            glow_color="rgba(255, 59, 48, 0.95)",
        )
    elif hit_tp2:
        render_glowing_alert(
            "تنبيه جني أرباح مضيء: تحقق الهدف الثاني (TP2)! اضغط (خروج الآن) لتثبيت الربح.",
            bg_color="#198754",
            glow_color="rgba(40, 167, 69, 0.95)",
        )
    elif opp_sig:
        render_glowing_alert(
            "تنبيه انعكاس إشارة: الاتجاه انعكس ضد صفقتك! يُنصح بالخروج الآن.",
            bg_color="#d97706",
            glow_color="rgba(245, 158, 11, 0.95)",
        )
    elif hit_tp1:
        st.success("🎯 تحقق الهدف الأول (TP1) — الصفقة تتقدم نحو الهدف الثاني.")
    else:
        st.info(f"🟢 الصفقة نشطة — السعر الحالي لـ {active_sym}: {format_price(live_price)}")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("الدخول", format_price(entry))
    m2.metric("الربح / الخسارة", f"{pnl_usdt:,.2f} USDT", f"{pnl_pct:.2f}%")
    m3.metric("الوقف", format_price(sl))
    m4.metric("الهدف 1", format_price(tp1))
    m5.metric("الهدف 2", format_price(tp2))

    if st.button("🚨 خروج الآن", type="primary", use_container_width=True):
        st.session_state.trade_history.append({
            "الوقت": datetime.now().strftime("%H:%M:%S"),
            "الزوج": active_sym,
            "النوع": t_type,
            "الدخول": round(entry, 4 if entry < 10 else 2),
            "الخروج": round(live_price, 4 if live_price < 10 else 2),
            "النتيجة (USDT)": round(pnl_usdt, 2),
            "النسبة (%)": round(pnl_pct, 2),
        })
        st.session_state.trade_active = False
        st.rerun()

st.markdown("---")
plot_df = df.tail(60).copy()
plot_df["EMA 9"] = ind_df["ema9"].tail(60)
plot_df["EMA 21"] = ind_df["ema21"].tail(60)
plot_df["VWAP"] = ind_df["vwap"].tail(60)

fig = px.line(plot_df, x="timestamp", y=["close", "EMA 9", "EMA 21", "VWAP"], title=f"الشارت اللحظي — {symbol}")
if st.session_state.trade_active and st.session_state.trade_symbol == symbol:
    fig.add_hline(y=st.session_state.entry_price, line_dash="dash", line_color="blue", annotation_text="دخول")
    fig.add_hline(y=st.session_state.stop_loss, line_dash="dot", line_color="red", annotation_text="وقف")
    fig.add_hline(y=st.session_state.take_profit_1, line_dash="dot", line_color="orange", annotation_text="هدف 1")
    fig.add_hline(y=st.session_state.take_profit_2, line_dash="dot", line_color="green", annotation_text="هدف 2")
st.plotly_chart(fig, use_container_width=True)

if st.session_state.trade_history:
    st.markdown("---")
    st.subheader("📒 سجل الجلسة (USDT)")
    hist_df = pd.DataFrame(st.session_state.trade_history)
    total_pnl = hist_df["النتيجة (USDT)"].sum()
    wins = int((hist_df["النتيجة (USDT)"] > 0).sum())
    win_rate = (wins / len(hist_df)) * 100.0

    s1, s2, s3 = st.columns(3)
    s1.metric("الصفقات", len(hist_df))
    s2.metric("نسبة النجاح", f"{win_rate:.1f}%")
    s3.metric("الصافي", f"{total_pnl:,.2f} USDT")
    st.dataframe(hist_df, use_container_width=True, hide_index=True)
