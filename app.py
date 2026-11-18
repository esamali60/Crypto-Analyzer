import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="بوت التداول الذكي", layout="wide")

st.title("🤖 بوت تداول العملات الرقمية التفاعلي")
st.markdown("مراقبة اللحظية للعملات، حساب المخاطر، وإعطاء إشارات الشراء والبيع بناءً على التحليل الفني.")

# الشريط الجانبي للإعدادات
st.sidebar.header("إعدادات الصفقة")
symbol = st.sidebar.text_input("اسم العملة (مثال: BTCUSDT أو ETHUSDT)", value="BTCUSDT").upper()
capital = st.sidebar.number_input("المبلغ المخصص للاستثمار ($)", min_value=10.0, value=500.0, step=50.0)
risk_percentage = st.sidebar.slider("نسبة وقف الخسارة المسموح بها (%)", min_value=1.0, max_value=10.0, value=3.0)

# دالة لجلب البيانات التاريخية واللحظية من Binance API (عامة ومجانية)
@st.cache_data(ttl=60)
def fetch_crypto_data(pair):
    url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval=1h&limit=100"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    else:
        return None

if st.sidebar.button("تشغيل / تحديث التحليل"):
    with st.spinner(f"جاري جلب وتحليل بيانات {symbol}..."):
        df = fetch_crypto_data(symbol)
        
        if df is not None and not df.empty:
            current_price = df['close'].iloc[-1]
            
            # حساب المؤشرات الفنية (RSI و Simple Moving Average)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            df['sma_20'] = df['close'].rolling(window=20).mean()
            
            current_rsi = df['rsi'].iloc[-1]
            current_sma = df['sma_20'].iloc[-1]
            
            # تحديد الإشارة (شراء، بيع، انتظار)
            signal = "انتظار (Neutral)"
            color = "orange"
            if current_rsi < 35 and current_price > current_sma:
                signal = "شراء (BUY)"
                color = "green"
            elif current_rsi > 65 or current_price < current_sma * 0.97:
                signal = "بيع / جني أرباح (SELL)"
                color = "red"
                
            # حساب مستويات المخاطر بناءً على رأس المال المخصص
            stop_loss_price = current_price * (1 - (risk_percentage / 100))
            take_profit_price = current_price * (1 + (risk_percentage * 2 / 100)) # نسبة المخاطرة للعائد 1:2
            allocated_coins = capital / current_price

            # عرض النتائج في واجهة Streamlit
            st.success(تم بنجاح تحليل العملة: **{symbol}**)
            
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
            st.subheader("📈 رسم بياني لحركة السعر وإغلاقات آخر الساعات")
            fig = px.line(df, x='timestamp', y='close', title=f"حركة سعر {symbol} خلال الفترة الأخيرة")
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.error("تعذر جلب البيانات. تأكد من صحة اسم العملة (مثال: BTCUSDT أو ADAUSDT).")
else:
    st.info("قم بإدخال بيانات العملة والمبلغ في الشريط الجانبي ثم اضغط على زر **تشغيل / تحديث التحليل**.")
