# استدعاء المكتبات البرمجية الأساسية
import streamlit as st
import pandas as pd
import ta
from textblob import TextBlob
import yfinance as yf

# إعداد واجهة الموقع لتبدو احترافية
st.set_page_config(page_title="المحلل الذكي الشامل", page_icon="📈", layout="centered")

# --- دالة جلب بيانات العملات الرقمية والأسهم عبر Yahoo Finance (مستقرة ولا توقف) ---
def get_market_data(symbol):
    clean_symbol = symbol.replace(" ", "").upper()
    try:
        # جلب البيانات لآخر شهر على إطار الساعة
        ticker = yf.Ticker(clean_symbol)
        df = ticker.history(period="1mo", interval="1h")
        
        if df.empty: 
            return None
            
        df = df.reset_index()
        # توحيد أسماء الأعمدة لتتوافق مع مؤشرات التحليل الفني
        df.rename(columns={'Open': 'open', 'Close': 'close', 'High': 'high', 'Low': 'low', 'Volume': 'volume'}, inplace=True)
        return df
    except: 
        return None

# --- دالة التحليل الفني (RSI + Bollinger Bands) ---
def analyze_technical(df):
    rsi = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    return df['close'].iloc[-1], rsi.iloc[-1], bb.bollinger_lband().iloc[-1], bb.bollinger_hband().iloc[-1]

# --- دالة تحليل مشاعر الأخبار (الذكاء الاصطناعي) ---
def analyze_news_sentiment(text):
    try:
        if not text or not isinstance(text, str):
            return "محايد ⚪"
        pol = TextBlob(text).sentiment.polarity
        if pol > 0.05: return "إيجابي 🟢"
        elif pol < -0.05: return "سلبي 🔴"
        return "محايد ⚪"
    except:
        return "محايد ⚪"

# --- دالة جلب الأخبار لأي أصل (عملات أو أسهم) ---
def get_market_news(symbol):
    clean_symbol = symbol.replace(" ", "").upper()
    try:
        ticker = yf.Ticker(clean_symbol)
        news = ticker.news
        news_list = []
        if news and isinstance(news, list):
            for i in news:
                title = i.get('title')
                link = i.get('link', '#')
                if title:
                    news_list.append({'title': str(title), 'url': str(link)})
        return news_list[:5] if news_list else None
    except: 
        return None

# --- واجهة الموقع ---
st.title("🚀 المحلل الذكي الشامل للأسواق")
st.write("أداة تحليلية تدمج الأرقام الفنية مع مشاعر الأخبار.")

market = st.radio("اختر السوق:", ["العملات الرقمية 🪙", "الأسهم العالمية 🏢"])

# تخصيص مثال الرمز بناءً على السوق المختار
if market == "العملات الرقمية 🪙":
    user_symbol = st.text_input("أدخل رمز العملة (مثال: BTC-USD أو ETH-USD):", "BTC-USD")
else:
    user_symbol = st.text_input("أدخل رمز السهم (مثال: AAPL لشركة آبل):", "AAPL")

if st.button("تحليل شامل الآن 🔍"):
    with st.spinner('جاري معالجة البيانات وتحليل الأخبار...'):
        # جلب البيانات والأخبار باستخدام الدوال الجديدة المستقرة
        df = get_market_data(user_symbol)
        news = get_market_news(user_symbol)
        
        if df is not None:
            price, rsi, sup, res = analyze_technical(df)
            col1, col2 = st.columns(2)
            col1.metric("السعر الحالي", f"${price:,.2f}")
            col2.metric("مؤشر RSI", f"{rsi:.2f}")
            
            st.subheader("📊 حالة السوق الفنية:")
            if rsi <= 30: 
                st.success("الأصل في قاع (تشبع بيعي) - احتمالية الصعود أعلى 🟢")
            elif rsi >= 70: 
                st.error("الأصل في قمة (تشبع شرائي) - احتمالية الهبوط أعلى 🔴")
            else: 
                st.warning("السعر في مسار محايد ومستقر ⚪")
            
            # --- العرض المنظم لنقاط الدخول ---
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
            st.error("عذراً، لم نتمكن من جلب بيانات لهذا الرمز. تأكد من كتابته بشكل صحيح (مثل BTC-USD للعملات).")
