# استدعاء المكتبات المطلوبة
import streamlit as st
import requests
import pandas as pd
import ta
from textblob import TextBlob
import yfinance as yf # 🌟 المكتبة الجديدة الخاصة بأسهم الشركات

# إعداد واجهة الموقع الأساسية
st.set_page_config(page_title="المحلل الذكي للأسواق", page_icon="📈", layout="centered")

# ==========================================
# 1. دوال جلب البيانات (الأسعار)
# ==========================================

def get_crypto_data(symbol, timeframe="1hour"):
    """دالة لجلب بيانات العملات الرقمية"""
    clean_symbol = symbol.replace(" ", "")
    formatted_symbol = clean_symbol.replace("/", "-").upper()
    url = f"https://api.kucoin.com/api/v1/market/candles?symbol={formatted_symbol}&type={timeframe}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data['code'] != '200000' or not data['data']:
            return None

        raw_data = data['data']
        df = pd.DataFrame(raw_data, columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
        df['close'] = df['close'].astype(float)
        df = df.iloc[::-1].reset_index(drop=True) 
        return df
    except Exception:
        return None

def get_stock_data(symbol):
    """🌟 دالة جديدة: جلب بيانات أسهم الشركات"""
    clean_symbol = symbol.replace(" ", "").upper()
    try:
        # جلب بيانات السهم لآخر شهر على إطار الساعة
        ticker = yf.Ticker(clean_symbol)
        df = ticker.history(period="1mo", interval="1h")
        
        if df.empty:
            return None
            
        # توحيد أسماء الأعمدة لتتناسب مع التحليل الفني
        df = df.reset_index()
        df.rename(columns={'Open': 'open', 'Close': 'close', 'High': 'high', 'Low': 'low', 'Volume': 'volume'}, inplace=True)
        return df
    except Exception:
        return None

# ==========================================
# 2. دوال التحليل الفني والمشاعر
# ==========================================

def analyze_technical(df):
    """حساب المؤشرات الفنية للأسهم والعملات"""
    rsi_indicator = ta.momentum.RSIIndicator(close=df['close'], window=14)
    df['rsi'] = rsi_indicator.rsi()
    
    bb_indicator = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_high'] = bb_indicator.bollinger_hband()
    df['bb_low'] = bb_indicator.bollinger_lband() 
    
    latest_rsi = df['rsi'].iloc[-1]
    latest_price = df['close'].iloc[-1]
    support = df['bb_low'].iloc[-1]
    resistance = df['bb_high'].iloc[-1]
    
    return latest_price, latest_rsi, support, resistance

def analyze_news_sentiment(text):
    """تحديد ما إذا كان الخبر إيجابياً أم سلبياً"""
    analysis = TextBlob(text)
    if analysis.sentiment.polarity > 0.1:
        return "إيجابي 🟢"
    elif analysis.sentiment.polarity < -0.1:
        return "سلبي 🔴"
    else:
        return "محايد ⚪"

# ==========================================
# 3. دوال جلب الأخبار
# ==========================================

def get_crypto_news():
    """جلب أخبار العملات الرقمية"""
    url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
    try:
        response = requests.get(url)
        data = response.json()
        if data.get('Message') == 'News list successfully returned':
            return [{'title': item['title'], 'url': item['url']} for item in data['Data'][:5]]
        return None
    except Exception:
        return None

def get_stock_news(symbol):
    """🌟 دالة جديدة: جلب أخبار الشركة المطلوبة تحديداً"""
    clean_symbol = symbol.replace(" ", "").upper()
    try:
        ticker = yf.Ticker(clean_symbol)
        news = ticker.news
        if not news:
            return None
        return [{'title': item['title'], 'url': item['link']} for item in news[:5]]
    except Exception:
        return None

# ==========================================
# 4. تصميم واجهة الموقع
# ==========================================

st.title("📈 المحلل الذكي الشامل للأسواق")
st.write("يدعم الآن تحليل العملات الرقمية وأسهم الشركات العالمية!")

# 🌟 اختيار نوع السوق
market_type = st.radio("الرجاء اختيار السوق الذي تود تحليله:", ["العملات الرقمية 🪙", "الأسهم العالمية 🏢"])

# تخصيص مربع البحث بناءً على الاختيار
if market_type == "العملات الرقمية 🪙":
    user_symbol = st.text_input("رمز العملة (مثال: BTC/USDT):", "BTC/USDT")
else:
    user_symbol = st.text_input("رمز السهم (مثال: AAPL لشركة آبل، أو BABA لشركة علي بابا):", "BABA")

if st.button("تحليل شامل الآن 🔍"):
    if user_symbol:
        st.info("جاري فحص السوق وقراءة الأخبار...")
        
        # جلب البيانات بناءً على نوع السوق
        if market_type == "العملات الرقمية 🪙":
            df = get_crypto_data(user_symbol)
            news_data = get_crypto_news()
        else:
            df = get_stock_data(user_symbol)
            news_data = get_stock_news(user_symbol)
        
        if df is not None:
            # --- القسم الأول: التحليل الفني ---
            price, rsi, support, resistance = analyze_technical(df)
            
            st.success("تم الانتهاء من فحص البيانات الفنية!")
            col1, col2 = st.columns(2)
            col1.metric("السعر الحالي", f"${price:,.2f}")
            col2.metric("مؤشر (RSI)", f"{rsi:.2f}")
            
            st.markdown("---")
            st.subheader("📊 حالة السوق الفنية:")
            if rsi <= 30:
                st.success("الأصل في قاع (تشبع بيعي) - احتمالية الصعود أعلى 🟢")
            elif rsi >= 70:
                st.error("الأصل في قمة (تشبع شرائي) - احتمالية الهبوط أعلى 🔴")
            else:
                st.warning("الأصل في مسار محايد ومستقر ⚪")
                
            st.write(f"**🟢 نقطة الشراء المقترحة (الدعم):** ${support:,.2f}")
            st.write(f"**🔴 نقطة البيع المقترحة (المقاومة):** ${resistance:,.2f}")
            
            st.markdown("---")
            
            # --- القسم الثاني: تحليل الأخبار والمشاعر ---
            st.subheader("📰 أحدث الأخبار وتأثيرها المتوقع:")
            
            if news_data:
                for article in news_data:
                    sentiment = analyze_news_sentiment(article['title'])
                    st.markdown(f"**التأثير:** {sentiment} | [{article['title']}]({article['url']})")
            else:
                st.info("لا توجد أخبار متاحة لهذا الرمز في الوقت الحالي.")
                
            st.markdown("---")
            st.caption("ملاحظة هامة: هذا الموقع أداة مساعدة تعتمد على خوارزميات برمجية. تداول بمسؤولية.")
        else:
            st.error("❌ عذراً، لم نتمكن من جلب البيانات. تأكد من صحة الرمز (مثال للأسهم: AAPL، للعملات: BTC/USDT).")
    else:
        st.warning("الرجاء إدخال الرمز أولاً.")
