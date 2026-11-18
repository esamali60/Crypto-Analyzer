import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px

st.set_page_config(page_title="بوت التداول الذكي", layout="wide")

st.title("🤖 بوت تداول العملات الرقمية التفاعلي")
st.markdown("مراقبة لحظية للعملات، حساب المخاطر، وإعطاء إشارات الشراء والبيع بناءً على التحليل الفني.")

# الشريط الجانبي للإعدادات
st.sidebar.header("إعدادات الصفقة")
# استخدام رموز Yahoo Finance مثل BTC-USD
symbol = st.sidebar.text_input("رمز العملة (مثال: BTC-USD أو ETH-USD)", value="BTC-USD").upper()
capital = st.sidebar.number_input("المبلغ المخصص للاستثمار ($)", min_value=10.0, value=500.0, step=50.0)
risk_percentage = st.sidebar.slider("نسبة وقف الخسارة المسموح بها (%)", min_value=1.0, max_value=10.0, value=3.0)

# دالة لجلب البيانات عبر yfinance
@st.cache_data(ttl=60)
def fetch_crypto_data(pair):
    try:
        # جلب البيانات التاريخية للساعة الأخيرة لآخر 5 أيام
        df = yf.download(pair, period="5d", interval="1h", progress=False)
        if df.empty:
            return None
        
        # تنظيم أسماء الأعمدة في حال كانت مصفوفة متعددة المستويات
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.reset_index()
        # توحيد أسماء الأعمدة
        df = df.rename(columns={'Datetime': 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
        return df
    except Exception as e:
        return None

if st.sidebar.button("تشغيل / تحديث التحليل"):
    with st.spinner(f"جاري جلب وتحليل بيانات {symbol}..."):
        df = fetch_crypto_data(symbol)
        
        if df is not None and not df.empty:
            current_price = float(df['close'].iloc[-1])
            
            # حساب المؤشرات الفنية (RSI و Simple Moving Average)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            df['sma_20'] = df['close'].rolling(window=20).mean()
            
            current_rsi = float(df['rsi'].iloc[-1])
            current_sma = float(df['sma_20'].iloc[-1])
            
            # تحديد الإشارة (شراء، بيع، انتظار)
            signal = "انتظار (Neutral)"
            if current_rsi < 35 and current_price > current_sma:
                signal = "شراء (BUY)"
            elif current_rsi > 65 or current_price < current_sma * 0.97:
                signal = "بيع / جني أرباح (SELL)"
                
            # حساب مستويات المخاطر بناءً على رأس المال المخصص
            stop_loss_price = current_price * (1 - (risk_percentage / 100))
            take_profit_price = current_price * (1 + (risk_percentage * 2 / 100))
            allocated_coins = capital / current_price

            # عرض النتائج في واجهة Streamlit
            st.success(f"تم بنجاح تحليل العملة: **{symbol}**")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("السعر الحالي", f"${current_price:,.2f}")
            col2.metric("مؤشر القوة (RSI)", f"{current_rsi:.2f}")
            col3.metric("الكمية المشتراة", f"{allocated_coins:.4f} وحدة")
            col4.metric("الإشارة الحالية", signal)
            
            # قسم إدارة المخاطر وتوصيات فتح الصفقة
            st.markdown("---")
            st.subheader("📊 خطة فتح وإيقاف الصفقة المقترحة")
            
            plan_col1, plan_col2, plan_col3 = st.columns(3)
            with plan_col1:
                st.info(f"**نقطة الدخول (Entry):**\n\n ${current_price:,.2f}")
            with plan_col2:
                st.warning(f"**وقف الخسارة (Stop Loss):**\n\n ${stop_loss_price:,.2f} (-{risk_percentage}%)")
            with plan_col3:
                st.success(f"**هدف الأرباح (Take Profit):**\n\n ${take_profit_price:,.2f} (+{risk_percentage * 2}%)")

            # الرسم البياني لحركة السعر
            st.markdown("---")
            st.subheader(f"📈 رسم بياني لحركة سعر {symbol}")
            fig = px.line(df, x='timestamp', y='close', title=f"حركة سعر {symbol} خلال الفترة الأخيرة")
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.error("تعذر جلب البيانات. تأكد من صحة رمز العملة (مثال: BTC-USD أو ETH-USD).")
else:
    st.info("قم بإدخال رمز العملة والمبلغ في الشريط الجانبي ثم اضغط على زر **تشغيل / تحديث التحليل**.")
