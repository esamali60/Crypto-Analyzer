import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="بوت التداول اللحظي الذكي", layout="wide")

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

st.title("🤖 بوت التداول اللحظي ومراقبة الصفقات")

# الشريط الجانبي للإعدادات
st.sidebar.header("⚙️ إعدادات الصفقة")
symbol = st.sidebar.text_input("رمز العملة (مثال: BTC-USD أو ETH-USD)", value="BTC-USD").upper()
capital = st.sidebar.number_input("المبلغ المخصص ($)", min_value=10.0, value=500.0, step=50.0)
risk_percentage = st.sidebar.slider("نسبة وقف الخسارة (%)", min_value=1.0, max_value=10.0, value=3.0)
refresh_rate = st.sidebar.selectbox("سرعة التحديث اللحظي (بالثواني)", options=[10, 15, 30, 60], index=1)

# دالة جلب البيانات اللحظية
def fetch_live_data(pair):
    try:
        df = yf.download(pair, period="1d", interval="1m", progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        df = df.rename(columns={'Datetime': 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
        return df
    except Exception:
        return None

# جزء التحديث اللحظي التلقائي
@st.fragment(run_every=refresh_rate)
def live_trading_dashboard():
    df = fetch_live_data(symbol)
    
    if df is None or df.empty:
        st.error(f"تعذر جلب البيانات اللحظية للعملة {symbol}. تأكد من الرمز (مثل BTC-USD).")
        return

    current_price = float(df['close'].iloc[-1])
    last_update = datetime.now().strftime("%H:%M:%S")

    # حساب المؤشرات الفنية (RSI و SMA)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['sma_20'] = df['close'].rolling(window=20).mean()

    current_rsi = float(df['rsi'].iloc[-1]) if not pd.isna(df['rsi'].iloc[-1]) else 50.0
    current_sma = float(df['sma_20'].iloc[-1]) if not pd.isna(df['sma_20'].iloc[-1]) else current_price

    # تحديد إشارة البوت الفنية بدقة
    is_buy_signal = current_rsi < 35 and current_price > current_sma
    is_sell_signal = current_rsi > 65 or current_price < current_sma * 0.985

    if is_buy_signal:
        signal_text = "شراء (BUY) 🟢"
        signal_color = "#28a745" # أخضر
    elif is_sell_signal:
        signal_text = "بيع / خروج (SELL) 🔴"
        signal_color = "#dc3545" # أحمر
    else:
        signal_text = "انتظار (Neutral) ⏳"
        signal_color = "#ffc107" # أصفر/برتقالي

    st.caption(f"🔄 آخر تحديث للسعر: **{last_update}** (يتحدث تلقائياً كل {refresh_rate} ثانية)")

    # عرض المؤشرات الرئيسية مع مؤشر الحالة المضيء
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("السعر اللحظي", f"${current_price:,.2f}")
    col2.metric("مؤشر القوة (RSI)", f"{current_rsi:.2f}")
    col3.metric("الكمية المتاحة للشراء", f"{(capital / current_price):.4f}")
    
    # عرض إشارة البوت مع المصباح اللوني المضيء
    with col4:
        st.markdown(f"""
        <div style="background-color: {signal_color}; padding: 10px; border-radius: 8px; text-align: center; color: white; font-weight: bold; font-size: 16px; box-shadow: 0px 0px 10px {signal_color};">
            إشارة البوت: {signal_text}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ==========================================
    # قسم التحكم في الصفقة ومراقبة الإيقاف
    # ==========================================
    if not st.session_state.trade_active:
        st.subheader("🚀 بدء صفقة جديدة")
        suggested_sl = current_price * (1 - (risk_percentage / 100))
        suggested_tp = current_price * (1 + (risk_percentage * 2 / 100))

        c1, c2, c3 = st.columns(3)
        c1.info(f"**سعر الدخول المتوقع:** ${current_price:,.2f}")
        c2.warning(f"**وقف الخسارة المقترح:** ${suggested_sl:,.2f}")
        c3.success(f"**هدف الربح المقترح:** ${suggested_tp:,.2f}")

        # التحقق من حالة الإشارة قبل السماح ببدء الصفقة
        if is_sell_signal:
            st.error("⚠️ **لا يمكن بدء صفقة جديدة:** الإشارة الحالية هي **بيع/خروج**. انتظر حتى تتحول الإشارة إلى شراء أخضر.")
            st.button("🚫 بدء الصفقة معطل (الإشارة بيع)", disabled=True, use_container_width=True)
        else:
            if st.button("✅ تم بدء الصفقة (تفعيل المراقبة الحية)", type="primary", use_container_width=True):
                st.session_state.trade_active = True
                st.session_state.entry_price = current_price
                st.session_state.stop_loss = suggested_sl
                st.session_state.take_profit = suggested_tp
                st.session_state.coins_bought = capital / current_price
                st.session_state.trade_symbol = symbol
                st.rerun()

    else:
        # مراقبة الصفقة الحية
        st.subheader(f"📡 مراقبة الصفقة الحية للعملة: {st.session_state.trade_symbol}")
        
        entry = st.session_state.entry_price
        sl = st.session_state.stop_loss
        tp = st.session_state.take_profit
        coins = st.session_state.coins_bought
        
        current_value = coins * current_price
        pnl_dollar = current_value - capital
        pnl_percent = ((current_price - entry) / entry) * 100

        # فحص شروط إنهاء الصفقة (وقف الخسارة أو جني الأرباح)
        hit_stop_loss = current_price <= sl
        hit_take_profit = current_price >= tp

        if hit_stop_loss:
            st.error("🚨 **تنبيه خطير - وقف الخسارة!** السعر وصل إلى حد وقف الخسارة. اضغط على زر **خروج الآن** فوراً لحماية رصيدك.")
        elif hit_take_profit:
            st.success("🎉 **مبروك - هدف الأرباح تحقق!** وصل السعر لهدف الربح المطلوب. اضغط على زر **خروج الآن** لجني الأرباح.")
        elif is_sell_signal:
            st.warning("⚠️ **إشارة انعكاس (بيع)!** المؤشرات تحولت إلى البيع، يفضل إغلاق الصفقة.")
        else:
            st.info("🟢 **الصفقة مستمرة بأمان...** جاري متابعة السعر لحظياً.")

        # عرض تفاصيل الصفقة الحية
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("سعر الدخول", f"${entry:,.2f}")
        m2.metric("الربح / الخسارة", f"${pnl_dollar:,.2f}", f"{pnl_percent:.2f}%")
        m3.metric("وقف الخسارة", f"${sl:,.2f}")
        m4.metric("هدف الربح", f"${tp:,.2f}")

        # زر واضح جداً للخروج الآن عند انتهاء الربح أو الخسارة
        if st.button("🚨 خروج الآن (إغلاق الصفقة وتصفيتها)", type="primary", use_container_width=True):
            st.session_state.trade_active = False
            st.rerun()

    # الرسم البياني اللحظي مع الخطوط التوجيهية
    st.markdown("---")
    fig = px.line(df.tail(60), x='timestamp', y='close', title=f"حركة السعر اللحظية (آخر 60 دقيقة) - {symbol}")
    if st.session_state.trade_active:
        fig.add_hline(y=st.session_state.entry_price, line_dash="dash", line_color="blue", annotation_text="دخول")
        fig.add_hline(y=st.session_state.stop_loss, line_dash="dot", line_color="red", annotation_text="وقف الخسارة")
        fig.add_hline(y=st.session_state.take_profit, line_dash="dot", line_color="green", annotation_text="هدف الربح")
    st.plotly_chart(fig, use_container_width=True)

# تشغيل اللوحة
live_trading_dashboard()
