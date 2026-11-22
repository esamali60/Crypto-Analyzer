import streamlit as st
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import plotly.express as px
import xml.etree.ElementTree as ET
from datetime import datetime
import re

st.set_page_config(page_title="بوت التداول الذاتي (مدارس + أخبار آلية)", layout="wide")

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
    "trade_history": [],
    "breakeven_triggered": False,
    "auto_paused": False,
    "pause_reason": ""
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.title("🤖 بوت التداول الذاتي المتطور (9 مدارس فنية + تحليل أخبار آلي)")

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

HIGH_RISK_SHOCK_WORDS = [
    "hack", "hacked", "exploit", "crash", "plunge", "ban", "banned", "liquidation", "emergency"
]

def format_price(val):
    return f"{val:,.4f} USDT" if abs(val) < 10 else f"{val:,.2f} USDT"

def normalize_symbol_to_usdt(raw_sym):
    s = raw_sym.strip().upper().replace("-USD", "").replace("/USDT", "").replace("-", "")
    if not s.endswith("USDT"):
        s = f"{s}USDT"
    return s

@st.cache_data(ttl=180)
def fetch_auto_news_sentiment(symbol_usdt):
    base_coin = symbol_usdt.replace("USDT", "").lower()
    feeds = [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss"
    ]
    headlines = []
    news_score = 0
    shock_detected = False
    shock_title = ""

    for feed_url in feeds:
        try:
            resp = requests.get(feed_url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and resp.text:
                root = ET.fromstring(resp.text)
                for item in root.findall(".//item")[:12]:
                    title_el = item.find("title")
                    if title_el is not None and title_el.text:
                        title = re.sub(r"\s+", " ", title_el.text.strip())
                        t_low = title.lower()
                        weight = 1.5 if (base_coin in t_low or "bitcoin" in t_low or "crypto" in t_low or "fed" in t_low or "market" in t_low) else 0.75

                        pos_hits = sum(1 for w in BULLISH_KEYWORDS if w in t_low)
                        neg_hits = sum(1 for w in BEARISH_KEYWORDS if w in t_low)
                        shock_hits = sum(1 for w in HIGH_RISK_SHOCK_WORDS if w in t_low)

                        delta_s = (pos_hits - neg_hits) * 4.0 * weight
                        news_score += delta_s

                        if shock_hits > 0 and neg_hits > 0 and not shock_detected:
                            shock_detected = True
                            shock_title = title

                        headlines.append((title, round(delta_s, 1)))
        except Exception:
            continue

    news_score = int(max(-25, min(25, round(news_score))))
    return {
        "score": news_score,
        "shock": shock_detected,
        "shock_title": shock_title,
        "count": len(headlines),
        "top_items": headlines[:5]
    }

def fetch_usdt_ohlcv(symbol_usdt, interval="5m", limit=150):
    sym = normalize_symbol_to_usdt(symbol_usdt)

    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}"
        r = requests.get(url, timeout=5)
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
                return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].dropna().reset_index(drop=True), "Binance"
    except Exception:
        pass

    try:
        base = sym.replace("USDT", "")
        kc_pair = f"{base}-USDT"
        kc_map = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1hour"}
        kc_tf = kc_map.get(interval, "5min")
        url_kc = f"https://api.kucoin.com/api/v1/market/candles?type={kc_tf}&symbol={kc_pair}"
        r_kc = requests.get(url_kc, timeout=5)
        if r_kc.status_code == 200:
            res_json = r_kc.json()
            if res_json.get("code") == "200000" and res_json.get("data"):
                raw = res_json["data"][:limit][::-1]
                df = pd.DataFrame(raw, columns=['timestamp', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
                df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='s')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].dropna().reset_index(drop=True), "KuCoin"
    except Exception:
        pass

    try:
        base = sym.replace("USDT", "")
        yf_pair = f"{base}-USD"
        period = "5d" if interval in ["5m", "15m", "1h"] else "1d"
        df = yf.download(yf_pair, period=period, interval=interval, progress=False)
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
            if len(df) > 20:
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

