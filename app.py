import streamlit as st
import pandas as pd
import ta
from textblob import TextBlob
import yfinance as yf

# إعداد الصفحة لتكون واسعة (Wide) لتناسب الإعلانات
st.set_page_config(page_title="المحلل الذكي الشامل", layout="wide")

# --- 1. البنر العلوي (Header) ---
st.markdown("""
    <div style="background-color: #f0f2f6; padding: 20px; text-align: center; border-radius: 10px; margin-bottom: 20px;">
        <h3><script src="https://pl30828515.effectivecpmnetwork.com/ef/a6/00/efa600e9f6c186772834551c15b76c98.js"></script></h3>
        <p style="font-size: 0.8em; color: #555;">هنا يظهر إعلانك العلوي</p>
    </div>
""", unsafe_allow_html=True)

# --- دوال التحليل والبيانات ---
def get_market_data(symbol):
    try:
        ticker = yf.Ticker(symbol.replace(" ", "").upper())
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

def analyze_news_sentiment(text):
    try:
        pol = TextBlob(text).sentiment.polarity
        return "إيجابي 🟢" if pol > 0.05 else "سلبي 🔴" if pol < -0.05 else "محايد ⚪"
    except: return "محايد ⚪"

def get_market_news(symbol):
    try:
        news = yf.Ticker(symbol.upper()).news
        return [{'title': i.get('title'), 'link': i.get('link', '#')} for i in news[:5]]
    except: return None

# --- تقسيم الصفحة (الوسط للتحليل، اليمين للإعلانات) ---
col_main, col_ads = st.columns([3, 1])

with col_main:
    st.title("🚀 المحلل الذكي الشامل")
    market = st.radio("اختر السوق:", ["العملات الرقمية 🪙", "الأسهم العالمية 🏢"])
    user_symbol = st.text_input("أدخل رمز الأصل (مثل BTC-USD أو AAPL):", "BTC-USD" if market == "العملات الرقمية 🪙" else "AAPL")

    if st.button("تحليل شامل الآن 🔍"):
        with st.spinner('جاري التحليل...'):
            df = get_market_data(user_symbol)
            news = get_market_news(user_symbol)
            
            if df is not None:
                price, rsi, sup, res = analyze_technical(df)
                c1, c2 = st.columns(2)
                c1.metric("السعر الحالي", f"${price:,.2f}")
                c2.metric("مؤشر RSI", f"{rsi:.2f}")
                
                st.subheader("📊 حالة السوق:")
                st.write(f"**نقطة الدعم (شراء):** ${sup:,.2f} | **نقطة المقاومة (بيع):** ${res:,.2f}")
                
                st.subheader("📰 أحدث الأخبار:")
                if news:
                    for item in news:
                        st.markdown(f"{analyze_news_sentiment(item['title'])} | [{item['title']}]({item['link']})")
                else: st.info("لا توجد أخبار حالياً.")
            else: st.error("تأكد من صحة الرمز.")

with col_ads:
    st.subheader("إعلانات 📢")
    st.markdown("""
        <div style="background-color: #262730; padding: 20px; border-radius: 10px; height: 500px; color: white;">
            <p><script>
  atOptions = {
    'key' : '04e5cc65f1f9df82e44cdac786768a40',
    'format' : 'iframe',
    'height' : 250,
    'width' : 300,
    'params' : {}
  };
</script>
<script src="https://www.highperformanceformat.com/04e5cc65f1f9df82e44cdac786768a40/invoke.js"></script>
</p>
            <p style="font-size: 0.8em; color: gray;">ضع كود الإعلان الخاص بك هنا</p>
        </div>
    """, unsafe_allow_html=True)
