# استدعاء المكتبات المطلوبة 
import streamlit as st
import requests
import pandas as pd
import ta
from textblob import TextBlob # 🌟 المكتبة الجديدة لتحليل مشاعر النصوص

# إعداد واجهة الموقع الأساسية
st.set_page_config(page_title="مُتابع العملات الرقمية", page_icon="🚀", layout="centered")

def get_crypto_data(symbol, timeframe="1hour"):
    """
    دالة لجلب بيانات العملة من الإنترنت للتحليل الفني.
    """
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

def analyze_technical(df):
    """
    دالة لحساب المؤشرات الفنية (RSI و Bollinger Bands).
    """
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

def get_latest_news():
    """
    دالة لجلب أحدث الأخبار العالمية.
    """
    url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
    try:
        response = requests.get(url)
        data = response.json()
        if data.get('Message') == 'News list successfully returned':
            return data['Data'][:5] # جلب أحدث 5 أخبار
        return None
    except Exception:
        return None

def analyze_news_sentiment(text):
    """
    🌟 دالة جديدة: تقوم بتحليل النص وتحديد ما إذا كان إيجابياً أم سلبياً
    """
    # تمرير النص إلى المكتبة الذكية
    analysis = TextBlob(text)
    
    # القطبية (polarity) تعطينا رقماً. إذا كان أكبر من الصفر فهو إيجابي، وإذا كان أقل فهو سلبي
    if analysis.sentiment.polarity > 0.1:
        return "إيجابي 🟢"
    elif analysis.sentiment.polarity < -0.1:
        return "سلبي 🔴"
    else:
        return "محايد ⚪"

# ==========================================
# تصميم واجهة الموقع
# ==========================================

st.title("🚀 المحلل الذكي الشامل للعملات الرقمية")
st.write("أداة احترافية تدمج بين التحليل الفني الآلي، وتحليل مشاعر الأخبار بالذكاء الاصطناعي.")

user_symbol = st.text_input("رمز العملة (مثال: BTC/USDT):", "BTC/USDT")

if st.button("تحليل شامل الآن 🔍"):
    if user_symbol:
        st.info("جاري فحص السوق وقراءة الأخبار...")
        
        df = get_crypto_data(user_symbol)
        
        if df is not None:
            # --- القسم الأول: التحليل الفني ---
            price, rsi, support, resistance = analyze_technical(df)
            
            st.success("تم الانتهاء من فحص البيانات!")
            col1, col2 = st.columns(2)
            col1.metric("السعر الحالي", f"${price:,.2f}")
            col2.metric("مؤشر (RSI)", f"{rsi:.2f}")
            
            st.markdown("---")
            st.subheader("📊 حالة السوق الفنية:")
            if rsi <= 30:
                st.success("العملة في قاع (تشبع بيعي) - احتمالية الصعود أعلى 🟢")
            elif rsi >= 70:
                st.error("العملة في قمة (تشبع شرائي) - احتمالية الهبوط أعلى 🔴")
            else:
                st.warning("العملة في مسار محايد ومستقر ⚪")
                
            st.write(f"**🟢 نقطة الشراء المقترحة (الدعم):** ${support:,.2f}")
            st.write(f"**🔴 نقطة البيع المقترحة (المقاومة):** ${resistance:,.2f}")
            
            st.markdown("---")
            
            # --- القسم الثاني: تحليل الأخبار والمشاعر ---
            st.subheader("📰 أحدث الأخبار وتأثيرها المتوقع:")
            news = get_latest_news()
            
            if news:
                for article in news:
                    # تحليل عنوان كل خبر يتم جلبه
                    sentiment = analyze_news_sentiment(article['title'])
                    
                    # عرض الخبر مع نتيجته
                    st.markdown(f"**تأثير الخبر:** {sentiment} | [{article['title']}]({article['url']})")
            else:
                st.info("لا توجد أخبار متاحة في الوقت الحالي.")
                
            st.markdown("---")
            st.caption("ملاحظة هامة: هذا الموقع أداة مساعدة تعتمد على خوارزميات برمجية. تداول بمسؤولية.")
        else:
            st.error("❌ عذراً، لم نتمكن من جلب البيانات. تأكد من صحة الرمز.")
    else:
        st.warning("الرجاء إدخال رمز العملة.")
