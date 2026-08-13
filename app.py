import streamlit as st
import pandas as pd
import ta
from textblob import TextBlob
import yfinance as yf

# إعداد الصفحة
st.set_page_config(page_title="المحلل الذكي الشامل", layout="centered")

# --- 1. البنر العلوي ---
st.markdown("""
    <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 15px; text-align: center; border-radius: 10px; margin-bottom: 20px;">
        <p style="color: #888; font-size: 14px; margin: 0;">مساحة إعلانية علوية</p>
    </div>
""", unsafe_allow_html=True)

# --- الدوال البرمجية ---
def get_market_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df.rename(columns={'Open': 'open', 'Close': 'close', 'High': 'high', 'Low': 'low', 'Volume': 'volume'}, inplace=True)
        return df
    except: return None

def analyze_technical(df):
    rsi = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    return df['close'].iloc[-1], rsi.iloc[-1], bb.bollinger_lband().iloc[-1], bb.bollinger_hband().iloc[-1]

# --- الواجهة الرئيسية مع القوائم المنسدلة ---
st.title("🚀 المحلل الذكي الشامل")

market_type = st.selectbox("اختر نوع السوق:", ["العملات الرقمية 🪙", "الأسهم العالمية 🏢"])

# تعريف القوائم المنسدلة للأصول
if market_type == "العملات الرقمية 🪙":
    symbol = st.selectbox("اختر العملة:", ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "BNB-USD"])
else:
    symbol = st.selectbox("اختر الشركة:", ["AAPL", "TSLA", "NVDA", "AMZN", "MSFT", "GOOGL"])

if st.button("بدء التحليل الفني 🔍"):
    with st.spinner('جاري معالجة البيانات...'):
        df = get_market_data(symbol)
        
        if df is not None:
            price, rsi, sup, res = analyze_technical(df)
            c1, c2 = st.columns(2)
            c1.metric("السعر الحالي", f"${price:,.2f}")
            c2.metric("مؤشر RSI", f"{rsi:.2f}")
            
            st.subheader("📊 حالة السوق الفنية:")
            if rsi <= 30: st.success("الأصل في قاع (تشبع بيعي) 🟢")
            elif rsi >= 70: st.error("الأصل في قمة (تشبع شرائي) 🔴")
            else: st.warning("السعر في مسار محايد ⚪")
            
            st.markdown("---")
            st.subheader("🎯 أقرب نقاط الدخول المقترحة:")
            st.write(f"**🟢 نقطة الدعم (شراء):** ${sup:,.2f}")
            st.write(f"**🔴 نقطة المقاومة (بيع):** ${res:,.2f}")
        else:
            st.error("عذراً، لم نتمكن من جلب بيانات لهذا الرمز.")
