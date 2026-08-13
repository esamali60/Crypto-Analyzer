import streamlit as st
import pandas as pd
import ta
from textblob import TextBlob
import yfinance as yf

# إعداد الصفحة لتكون واسعة (Wide) لتناسب الإعلانات والتنسيق الاحترافي
st.set_page_config(page_title="المحلل الذكي الشامل", layout="wide")

# --- 1. البنر العلوي للإعلانات (Header) ---
st.markdown("""
    <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 15px; text-align: center; border-radius: 10px; margin-bottom: 20px;">
        <p style="color: #888; font-size: 14px; margin: 0;"><script> atOptions = { 'key' : '9a374e1ba3c8e64316b7e2eb29f45a7a', 'format' : 'iframe', 'height' : 90, 'width' : 728, 'params' : {} }; </script> <script src="https://www.highperformanceformat.com/9a374e1ba3c8e64316b7e2eb29f45a7a/invoke.js"></script></p>
    </div>
""", unsafe_allow_html=True)

# --- الدوال البرمجية لجلب البيانات وتحليلها ---
def get_market_data(symbol):
    """دالة لجلب بيانات الأسهم والعملات من Yahoo Finance"""
    try:
        ticker = yf.Ticker(symbol.replace(" ", "").upper())
        df = ticker.history(period="1mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df.rename(columns={'Open': 'open', 'Close': 'close', 'High': 'high', 'Low': 'low', 'Volume': 'volume'}, inplace=True)
        return df
    except: return None

def analyze_technical(df):
    """دالة حساب مؤشر القوة النسبية RSI وحدود بولينجر"""
    rsi = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    return df['close'].iloc[-1], rsi.iloc[-1], bb.bollinger_lband().iloc[-1], bb.bollinger_hband().iloc[-1]

def analyze_news_sentiment(text):
    """دالة تحليل مشاعر الخبر (إيجابي، سلبي، محايد)"""
    try:
        if not text or not isinstance(text, str):
            return "محايد ⚪"
        pol = TextBlob(text).sentiment.polarity
        if pol > 0.05: return "إيجابي 🟢"
        elif pol < -0.05: return "سلبي 🔴"
        return "محايد ⚪"
    except:
        return "محايد ⚪"

def get_market_news(symbol):
    """دالة لجلب الأخبار الحقيقية وتصفيتها لتجنب الروابط الفارغة"""
    try:
        ticker = yf.Ticker(symbol.upper())
        news = ticker.news
        news_list = []
        if news and isinstance(news, list):
            for i in news:
                title = i.get('title')
                link = i.get('link')
                if title and link and title != "None" and link != "None":
                    news_list.append({'title': str(title), 'link': str(link)})
        return news_list[:5] if news_list else None
    except: 
        return None

# --- تقسيم الصفحة إلى عمودين (اليسار/الوسط للمحتوى، اليمين للإعلانات) ---
col_main, col_ads = st.columns([3, 1])

with col_main:
    st.title("🚀 المحلل الذكي الشامل")
    market = st.radio("اختر السوق:", ["العملات الرقمية 🪙", "الأسهم العالمية 🏢"])
    
    default_symbol = "BTC-USD" if market == "العملات الرقمية 🪙" else "AAPL"
    user_symbol = st.text_input("أدخل رمز الأصل (مثال: AAPL للأسهم، أو BTC-USD للعملات):", default_symbol)

    if st.button("تحليل شامل الآن 🔍"):
        with st.spinner('جاري جلب البيانات وتحليل السوق...'):
            df = get_market_data(user_symbol)
            news = get_market_news(user_symbol)
            
            if df is not None:
                price, rsi, sup, res = analyze_technical(df)
                
                # عرض المؤشرات الأساسية
                c1, c2 = st.columns(2)
                c1.metric("السعر الحالي", f"${price:,.2f}")
                c2.metric("مؤشر RSI", f"{rsi:.2f}")
                
                st.subheader("📊 حالة السوق الفنية:")
                if rsi <= 30: 
                    st.success("الأصل في قاع (تشبع بيعي) - احتمالية الصعود أعلى 🟢")
                elif rsi >= 70: 
                    st.error("الأصل في قمة (تشبع شرائي) - احتمالية الهبوط أعلى 🔴")
                else: 
                    st.warning("السعر في مسار محايد ومستقر ⚪")
                
                # --- العرض المنظم والقديم لنقاط الدخول في أسطر منفصلة ---
                st.markdown("---")
                st.subheader("🎯 أقرب نقاط الدخول المقترحة:")
                st.write(f"**🟢 نقطة الدخول شراء (صعود - دعم):** بالقرب من مستوى السعر **${sup:,.2f}**")
                st.write(f"**🔴 نقطة الدخول بيع (هبوط - مقاومة):** بالقرب من مستوى السعر **${res:,.2f}**")
                
                st.markdown("---")
                st.subheader("📰 أحدث الأخبار وتأثيرها:")
                if news:
                    for item in news:
                        sentiment = analyze_news_sentiment(item['title'])
                        st.markdown(f"**{sentiment}** | [{item['title']}]({item['link']})")
                else: 
                    st.info("لا توجد أخبار حقيقية متوفرة لهذا الرمز حالياً.")
            else: 
                st.error("عذراً، لم نتمكن من جلب بيانات لهذا الرمز. تأكد من صحة كتابته.")

with col_ads:
    st.subheader("📢 إعلانات")
    st.markdown("""
        <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 20px; border-radius: 10px; height: 500px; color: #888; text-align: center;">
            <p style="margin-top: 200px;"><script> atOptions = { 'key' : '04e5cc65f1f9df82e44cdac786768a40', 'format' : 'iframe', 'height' : 250, 'width' : 300, 'params' : {} }; </script> <script src="https://www.highperformanceformat.com/04e5cc65f1f9df82e44cdac786768a40/invoke.js"></script></p>
        </div>
    """, unsafe_allow_html=True)