def autonomous_expert_decision(ind_df, idx, htf_bias=0, news_info=None):
    if news_info is None:
        news_info = {"score": 0, "shock": False, "shock_title": "", "count": 0}

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

    # المدرسة العاشرة: تحليل الأخبار آلياً
    n_score = news_info["score"]
    if n_score > 0:
        score += n_score
        bull_conf += 1
        reasons.append(f"أخبار داعمة آلياً (+{n_score})")
    elif n_score < 0:
        score += n_score
        bear_conf += 1
        reasons.append(f"ضغط أخبار سلبية آلياً ({n_score})")

    if adx < 18:
        score = int(score * 0.55)
        reasons.append(f"ترند عرضي ضعيف (ADX={adx:.1f})")
    elif adx >= 25:
        reasons.append(f"ترند قوي (ADX={adx:.1f})")

    score = max(-100, min(100, score))

    if news_info["shock"]:
        decision = "HOLD_SHOCK"
        quality = "توقف تلقائي بسبب خبر عاجل عالي الخطورة 🚨"
    elif score >= 45 and bull_conf >= 4 and adx >= 18:
        decision = "BUY"
        quality = "فرصة شراء ذهبية مؤيدة بالمدارس والأخبار ⭐⭐⭐"
    elif score <= -45 and bear_conf >= 4 and adx >= 18:
        decision = "SELL"
        quality = "فرصة بيع ذهبية مؤيدة بالمدارس والأخبار ⭐⭐⭐"
    elif score >= 30:
        decision = "BUY_WEAK"
        quality = "شراء متوسط ⭐"
    elif score <= -30:
        decision = "SELL_WEAK"
        quality = "بيع متوسط ⭐"
    else:
        decision = "NEUTRAL"
        quality = "انتظار — البوت يراقب ولا يغامر"

    return {
        "price": price, "rsi": rsi, "mfi": mfi, "adx": adx, "atr": atr, "vwap": vwap,
        "score": score, "decision": decision, "quality": quality,
        "bull_conf": bull_conf, "bear_conf": bear_conf, "reasons": reasons
    }

def get_htf_bias_usdt(symbol_usdt):
    df_1h, _ = fetch_usdt_ohlcv(symbol_usdt, interval="1h", limit=60)
    if df_1h is None or len(df_1h) < 30:
        return "غير محدد", 0
    ema20 = df_1h['close'].ewm(span=20, adjust=False).mean()
    ema50 = df_1h['close'].ewm(span=50, adjust=False).mean()
    c = float(df_1h['close'].iloc[-1])
    e20 = float(ema20.iloc[-1])
    e50 = float(ema50.iloc[-1])
    if c > e20 > e50:
        return "صاعد على فريم الساعة 🟢", 1
    elif c < e20 < e50:
        return "هابط على فريم الساعة 🔴", -1
    return "متذبذب على فريم الساعة 🟡", 0

