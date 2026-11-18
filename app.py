import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="بوت التداول اللحظي الذكي", layout="wide")

# تهيئة متغيرات الجلسة لحفظ حالة الصفقة المفتوحة
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
        # جلب بيانات دقيقة واحدة لآخر يوم للحصول على أحدث سعر لحظي
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

# جزء يتحدث تلقائياً بشكل لحظي
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

    # تحديد إشارة الدخول/الخروج الفنية
    signal = "انتظار (Neutral) ⏳"
    if current_rsi < 35 and current_price > current_sma:
        signal = "شراء الآن (BUY) 🟢"
    elif current_rsi > 65 or current_price < current_sma * 0.985:
        signal = "بيع / خروج (SELL) 🔴"

    st.caption(f"🔄 آخر تحديث لحظي للسعر: **{last_update}** (يتحدث تلقائياً كل {refresh_rate} ثانية)")

    # عرض المؤشرات الرئيسية
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("السعر اللحظي", f"${current_price:,.2f}")
    col2.metric("مؤشر القوة (RSI)", f"{current_rsi:.2f}")
    col3.metric("الكمية المتاحة للشراء", f"{(capital / current_price):.4f}")
    col4.metric("إشارة البوت الحالية", signal)

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

        if st.button("✅ تم بدء الصفقة (تفعيل المراقبة الحية)", type="primary", use_container_width=True):
            st.session_state.trade_active = True
            st.session_state.entry_price = current_price
            st.session_state.stop_loss = suggested_sl
            st.session_state.take_profit = suggested_tp
            st.session_state.coins_bought = capital / current_price
            st.session_state.trade_symbol = symbol
            st.rerun()

    else:
        # في حال وجود صفقة مفتوحة حالياً
        st.subheader(f"📡 مراقبة الصفقة الحية للعملة: {st.session_state.trade_symbol}")
        
        entry = st.session_state.entry_price
        sl = st.session_state.stop_loss
        tp = st.session_state.take_profit
        coins = st.session_state.coins_bought
        
        current_value = coins * current_price
        pnl_dollar = current_value - capital
        pnl_percent = ((current_price - entry) / entry) * 100

        # التحقق من شروط إيقاف الصفقة وإعطاء التنبيه
        if current_price <= sl:
            st.error("🚨 **تنبيه إيقاف الصفقة فوراً (STOP LOSS)!** السعر وصل إلى حد وقف الخسارة. قم بالبيع الآن لحماية رأس مالك.")
        elif current_price >= tp:
            st.success("🎉 **تنبيه جني الأرباح (TAKE PROFIT)!** الصفقة حققت الهدف المطلوب. يُنصح بإغلاق الصفقة وجني الربح الآن.")
        elif "SELL" in signal:
            st.warning("⚠️ **إشارة خروج فنية (SELL)!** المؤشرات الفنية تشير إلى انعكاس السعر وهبوطه، يفضل إغلاق الصفقة الآن.")
        else:
            st.info("🟢 **الصفقة مستمرة بأمان...** السعر يتحرك ضمن النطاق الآمن ولم يصل لنقطة الإيقاف بعد.")

        # عرض تفاصيل الصفقة الحية
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("سعر الدخول", f"${entry:,.2f}")
        m2.metric("الربح / الخسارة اللحظي", f"${pnl_dollar:,.2f}", f"{pnl_percent:.2f}%")
        m3.metric("حد وقف الخسارة", f"${sl:,.2f}")
        m4.metric("هدف جني الربح", f"${tp:,.2f}")

        if st.button("🛑 تم إغلاق الصفقة (إنهاء المراقبة)", use_container_width=True):
            st.session_state.trade_active = False
            st.rerun()

    # الرسم البياني اللحظي
    st.markdown("---")
    fig = px.line(df.tail(60), x='timestamp', y='close', title=f"حركة السعر اللحظية (آخر 60 دقيقة) - {symbol}")
    if st.session_state.trade_active:
        fig.add_hline(y=st.session_state.entry_price, line_dash="dash", line_color="blue", annotation_text="نقطة الدخول")
        fig.add_hline(y=st.session_state.stop_loss, line_dash="dot", line_color="red", annotation_text="وقف الخسارة")
        fig.add_hline(y=st.session_state.take_profit, line_dash="dot", line_color="green", annotation_text="هدف الربح")
    st.plotly_chart(fig, use_container_width=True)

# تشغيل لوحة المراقبة الحية
live_trading_dashboard()
