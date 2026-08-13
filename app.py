import streamlit as st
import pandas as pd
import ta
from textblob import TextBlob
import yfinance as yf

# إعداد الصفحة لتكون واسعة
st.set_page_config(page_title="المحلل الذكي الشامل", layout="wide")

# --- 1. البنر العلوي ---
st.markdown("""
    <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 15px; text-align: center; border-radius: 10px; margin-bottom: 20px;">
        <p style="color: #888; font-size: 14px; margin: 0;"><script> atOptions = { 'key' : '9a374e1ba3c8e64316b7e2eb29f45a7a', 'format' : 'iframe', 'height' : 90, 'width' : 728, 'params' : {} }; </script> <script src="https://www.highperformanceformat.com/9a374e1ba3c8e64316b7e2eb29f45a7a/invoke.js"></script></p>
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

def get_market_news(symbol):
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        if not news: return None
        return [{'title': i.get('title'), 'link': i.get('link', '#')} for i in news if i.get('title')]
    except: return None

# --- تقسيم الصفحة ---
col_main, col_ads = st.columns([3, 1])

with col_main:
    st.title("🚀 المحلل الذكي الشامل")
    market_type = st.selectbox("اختر نوع السوق:", ["العملات الرقمية 🪙", "الأسهم العالمية 🏢"])
    
    if market_type == "العملات الرقمية 🪙":
        symbol = st.selectbox("اختر العملة:", ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "BNB-USD"])
    else:
        symbol = st.selectbox("اختر الشركة:", ["AAPL", "TSLA", "NVDA", "AMZN", "MSFT", "GOOGL"])

    if st.button("بدء التحليل الفني 🔍"):
        with st.spinner('جاري التحليل...'):
            df = get_market_data(symbol)
            news = get_market_news(symbol)
            
            if df is not None:
                price, rsi, sup, res = analyze_technical(df)
                c1, c2 = st.columns(2)
                c1.metric("السعر الحالي", f"${price:,.2f}")
                c2.metric("مؤشر RSI", f"{rsi:.2f}")
                
                # --- تعديل نقاط الدخول لتظهر أسفل بعضها ---
                st.subheader("🎯 أقرب نقاط الدخول المقترحة:")
                st.write(f"🟢 **نقطة الدخول شراء (دعم):** ${sup:,.2f}")
                st.write(f"🔴 **نقطة الدخول بيع (مقاومة):** ${res:,.2f}")
                
                st.subheader("📰 أحدث الأخبار الاقتصادية:")
                if news:
                    for item in news[:5]:
                        st.markdown(f"🔗 [{item['title']}]({item['link']})")
                else: st.warning("لا توجد أخبار اقتصادية متاحة حالياً.")
            else: st.error("فشل في جلب البيانات.")

with col_ads:
    st.subheader("📢 إعلانات")
    st.markdown("""
        <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 20px; border-radius: 10px; height: 500px; color: #888; text-align: center;">
            <p><script> atOptions = { 'key' : '04e5cc65f1f9df82e44cdac786768a40', 'format' : 'iframe', 'height' : 250, 'width' : 300, 'params' : {} }; </script> <script src="https://www.highperformanceformat.com/04e5cc65f1f9df82e44cdac786768a40/invoke.js"></script></p>
        </div>
    """, unsafe_allow_html=True)
