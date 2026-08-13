# استدعاء المكتبات البرمجية الأساسية
import streamlit as st
import requests
import pandas as pd
import ta
from textblob import TextBlob
import yfinance as yf

# إعداد واجهة الموقع لتبدو احترافية
st.set_page_config(page_title="المحلل الذكي الشامل", page_icon="📈", layout="centered")

# --- دالة جلب بيانات العملات الرقمية ---
def get_crypto_data(symbol, timeframe="1hour"):
    clean_symbol = symbol.replace(" ", "").replace("/", "-").upper()
    url = f"https://api.kucoin.com/api/v1/market/candles?symbol={clean_symbol}&type={timeframe}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data.get('code') != '200000' or not data.get('data'): return None
        df = pd.DataFrame(data['data'], columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
        df['close'] = df['close'].astype(format=None, errors='ignore').astype(float)
        return df.iloc[::-1].reset_index(drop=True)
    except: return None

# --- دالة جلب بيانات الأسهم ---
def get_stock_data(symbol):
    clean_symbol = symbol.replace(" ", "").upper()
    try:
        ticker = yf.Ticker(clean_symbol)
        df = ticker.history(period="1mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df.rename(columns={'Open': 'open', 'Close': 'close', 'High': 'high', 'Low': 'low', 'Volume': 'volume'}, inplace=True)
        return df
    except: return None

# --- دالة التحليل الفني (RSI + Bollinger Bands) ---
def analyze_technical(df):
    rsi = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    return df['close'].iloc[-1], rsi.iloc[-1], bb.bollinger_lband().iloc[-1], bb.bollinger_hband().iloc[-1]

# --- دالة تحليل مشاعر الأخبار (الذكاء الاصطناعي) ---
def analyze_news_sentiment(text):
    try:
        # التأكد من أن النص عبارة عن سلسلة نصية صحيحة وليست فارغة
        if not text or not isinstance(text, str):
            return "محايد ⚪"
        pol = TextBlob(text).sentiment.polarity
        if pol > 0.05: return "إيجابي 🟢"
        elif pol < -0.05: return "سلبي 🔴"
        return "محايد ⚪"
    except:
        return "محايد ⚪"

# --- دوال جلب الأخبار ---
def get_crypto_news():
    url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers).json()
        articles = res.get('Data', [])
        news_list = []
        for i in articles:
            title = i.get('title')
            url_link = i.get('url')
            if title and url_link:
                news_list.append({'title': str(title), 'url': str(url_link)})
        return news_list[:5] if news_list else None
    except: return None

def get_stock_news(symbol):
    try:
        ticker = yf.Ticker(symbol.upper())
        news = ticker.news
        news_list = []
        if news and isinstance(news, list):
            for i in news:
                title = i.get('title')
                link = i.get('link', '#')
                if title:
                    news_list.append({'title': str(title), 'url': str(link)})
        return news_list[:5] if news_list else None
    except: return None

# --- واجهة الموقع ---
st.title("🚀 المحلل الذكي الشامل للأسواق")
st.write("أداة تحليلية تدمج الأرقام الفنية مع مشاعر الأخبار.")

market = st.radio("اختر السوق:", ["العملات الرقمية 🪙", "الأسهم العالمية 🏢"])
user_symbol = st.text_input("أدخل رمز الأصل (مثل BTC/USDT للعملات، أو AAPL للأسهم):", "BTC/USDT" if market == "العملات الرقمية 🪙" else "AAPL")

if st.button("تحليل شامل الآن 🔍"):
    with st.spinner('جاري معالجة البيانات وتحليل الأخبار...'):
        df = get_crypto_data(user_symbol) if market == "العملات الرقمية 🪙" else get_stock_data(user_symbol)
        news = get_crypto_news() if market == "العملات الرقمية 🪙" else get_stock_news(user_symbol)
        
        if df is not None:
            price, rsi, sup, res = analyze_technical(df)
            col1, col2 = st.columns(2)
            col1.metric("السعر الحالي", f"${price:,.2f}")
            col2.metric("مؤشر RSI", f"{rsi:.2f}")
            
            st.subheader("📊 حالة السوق الفنية:")
            if rsi <= 30: 
                st.success("العملة في قاع (تشبع بيعي) - احتمالية الصعود أعلى 🟢")
            elif rsi >= 70: 
                st.error("العملة في قمة (تشبع شرائي) - احتمالية الهبوط أعلى 🔴")
            else: 
                st.warning("السعر في مسار محايد ومستقر ⚪")
            
            # --- العرض المنظم لنقاط الدخول كما طلبت ---
            st.markdown("---")
            st.subheader("🎯 أقرب نقاط الدخول المقترحة:")
            st.write(f"**🟢 نقطة الدخول شراء (صعود - دعم):** بالقرب من مستوى السعر **${sup:,.2f}**")
            st.write(f"**🔴 نقطة الدخول بيع (هبوط - مقاومة):** بالقرب من مستوى السعر **${res:,.2f}**")
            
            st.markdown("---")
            st.subheader("📰 أحدث الأخبار وتأثيرها:")
            if news:
                for item in news:
                    sentiment = analyze_news_sentiment(item['title'])
                    st.markdown(f"**التأثير:** {sentiment} | [{item['title']}]({item['url']})")
            else: 
                st.info("لا توجد أخبار متوفرة لهذا الرمز حالياً.")
        else: 
            st.error("عذراً، لم نتمكن من جلب بيانات لهذا الرمز. يرجى التأكد من كتابته بشكل صحيح.")
