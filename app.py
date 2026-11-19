import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="بوت التداول الخبير + رادار الفرص", layout="wide")

# تهيئة متغيرات الجلسة
if "trade_active" not in st.session_state:
    st.session_state.trade_active = False
if "entry_price" not in st.session_state:
    st.session_state.entry_price = 0.0
if "stop_loss" not in st.session_state:
    st.session_state.stop_loss = 0.0
if "take_profit" not in st.session_state:
    st.session_state.take_profit = 0.0
if "coins_bought" not in st.session_state:
    st.session_state.coins_bought = 0.0
if "trade_symbol" not in st.session_state:
    st.session_state.trade_symbol = ""
if "trade_type" not in st.session_state:
    st.session_state.trade_type = "شراء"
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "BTC-USD"

st.title("🧠 بوت التداول الخبير (تحليل متعدد المؤشرات + رادار الفرص)")

# قائمة العملات التي يفحصها الرادار
WATCHLIST = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "NEAR-USD", "BNB-USD"]

# دالة التحليل الفني المتقدم (عقل الخبير)
def analyze_market_expert(df):
    if df is None or len(df) < 30:
        return None

    close = df['close']
    current_price = float(close.iloc[-1])

    # 1. حساب RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    curr_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

    # 2. المتوسطات الأسية EMA 9 و EMA 21
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    curr_ema9 = float(ema9.iloc[-1])
    curr_ema21 = float(ema21.iloc[-1])

    # 3. مؤشر MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9, adjust=False).mean()
    curr_macd = float(macd.iloc[-1])
    curr_sig = float(signal_line.iloc[-1])

    # 4. قنوات بولينجر Bollinger Bands
    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    upper_band = float((sma20 + (std20 * 2)).iloc[-1])
    lower_band = float((sma20 - (std20 * 2)).iloc[-1])

    # نظام النقاط للخبير (من -100 للبيع القوي إلى +100 للشراء القوي)
    score = 0
    reasons = []

    # تحليل الزخم RSI
    if curr_rsi < 35:
        score += 30
        reasons.append("تشبع بيعي قوي (RSI منخفض)")
    elif curr_rsi < 45:
        score += 15
        reasons.append("منطقة تجميع جيدة (RSI)")
    elif curr_rsi > 65:
        score -= 30
        reasons.append("تشبع شرائي مرتفع (RSI)")
    elif curr_rsi > 55:
        score -= 15
        reasons.append("ضعف في زخم الصعود (RSI)")

    # تحليل تقاطع المتوسطات EMA
    if curr_ema9 > curr_ema21:
        score += 25
        reasons.append("اتجاه صاعد قصير المدى (EMA9 > EMA21)")
    else:
        score -= 25
        reasons.append("اتجاه هابط قصير المدى (EMA9 < EMA21)")

    # تحليل الماكد MACD
    if curr_macd > curr_sig:
        score += 25
        reasons.append("تقاطع إيجابي للماكد (MACD)")
    else:
        score -= 25
        reasons.append("تقاطع سلبي للماكد (MACD)")

    # تحليل بولينجر باند
    if current_price <= lower_band * 1.005:
        score += 20
        reasons.append("ارتداد من الحد السفلي لبولينجر")
    elif current_price >= upper_band * 0.995:
        score -= 20
        reasons.append("ملامسة القمة السعرية لبولينجر")

    # تحديد القرار النهائي
    if score >= 30:
        decision = "BUY"
        label = f"شراء قوي (قوة الإشارة {score}%)"
    elif score <= -30:
        decision = "SELL"
        label = f"بيع قوي (قوة الإشارة {abs(score)}%)"
    else:
        decision = "NEUTRAL"
        label = f"ترقب / تذبذب ({score})"

    return {
        "price": current_price,
        "rsi": curr_rsi,
        "score": score,
        "decision": decision,
        "label": label,
        "reasons": reasons,
        "ema9": ema9,
        "ema21": ema21
    }