# الشريط الجانبي
st.sidebar.header("📡 رادار الفرص الذهبية (USDT)")
if st.sidebar.button("🔍 افحص 12 عملة واقتنص أقوى فرصة", type="primary", use_container_width=True):
    with st.sidebar.status("البوت يحلل المؤشرات والأخبار آلياً..."):
        ranked = []
        for coin in WATCHLIST_USDT:
            d, _ = fetch_usdt_ohlcv(coin, interval="5m", limit=100)
            if d is not None and len(d) >= 40:
                ind_d = compute_expert_indicators(d)
                _, bias = get_htf_bias_usdt(coin)
                n_info = fetch_auto_news_sentiment(coin)
                res = autonomous_expert_decision(ind_d, len(ind_d) - 1, htf_bias=bias, news_info=n_info)
                ranked.append({
                    "العملة": coin,
                    "القوة": res['score'],
                    "أخبار": n_info['score'],
                    "ADX": round(res['adx'], 1),
                    "القرار": res['decision'],
                    "الجودة": res['quality']
                })

        if ranked:
            rdf = pd.DataFrame(ranked)
            rdf['abs_s'] = rdf['القوة'].abs()
            rdf = rdf.sort_values(by='abs_s', ascending=False).reset_index(drop=True)
            top = rdf.iloc[0]

            if top['القرار'] == "HOLD_SHOCK":
                st.sidebar.error("🚨 تم رصد خبر عاجل عالي الخطورة؛ البوت يوصي بالتوقف المؤقت حالياً.")
            elif top['abs_s'] >= 30:
                st.session_state.selected_symbol = top['العملة']
                d_txt = "شراء 🟢" if top['القوة'] > 0 else "بيع 🔴"
                st.sidebar.success(
                    f"🏆 **أفضل فرصة الآن: {top['العملة']}**\n\n"
                    f"الاتجاه: **{d_txt}** | التقييم: **{int(top['abs_s'])}/100**\n\n"
                    f"{top['الجودة']}"
                )
            else:
                st.sidebar.warning("السوق في حالة ترقب ولا توجد فرصة عالية الدقة الآن.")

            st.sidebar.dataframe(rdf[['العملة', 'القوة', 'أخبار', 'ADX']].head(6), use_container_width=True, hide_index=True)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ إعدادات الصفقة وإدارة رأس المال")
raw_input = st.sidebar.text_input("رمز العملة (USDT)", value=st.session_state.selected_symbol)
symbol = normalize_symbol_to_usdt(raw_input)
st.session_state.selected_symbol = symbol

