import streamlit as st
import pandas as pd
import ta
from textblob import TextBlob
import yfinance as yf

# إعداد الصفحة لتكون واسعة
st.set_page_config(page_title="المحلل الذكي الشامل", layout="wide")

# --- 1. البنر العلوي للإعلانات ---
st.markdown("""
    <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 15px; text-align: center; border-radius: 10px; margin-bottom: 20px;">
        <p style="color: #888; font-size: 14px; margin: 0;"><script> atOptions = { 'key' : '9a374e1ba3c8e64316b7e2eb29f45a7a', 'format' : 'iframe', 'height' : 90, 'width' : 728, 'params' : {} }; </script> <script src="https://www.highperformanceformat.com/9a374e1ba3c8e64316b7e2eb29f45a7a/invoke.js"></script></p>
    </div>
""", unsafe_allow_html=True)

# --- الدوال البرمجية ---
def get_market_data(symbol):
    """دالة لجلب بيانات السوق وتحويلها لأسماء أعمدة متوافقة"""
    try:
        ticker = yf.Ticker(symbol.strip().upper())
        df = ticker.history(period="1mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df.rename(columns={'Open': 'open', 'Close': 'close', 'High': 'high', 'Low': 'low', 'Volume': 'volume'}, inplace=True)
        return df
    except: return None

def analyze_technical(df):
    """دالة حساب المؤشرات الفنية RSI وبولينجر باند"""
    rsi = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    return df['close'].iloc[-1], rsi.iloc[-1], bb.bollinger_lband().iloc[-1], bb.bollinger_hband().iloc[-1]

def get_market_news(symbol):
    """دالة لجلب الأخبار الاقتصادية المرتبطة بالأصل"""
    try:
        ticker = yf.Ticker(symbol.strip().upper())
        news = ticker.news
        if not news: return None
        return [{'title': i.get('title'), 'link': i.get('link', '#')} for i in news if i.get('title')]
    except: return None

# --- تقسيم الصفحة إلى عمودين (الرئيسي والإعلاني) ---
col_main, col_ads = st.columns([3, 1])

with col_main:
    st.title("🚀 المحلل الذكي الشامل")
    
    # اختيار السوق
    market_type = st.radio("اختر نوع السوق:", ["العملات الرقمية 🪙", "الأسهم العالمية 🏢"], horizontal=True)
    
    # تحديد الخيارات المتاحة في القائمة بناءً على السوق
    if market_type == "العملات الرقمية 🪙":
        list_options = ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "BNB-USD", "XRP-USD"]
        default_idx = 0
    else:
        list_options = ["AAPL", "TSLA", "NVDA", "AMZN", "MSFT", "GOOGL", "META"]
        default_idx = 0

    # استخدام طريقتين منفصلتين وواضحتين تماماً لتجنب التعارض:
    # 1. القائمة المنسدلة السريعة
    selected_from_list = st.selectbox("1️⃣ أو اختر من القائمة الجاهزة:", list_options, index=default_idx)
    
    # 2. خانة الإدخال اليدوي الحر (إذا كتب فيها المستخدم شيئاً، ستلغي القائمة تلقائياً)
    manual_input = st.text_input("2️⃣ أو اكتب رمز الأصل بنفسك (مثال: DOGE-USD أو MSFT):", "")

    # تحديد أي الرمزين سيتم اعتماده في التحليل
    if manual_input.strip() != "":
        final_symbol = manual_input.strip().upper()
    else:
        final_symbol = selected_from_list

    st.write(f"الرمز المختار حالياً للتحليل: **{final_symbol}**")

    if st.button("بدء التحليل الفني الشامل 🔍"):
        with st.spinner('جاري جلب البيانات ومعالجة السوق...'):
            df = get_market_data(final_symbol)
            news = get_market_news(final_symbol)
            
            if df is not None:
                price, rsi, sup, res = analyze_technical(df)
                
                c1, c2 = st.columns(2)
                c1.metric("السعر الحالي", f"${price:,.2f}")
                c2.metric("مؤشر RSI", f"{rsi:.2f}")
                
                st.subheader("📊 حالة السوق الفنية:")
                if rsi <= 30: st.success("الأصل في قاع (تشبع بيعي) - احتمالية الصعود أعلى 🟢")
                elif rsi >= 70: st.error("الأصل في قمة (تشبع شرائي) - احتمالية الهبوط أعلى 🔴")
                else: st.warning("السعر في مسار محايد ومستقر ⚪")
                
                st.markdown("---")
                st.subheader("🎯 أقرب نقاط الدخول المقترحة:")
                st.write(f"🟢 **نقطة الدخول شراء (دعم):** ${sup:,.2f}")
                st.write(f"🔴 **نقطة الدخول بيع (مقاومة):** ${res:,.2f}")
                
                st.markdown("---")
                st.subheader("📰 أحدث الأخبار الاقتصادية:")
                if news:
                    for item in news[:5]:
                        st.markdown(f"🔗 [{item['title']}]({item['link']})")
                else: 
                    st.warning("لا توجد أخبار اقتصادية متاحة حالياً لهذا الرمز.")
            else: 
                st.error(f"عذراً، لم نتمكن من العثور على بيانات للرمز ({final_symbol}). تأكد من صحة كتابته (مثلاً العملات تنتهي بـ -USD مثل SOL-USD).")

with col_ads:
    st.subheader("📢 إعلانات")
    st.markdown("""
        <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 20px; border-radius: 10px; height: 500px; color: #888; text-align: center;">
            <p style="margin-top: 200px;"><script> atOptions = { 'key' : '04e5cc65f1f9df82e44cdac786768a40', 'format' : 'iframe', 'height' : 250, 'width' : 300, 'params' : {} }; </script> <script src="https://www.highperformanceformat.com/04e5cc65f1f9df82e44cdac786768a40/invoke.js"></script></p>
        </div>
    """, unsafe_allow_html=True)
