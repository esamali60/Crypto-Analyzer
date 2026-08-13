import streamlit as st
import pandas as pd
import ta
from textblob import TextBlob
import yfinance as yf

# إعداد الصفحة
st.set_page_config(page_title="المحلل الذكي الشامل", layout="wide")

# --- البنر العلوي ---
st.markdown("""
    <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 15px; text-align: center; border-radius: 10px; margin-bottom: 20px;">
        <p style="color: #888; font-size: 14px; margin: 0;">مساحة إعلانية علوية</p>
    </div>
""", unsafe_allow_html=True)

# --- الدوال البرمجية ---
def get_market_data(symbol):
    try:
        ticker = yf.Ticker(symbol.upper())
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
        ticker = yf.Ticker(symbol.upper())
        news = ticker.news
        return [{'title': i.get('title'), 'link': i.get('link', '#')} for i in news if i.get('title')]
    except: return None

# --- الواجهة الرئيسية ---
col_main, col_ads = st.columns([3, 1])

with col_main:
    st.title("🚀 المحلل الذكي الشامل")
    
    # 1. اختيار السوق
    market_type = st.selectbox("اختر نوع السوق:", ["العملات الرقمية 🪙", "الأسهم العالمية 🏢"])
    
    # 2. مربع بحث حر (يدعم أي رمز)
    manual_symbol = st.text_input("أدخل رمز العملة أو السهم يدوياً (مثال: BTC-USD أو AAPL):")
    
    # 3. قائمة اختيار سريعة
    if not manual_symbol:
        if market_type == "العملات الرقمية 🪙":
            symbol = st.selectbox("أو اختر من القائمة:", ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "BNB-USD"])
        else:
            symbol = st.selectbox("أو اختر من القائمة:", ["AAPL", "TSLA", "NVDA", "AMZN", "MSFT", "GOOGL"])
    else:
        symbol = manual_symbol

    if st.button("بدء التحليل الفني 🔍"):
        with st.spinner('جاري جلب البيانات...'):
            df = get_market_data(symbol)
            news = get_market_news(symbol)
            
            if df is not None:
                price, rsi, sup, res = analyze_technical(df)
                c1, c2 = st.columns(2)
                c1.metric("السعر الحالي", f"${price:,.2f}")
                c2.metric("مؤشر RSI", f"{rsi:.2f}")
                
                st.subheader("🎯 أقرب نقاط الدخول المقترحة:")
                st.write(f"🟢 **نقطة الدخول شراء (دعم):** ${sup:,.2f}")
                st.write(f"🔴 **نقطة الدخول بيع (مقاومة):** ${res:,.2f}")
                
                st.subheader("📰 أحدث الأخبار الاقتصادية:")
                if news:
                    for item in news[:5]:
                        st.markdown(f"🔗 [{item['title']}]({item['link']})")
                else: st.warning("لا توجد أخبار اقتصادية متاحة حالياً.")
            else: st.error("عذراً، لم يتم العثور على بيانات لهذا الرمز. تأكد من كتابته بشكل صحيح.")

with col_ads:
    st.subheader("📢 إعلانات")
    st.markdown("""
        <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 20px; border-radius: 10px; height: 500px; color: #888; text-align: center;">
            <p>ضع كود الإعلان الجانبي هنا</p>
        </div>
    """, unsafe_allow_html=True)
