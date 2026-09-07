import streamlit as st
import pandas as pd
import ta
from textblob import TextBlob
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

# إعداد الصفحة لتكون واسعة
st.set_page_config(page_title="المحلل الذكي الشامل", layout="wide")

# --- 1. التحديث التلقائي (كل 60 ثانية) ---
st_autorefresh(interval=60000, limit=None, key="market_refresh")

# --- 2. البنر العلوي للإعلانات ---
st.markdown("""
    <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 15px; text-align: center; border-radius: 10px; margin-bottom: 20px;">
        <p style="color: #888; font-size: 14px; margin: 0;">مساحة إعلانية علوية</p>
    </div>
""", unsafe_allow_html=True)

# --- الدوال البرمجية لجلب وتحليل البيانات ---
def get_market_data(symbol):
    try:
        ticker = yf.Ticker(symbol.strip().upper())
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
        ticker = yf.Ticker(symbol.strip().upper())
        news = ticker.news
        if not news: return None
        return [{'title': i.get('title'), 'link': i.get('link', '#')} for i in news if i.get('title')]
    except: return None

def get_trading_recommendation(price, rsi, sup, res):
    if rsi <= 30:
        trend = "صاعد (فرصة ارتداد من القاع)"
        advice = "🟢 **التوصية:** الشراء الآن (السعر في منطقة تشبع بيعي، وهناك احتمالية قوية للصعود)."
    elif rsi >= 70:
        trend = "هابط (تصحيح محتمل من القمة)"
        advice = "🔴 **التوصية:** البيع أو جني الأرباح الآن (السعر في منطقة تشبع شرائي، وقد يسببه هبوط قريب)."
    else:
        if abs(price - sup) < abs(price - res):
            trend = "محايد يميل للصعود تدريجياً"
            advice = f"🟡 **التوصية:** الانتظار قليلاً أو الشراء بحذر عند الاقتراب من نقطة الدعم (${sup:,.2f})."
        else:
            trend = "محايد يميل للهبوط أو التذبذب"
            advice = f"🟡 **التوصية:** الانتظار حتى يهبط السعر نحو الدعم (${sup:,.2f}) أو تجنب الشراء حالياً لقربه من المقاومة."
    return trend, advice

# --- واجهة المستخدم الرئيسية ---
col_main, col_ads = st.columns([3, 1])

with col_main:
    st.title("🚀 المحلل الذكي الشامل للأسواق")
    
    # اختيار نوع السوق
    market_type = st.radio("اختر نوع السوق:", ["العملات الرقمية 🪙", "الأسهم العالمية 🏢"], horizontal=True)
    
    # تجهيز القوائم المنسدلة حسب السوق المختار
    if market_type == "العملات الرقمية 🪙":
        options = ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "BNB-USD", "XRP-USD", "DOGE-USD"]
    else:
        options = ["AAPL", "TSLA", "NVDA", "AMZN", "MSFT", "GOOGL", "META", "NFLX"]

    # صندوق اختيار من القائمة أو كتابة يدوية
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        selected_dropdown = st.selectbox("اختر من القائمة الجاهزة:", options)
    with col_input2:
        manual_text = st.text_input("أو اكتب الرمز يدوياً (مثال: AVAX-USD):", "")

    # معالجة الرمز النهائي المستخدم في التحليل
    if manual_text.strip() != "":
        final_symbol = manual_text.strip().upper()
    else:
        final_symbol = selected_dropdown

    st.info(f"📊 جارٍ تحليل الأصل الحالي: **{final_symbol}** (تحديث تلقائي كل دقيقة)")

    # تنفيذ جلب البيانات وعرضها مباشرة
    with st.spinner('جاري جلب بيانات السوق وتحليل المؤشرات...'):
        df = get_market_data(final_symbol)
        news = get_market_news(final_symbol)
        
        if df is not None:
            price, rsi, sup, res = analyze_technical(df)
            trend, advice = get_trading_recommendation(price, rsi, sup, res)
            
            # عرض السعر ومؤشر RSI في أعمدة مترابطة
            c1, c2 = st.columns(2)
            c1.metric("السعر الحالي", f"${price:,.2f}")
            c2.metric("مؤشر RSI", f"{rsi:.2f}")
            
            # عرض التوصية الذكية
            st.markdown("---")
            st.subheader("💡 النبذة والتوصية الذكية:")
            st.write(f"📈 **حالة الاتجاه:** {trend}")
            st.markdown(advice)
            
            # عرض نقاط الدخول في أسطر منفصلة وواضحة
            st.markdown("---")
            st.subheader("🎯 أقرب نقاط الدخول المقترحة:")
            st.write(f"🟢 **نقطة الدخول شراء (دعم):** ${sup:,.2f}")
            st.write(f"🔴 **نقطة الدخول بيع (مقاومة):** ${res:,.2f}")
            
            # عرض الأخبار الاقتصادية
            st.markdown("---")
            st.subheader("📰 أحدث الأخبار الاقتصادية:")
            if news:
                for item in news[:5]:
                    st.markdown(f"🔗 [{item['title']}]({item['link']})")
            else:
                st.warning("لا توجد أخبار اقتصادية متاحة حالياً لهذا الرمز.")
        else:
            st.error(f"عذراً، لم نتمكن من جلب بيانات للرمز ({final_symbol}). تأكد من كتابة الرمز بشكل صحيح (مثل إضافة -USD للعملات الرقمية).")

with col_ads:
    st.subheader("📢 إعلانات")
    st.markdown("""
        <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 20px; border-radius: 10px; height: 500px; color: #888; text-align: center;">
            <p style="margin-top: 200px;">ضع كود الإعلان الجانبي هنا</p>
        </div>
    """, unsafe_allow_html=True)