def fetch_live_data(pair, period="1d", interval="5m"):
    try:
        df = yf.download(pair, period=period, interval=interval, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        df = df.rename(columns={'Datetime': 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
        return df
    except Exception:
        return None

# ==========================================
# الشريط الجانبي للإعدادات + رادار الفرص
# ==========================================
st.sidebar.header("📡 رادار اقتناص الفرص الحية")
if st.sidebar.button("🔍 ابحث لي عن أفضل عملة الآن", type="primary", use_container_width=True):
    with st.sidebar.status("جاري مسح السوق وتحليل 10 عملات..."):
        best_coin = None
        highest_abs_score = 0
        scan_results = []

        for coin in WATCHLIST:
            d = fetch_live_data(coin, period="1d", interval="5m")
            res = analyze_market_expert(d)
            if res:
                scan_results.append((coin, res['decision'], res['score'], res['price']))
                if abs(res['score']) > highest_abs_score:
                    highest_abs_score = abs(res['score'])
                    best_coin = (coin, res)

        if best_coin and highest_abs_score >= 30:
            coin_name, coin_data = best_coin
            st.session_state.selected_symbol = coin_name
            action_ar = "شراء 🟢" if coin_data['decision'] == "BUY" else "بيع 🔴"
            st.sidebar.success(f"🎯 **أفضل فرصة الآن: {coin_name}**\n\nالتوصية: **{action_ar}** بقوة **{abs(coin_data['score'])}%**")
        else:
            st.sidebar.warning("السوق هادئ حالياً، لا توجد عملة وصلت لقوة إشارة عالية. جرب التحديث بعد قليل.")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ إعدادات الصفقة")
symbol = st.sidebar.text_input("رمز العملة", value=st.session_state.selected_symbol).upper()
st.session_state.selected_symbol = symbol
capital = st.sidebar.number_input("المبلغ المخصص ($)", min_value=10.0, value=500.0, step=50.0)
timeframe = st.sidebar.selectbox("الإطار الزمني للتحليل", options=["1m", "5m", "15m"], index=1, help="إطار 5 دقائق يعطي إشارات أدق وأقل ضوضاء من الدقيقة الواحدة")
risk_percentage = st.sidebar.slider("نسبة وقف الخسارة (%)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)
refresh_rate = st.sidebar.selectbox("سرعة التحديث اللحظي (ثانية)", options=[10, 15, 30, 60], index=1)

# ==========================================
# لوحة التداول اللحظية
# ==========================================
@st.fragment(run_every=refresh_rate)
def live_trading_dashboard():
    df = fetch_live_data(symbol, period="1d", interval=timeframe)
    
    if df is None or df.empty:
        st.error(f"تعذر جلب البيانات للعملة {symbol}. تأكد من كتابة الرمز بشكل صحيح (مثل SOL-USD أو BTC-USD).")
        return

    analysis = analyze_market_expert(df)
    if not analysis:
        st.warning("البيانات غير كافية للتحليل الفني حالياً.")
        return

    current_price = analysis['price']
    current_rsi = analysis['rsi']
    decision = analysis['decision']
    score = analysis['score']
    last_update = datetime.now().strftime("%H:%M:%S")

    if decision == "BUY":
        signal_text = f"شراء (BUY) 🟢 | قوة {score}%"
        signal_color = "#28a745"
        btn_color_class = "🟢 شراء"
    elif decision == "SELL":
        signal_text = f"بيع (SELL) 🔴 | قوة {abs(score)}%"
        signal_color = "#dc3545"
        btn_color_class = "🔴 بيع"
    else:
        signal_text = f"انتظار (تذبذب) ⏳ | {score}"
        signal_color = "#ffc107"
        btn_color_class = "🟡 دخول حذر (شراء)"

    st.caption(f"🔄 آخر تحديث للسعر: **{last_update}** | الإطار الزمني: **{timeframe}** (يتحدث تلقائياً كل {refresh_rate} ثانية)")

    # عرض المؤشرات الرئيسية
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"سعر {symbol}", f"${current_price:,.4f}" if current_price < 10 else f"${current_price:,.2f}")
    col2.metric("مؤشر القوة (RSI)", f"{current_rsi:.2f}")
    col3.metric("الكمية المتاحة", f"{(capital / current_price):.4f}")
    
    with col4:
        st.markdown(f"""
        <div style="background-color: {signal_color}; padding: 12px; border-radius: 8px; text-align: center; color: white; font-weight: bold; font-size: 16px; box-shadow: 0px 0px 12px {signal_color};">
            {signal_text}
        </div>
        """, unsafe_allow_html=True)

    # عرض أسباب قرار الخبير
    with st.expander("📋 تفاصيل قراءة الخبير للمؤشرات الأربعة (اضغط للعرض)", expanded=True):
        st.write(" • ".join([f"**{r}**" for r in analysis['reasons']]))

    st.markdown("---")

    # ==========================================
    # قسم التحكم في الصفقة ومراقبة الإيقاف
    # ==========================================
    if not st.session_state.trade_active:
        st.subheader(f"🚀 بدء صفقة جديدة على {symbol}")
        
        is_sell = (decision == "SELL")
        if is_sell:
            suggested_sl = current_price * (1 + (risk_percentage / 100))
            suggested_tp = current_price * (1 - (risk_percentage * 2 / 100))
            sl_label = f"+{risk_percentage}%"
            tp_label = f"-{risk_percentage * 2}%"
        else:
            suggested_sl = current_price * (1 - (risk_percentage / 100))
            suggested_tp = current_price * (1 + (risk_percentage * 2 / 100))
            sl_label = f"-{risk_percentage}%"
            tp_label = f"+{risk_percentage * 2}%"

        fmt = "${:,.4f}" if current_price < 10 else "${:,.2f}"
        c1, c2, c3 = st.columns(3)
        c1.info(f"**سعر الدخول المتوقع:** {fmt.format(current_price)}")
        c2.warning(f"**وقف الخسارة ({sl_label}):** {fmt.format(suggested_sl)}")
        c3.success(f"**هدف الربح ({tp_label}):** {fmt.format(suggested_tp)}")

        if st.button(f"✅ بدء الصفقة الآن ({btn_color_class})", type="primary", use_container_width=True):
            st.session_state.trade_active = True
            st.session_state.entry_price = current_price
            st.session_state.stop_loss = suggested_sl
            st.session_state.take_profit = suggested_tp
            st.session_state.coins_bought = capital / current_price
            st.session_state.trade_symbol = symbol
            st.session_state.trade_type = "بيع" if is_sell else "شراء"
            st.rerun()

    else:
        # مراقبة الصفقة الحية
        t_type = st.session_state.trade_type
        st.subheader(f"📡 مراقبة الصفقة الحية: {st.session_state.trade_symbol} ({t_type})")
        
        entry = st.session_state.entry_price
        sl = st.session_state.stop_loss
        tp = st.session_state.take_profit
        coins = st.session_state.coins_bought
        
        if t_type == "بيع":
            pnl_dollar = (entry - current_price) * coins
            pnl_percent = ((entry - current_price) / entry) * 100
            hit_stop_loss = current_price >= sl
            hit_take_profit = current_price <= tp
        else:
            pnl_dollar = (current_price - entry) * coins
            pnl_percent = ((current_price - entry) / entry) * 100
            hit_stop_loss = current_price <= sl
            hit_take_profit = current_price >= tp

        if hit_stop_loss:
            st.error("🚨 **تنبيه وقف الخسارة!** السعر وصل لحد الخسارة. اضغط على **خروج الآن**.")
        elif hit_take_profit:
            st.success("🎉 **تنبيه جني الأرباح!** الصفقة حققت الهدف. اضغط على **خروج الآن**.")
        elif (t_type == "شراء" and decision == "SELL") or (t_type == "بيع" and decision == "BUY"):
            st.warning("⚠️ **تنبيه انعكاس الاتجاه!** مؤشرات الخبير انعكست ضد صفقتك، يُنصح بالخروج وتأمين الرصيد.")
        else:
            st.info("🟢 **الصفقة مستمرة بأمان...** المؤشرات ما زالت داعمة لاتجاه صفقتك.")

        fmt = "${:,.4f}" if entry < 10 else "${:,.2f}"
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("سعر الدخول", fmt.format(entry))
        m2.metric("الربح / الخسارة", f"${pnl_dollar:,.2f}", f"{pnl_percent:.2f}%")
        m3.metric("وقف الخسارة", fmt.format(sl))
        m4.metric("هدف الربح", fmt.format(tp))

        if st.button("🚨 خروج الآن (إغلاق الصفقة وتصفيتها)", type="primary", use_container_width=True):
            st.session_state.trade_active = False
            st.rerun()

    # الرسم البياني مع المتوسطات الأسية
    st.markdown("---")
    plot_df = df.tail(60).copy()
    plot_df['EMA 9'] = analysis['ema9'].tail(60)
    plot_df['EMA 21'] = analysis['ema21'].tail(60)
    
    fig = px.line(plot_df, x='timestamp', y=['close', 'EMA 9', 'EMA 21'], title=f"الشارت اللحظي مع متوسطات الخبير - {symbol}")
    if st.session_state.trade_active:
        fig.add_hline(y=st.session_state.entry_price, line_dash="dash", line_color="blue", annotation_text="دخول")
        fig.add_hline(y=st.session_state.stop_loss, line_dash="dot", line_color="red", annotation_text="وقف الخسارة")
        fig.add_hline(y=st.session_state.take_profit, line_dash="dot", line_color="green", annotation_text="هدف الربح")
    st.plotly_chart(fig, use_container_width=True)

live_trading_dashboard()