capital_usdt = st.sidebar.number_input("إجمالي رأس المال (USDT)", min_value=10.0, value=500.0, step=50.0)
max_risk_pct = st.sidebar.slider("المخاطرة القصوى في الصفقة (%)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)
sl_mode = st.sidebar.radio("حساب وقف الخسارة", options=["ذكي حسب التقلب (ATR)", "نسبة ثابتة (%)"], index=0)
fixed_sl_pct = st.sidebar.slider("نسبة وقف الخسارة الثابتة (%)", min_value=0.5, max_value=10.0, value=1.5, step=0.5)
auto_advance_and_pause = st.sidebar.checkbox("تفعيل القرار الذاتي لتقدّم وتوقّف الصفقة", value=True)
timeframe = st.sidebar.selectbox("الإطار الزمني", options=["1m", "5m", "15m"], index=1)
refresh_rate = st.sidebar.selectbox("سرعة التحديث (ثانية)", options=[10, 15, 30, 60], index=1)

# لوحة التداول اللحظية الذاتية
@st.fragment(run_every=refresh_rate)
def live_trading_dashboard():
    df, data_source = fetch_usdt_ohlcv(symbol, interval=timeframe, limit=150)
    if df is None or len(df) < 40:
        st.error(f"تعذر جلب بيانات كافية للزوج {symbol}.")
        return

    ind_df = compute_expert_indicators(df)
    htf_text, htf_bias = get_htf_bias_usdt(symbol)
    news_info = fetch_auto_news_sentiment(symbol)
    analysis = autonomous_expert_decision(ind_df, len(ind_df) - 1, htf_bias=htf_bias, news_info=news_info)

    price = analysis['price']
    rsi = analysis['rsi']
    mfi = analysis['mfi']
    adx = analysis['adx']
    atr = analysis['atr']
    score = analysis['score']
    decision = analysis['decision']
    last_update = datetime.now().strftime("%H:%M:%S")

    if sl_mode == "ذكي حسب التقلب (ATR)" and atr > 0:
        sl_dist = max(atr * 2.0, price * 0.005)
        sl_pct = (sl_dist / price) * 100.0
    else:
        sl_pct = fixed_sl_pct
        sl_dist = price * (sl_pct / 100.0)

    risk_usdt = capital_usdt * (max_risk_pct / 100.0)
    pos_usdt = min(capital_usdt, risk_usdt / (sl_pct / 100.0))

    if decision == "HOLD_SHOCK":
        sig_label = "توقف تلقائي (خبر عاجل) 🚨"
        sig_color = "#842029"
        btn_tag = "🚨 خطر إخباري"
    elif decision == "BUY":
        sig_label = f"شراء قوي (BUY) 🟢 | {score}/100"
        sig_color = "#198754"
        btn_tag = "🟢 شراء مؤكد"
    elif decision == "BUY_WEAK":
        sig_label = f"شراء متوسط 🟢 | {score}/100"
        sig_color = "#20c997"
        btn_tag = "🟢 شراء متوسط"
    elif decision == "SELL":
        sig_label = f"بيع قوي (SELL) 🔴 | {abs(score)}/100"
        sig_color = "#dc3545"
        btn_tag = "🔴 بيع مؤكد"
    elif decision == "SELL_WEAK":
        sig_label = f"بيع متوسط 🔴 | {abs(score)}/100"
        sig_color = "#fd7e14"
        btn_tag = "🔴 بيع متوسط"
    else:
        sig_label = f"انتظار ذكي ⏳ | {score}"
        sig_color = "#6c757d"
        btn_tag = "🟡 دخول حذر"

    st.caption(
        f"📡 المصدر: **{data_source}** | آخر تحديث: **{last_update}** | الفريم: **{timeframe}** | "
        f"الاتجاه العام: **{htf_text}** | مؤشر الأخبار الآلي: **{news_info['score']:+d}**"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"سعر {symbol}", format_price(price), f"VWAP: {format_price(analysis['vwap'])}")
    c2.metric("السيولة (MFI) / الزخم (RSI)", f"{mfi:.0f} / {rsi:.0f}")
    c3.metric("حجم الصفقة المقترح", f"{pos_usdt:,.2f} USDT", f"مخاطرة قصوى {risk_usdt:,.2f} USDT")

    with c4:
        st.markdown(f"""
        <div style="background-color: {sig_color}; padding: 12px; border-radius: 10px; text-align: center; color: white; font-weight: bold; font-size: 15px; box-shadow: 0px 0px 12px {sig_color};">
            {sig_label}<br><span style="font-size: 12px; font-weight: normal;">{analysis['quality']}</span>
        </div>
        """, unsafe_allow_html=True)

    with st.expander(f"🧠 قراءة البوت الذاتية (المدارس + الأخبار | {analysis['bull_conf']} إيجابية / {analysis['bear_conf']} سلبية)", expanded=True):
        st.write(" • ".join([f"**{r}**" for r in analysis['reasons']]))
        if news_info["shock"] and news_info["shock_title"]:
            st.error(f"📰 **خبر صادم مرصود آلياً:** {news_info['shock_title']}")

    st.markdown("---")

    if not st.session_state.trade_active:
        st.subheader(f"🚀 إعداد الصفقة الجديدة على {symbol}")
        is_sell = decision in ["SELL", "SELL_WEAK"]

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

        p1, p2, p3, p4 = st.columns(4)
        p1.info(f"**سعر الدخول:**\n\n{format_price(price)}")
        p2.warning(f"**وقف الخسارة ({sl_txt}):**\n\n{format_price(sl_price)}")
        p3.success(f"**الهدف الأول ({tp1_txt}):**\n\n{format_price(tp1_price)}")
        p4.success(f"**الهدف الثاني ({tp2_txt}):**\n\n{format_price(tp2_price)}")

        if st.button(f"✅ بدء الصفقة الآن ({btn_tag}) بمبلغ {pos_usdt:,.2f} USDT", type="primary", use_container_width=True):
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
            st.session_state.auto_paused = False
            st.session_state.pause_reason = ""
            st.rerun()

    else:
        t_type = st.session_state.trade_type
        entry = st.session_state.entry_price
        coins = st.session_state.coins_bought
        pos_usdt = st.session_state.position_size_usdt
        tp1 = st.session_state.take_profit_1
        tp2 = st.session_state.take_profit_2

        # القرار الذاتي لتقدّم الصفقة وتأمينها أو إيقافها
        advanced_note = ""
        st.session_state.auto_paused = False
        st.session_state.pause_reason = ""

        if auto_advance_and_pause:
            if t_type == "شراء":
                # تقدّم الصفقة وتأمينها تلقائياً
                if price >= entry + (tp1 - entry) * 0.55 and not st.session_state.breakeven_triggered:
                    st.session_state.stop_loss = max(st.session_state.stop_loss, entry * 1.001)
                    st.session_state.breakeven_triggered = True
                    advanced_note = " — تم تأمين الوقف فوق نقطة الدخول تلقائياً"
                # دفع الوقف للأمام عند دعم الأخبار الإيجابية أو اختراق TP1
                if (news_info["score"] >= 8 or price >= tp1) and price > entry:
                    pushed_sl = max(st.session_state.stop_loss, price - (sl_dist * 0.85))
                    if pushed_sl > st.session_state.stop_loss:
                        st.session_state.stop_loss = pushed_sl
                        advanced_note = " — البوت يدفع الصفقة للأمام نحو الهدف الثاني"

                # شروط التوقف الذاتي
                if news_info["shock"] or news_info["score"] <= -12:
                    st.session_state.auto_paused = True
                    st.session_state.pause_reason = "خبر اقتصادي/سوقي سلبي قوي؛ البوت يوصي بتوقف الصفقة فوراً."
                elif decision in ["SELL", "SELL_WEAK"] and score <= -35:
                    st.session_state.auto_paused = True
                    st.session_state.pause_reason = "انعكاس فني وإخباري ضد صفقة الشراء؛ البوت يوصي بالإغلاق."
            else:
                if price <= entry - (entry - tp1) * 0.55 and not st.session_state.breakeven_triggered:
                    st.session_state.stop_loss = min(st.session_state.stop_loss, entry * 0.999)
                    st.session_state.breakeven_triggered = True
                    advanced_note = " — تم تأمين الوقف تحت نقطة الدخول تلقائياً"
                if (news_info["score"] <= -8 or price <= tp1) and price < entry:
                    pushed_sl = min(st.session_state.stop_loss, price + (sl_dist * 0.85))
                    if pushed_sl < st.session_state.stop_loss:
                        st.session_state.stop_loss = pushed_sl
                        advanced_note = " — البوت يدفع صفقة البيع للأمام نحو الهدف الثاني"

                if news_info["shock"] or news_info["score"] >= 12:
                    st.session_state.auto_paused = True
                    st.session_state.pause_reason = "خبر إيجابي مفاجئ ضد صفقة البيع؛ البوت يوصي بتوقف الصفقة فوراً."
                elif decision in ["BUY", "BUY_WEAK"] and score >= 35:
                    st.session_state.auto_paused = True
                    st.session_state.pause_reason = "انعكاس فني وإخباري ضد صفقة البيع؛ البوت يوصي بالإغلاق."

        sl = st.session_state.stop_loss

        if t_type == "بيع":
            pnl_usdt = (entry - price) * coins
            pnl_pct = ((entry - price) / entry) * 100.0
            hit_sl = price >= sl
            hit_tp1 = price <= tp1
            hit_tp2 = price <= tp2
        else:
            pnl_usdt = (price - entry) * coins
            pnl_pct = ((price - entry) / entry) * 100.0
            hit_sl = price <= sl
            hit_tp1 = price >= tp1
            hit_tp2 = price >= tp2

        st.subheader(f"📡 متابعة الصفقة الذاتية: {st.session_state.trade_symbol} ({t_type}) | {pos_usdt:,.2f} USDT")

        if hit_sl:
            st.error("🚨 **توقّف الصفقة (وقف الخسارة)!** السعر بلغ مستوى الإيقاف. اضغط **خروج الآن**.")
        elif st.session_state.auto_paused:
            st.error(f"🛑 **قرار توقّف ذاتي من البوت:** {st.session_state.pause_reason} اضغط **خروج الآن**.")
        elif hit_tp2:
            st.success("🏆 **تحقق الهدف الثاني (TP2)!** يُنصح بإغلاق الصفقة وجني الأرباح الآن.")
        elif hit_tp1:
            st.success(f"🎯 **تحقق الهدف الأول (TP1)!** الصفقة تتقدم نحو الهدف الثاني{advanced_note}.")
        else:
            st.info(f"🟢 **الصفقة تتقدم تحت المراقبة الذاتية...**{advanced_note}")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("الدخول", format_price(entry))
        m2.metric("الربح / الخسارة", f"{pnl_usdt:,.2f} USDT", f"{pnl_pct:.2f}%")
        m3.metric("الوقف الحالي", format_price(sl))
        m4.metric("الهدف 1", format_price(tp1))
        m5.metric("الهدف 2", format_price(tp2))

        if st.button("🚨 خروج الآن (إغلاق الصفقة وتسجيل النتيجة)", type="primary", use_container_width=True):
            st.session_state.trade_history.append({
                "الوقت": datetime.now().strftime("%H:%M:%S"),
                "الزوج": st.session_state.trade_symbol,
                "النوع": t_type,
                "الدخول": round(entry, 4 if entry < 10 else 2),
                "الخروج": round(price, 4 if price < 10 else 2),
                "النتيجة (USDT)": round(pnl_usdt, 2),
                "النسبة (%)": round(pnl_pct, 2)
            })
            st.session_state.trade_active = False
            st.session_state.auto_paused = False
            st.rerun()

    st.markdown("---")
    plot_df = df.tail(65).copy()
    plot_df['EMA 9'] = ind_df['ema9'].tail(65)
    plot_df['EMA 21'] = ind_df['ema21'].tail(65)
    plot_df['EMA 50'] = ind_df['ema50'].tail(65)
    plot_df['VWAP'] = ind_df['vwap'].tail(65)

    fig = px.line(
        plot_df, x='timestamp', y=['close', 'EMA 9', 'EMA 21', 'EMA 50', 'VWAP'],
        title=f"الشارت اللحظي (المتوسطات + سيولة VWAP) — {symbol}"
    )
    if st.session_state.trade_active:
        fig.add_hline(y=st.session_state.entry_price, line_dash="dash", line_color="blue", annotation_text="دخول")
        fig.add_hline(y=st.session_state.stop_loss, line_dash="dot", line_color="red", annotation_text="وقف الخسارة")
        fig.add_hline(y=st.session_state.take_profit_1, line_dash="dot", line_color="orange", annotation_text="هدف 1")
        fig.add_hline(y=st.session_state.take_profit_2, line_dash="dot", line_color="green", annotation_text="هدف 2")
    st.plotly_chart(fig, use_container_width=True)

    if st.session_state.trade_history:
        st.markdown("---")
        st.subheader("📒 سجل صفقات الجلسة (USDT)")
        hist_df = pd.DataFrame(st.session_state.trade_history)
        total_pnl = hist_df["النتيجة (USDT)"].sum()
        wins = int((hist_df["النتيجة (USDT)"] > 0).sum())
        win_rate = (wins / len(hist_df)) * 100.0

        s1, s2, s3 = st.columns(3)
        s1.metric("الصفقات المغلقة", len(hist_df))
        s2.metric("نسبة النجاح (Win Rate)", f"{win_rate:.1f}%")
        s3.metric("صافي الجلسة", f"{total_pnl:,.2f} USDT")
        st.dataframe(hist_df, use_container_width=True, hide_index=True)

live_trading_dashboard()
