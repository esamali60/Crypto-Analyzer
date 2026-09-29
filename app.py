import streamlit as st
import pandas as pd
import numpy as np
import ta
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

# 1. إعداد الصفحة لتكون واسعة
st.set_page_config(page_title="المحلل الذكي بالتفاضل والتكامل الرياضي", layout="wide")

# 2. التحديث التلقائي (كل 60 ثانية)
st_autorefresh(interval=60000, limit=None, key="market_refresh")

# 3. البنر العلوي للإعلانات
st.markdown("""
    <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 15px; text-align: center; border-radius: 10px; margin-bottom: 20px;">
        <p style="color: #888; font-size: 14px; margin: 0;">مساحة إعلانية علوية</p>
    </div>
""", unsafe_allow_html=True)

# --- الدوال البرمجية لجلب وتحليل البيانات رياضياً ---
def get_market_data(symbol):
    """دالة لجلب بيانات السعر التاريخية للأصل من yfinance"""
    try:
        ticker = yf.Ticker(symbol.strip().upper())
        df = ticker.history(period="1mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df.rename(columns={'Open': 'open', 'Close': 'close', 'High': 'high', 'Low': 'low', 'Volume': 'volume'}, inplace=True)
        return df
    except: return None

def analyze_with_calculus(df):
    """
    دالة تعتمد على التفاضل الرياضي (المشتقة الأولى والثانية) 
    لتحديد السرعة، التسارع، ونقاط الانعكاس المتوقعة للسعر.
    """
    prices = df['close'].values
    
    # 1. المشتقة الأولى (السرعة / ميل السعر) باستخدام np.gradient
    velocity = np.gradient(prices)
    
    # 2. المشتقة الثانية (التسارع / التقعر) لتحديد متى يفقد السعر عزمه
    acceleration = np.gradient(velocity)
    
    current_price = prices[-1]
    current_velocity = velocity[-1]
    current_accel = acceleration[-1]
    
    # حساب المستويات المتوقعة للوقوف أو الانعكاس بناءً على التراكم (التكامل التقريبي)
    integral_proxy = np.mean(prices) # متوسط السعر التراكمي كمستوى ارتكاز
    
    return current_price, current_velocity, current_accel, integral_proxy

def get_calculus_recommendation(velocity, acceleration, price, base_level):
    """
    اتخاذ القرار بناءً على قيمة المشتقة الأولى والثانية (التفاضل)
    """
    if velocity > 0 and acceleration > 0:
        trend = "صاعد بقوة (تسارع إيجابي 🚀)"
        advice = "🟢 **التوصية:** السعر في مسار صاعد نشط. يمكنك الاحتفاظ أو الشراء بحذر مع متابعة العزم."
    elif velocity > 0 and acceleration < 0:
        trend = "صاعد يفقد زخمه (قريب من قمة محتملة ⚠️)"
        advice = "🟡 **التوصية:** الصعود يتباطأ (المشتقة الثانية سالبة). يُفضل **الانتظار أو جني الأرباح جزئياً** لأنه قد يتوقف قريباً."
    elif velocity < 0 and acceleration < 0:
        trend = "هابط بقوة (تسارع سلبي للأسفل 🔻)"
        advice = "🔴 **التوصية:** البيع أو تجنب الشراء حالياً، السعر يسقط بتسارع متزايد."
    else:
        trend = "هابط يبطئ من هبوطه (قريب من قاع محتمل 🔵)"
        advice = f"🟢 **التوصية:** الهبوط يتباطأ والاقتراب من نقطة الارتكاز (${base_level:,.2f}). قد تكون فرصة **شراء استباقي** إذا ارتدت السرعة."
    
    return trend, advice

def get_market_news(symbol):
    """دالة لجلب آخر الأخبار الاقتصادية المرتبطة بالرمز"""
    try:
        ticker = yf.Ticker(symbol.strip().upper())
        news = ticker.news
        if not news: return None
        return [{'title': i.get('title'), 'link': i.get('link', '#')} for i in news if i.get('title')]
    except: return None

# --- واجهة المستخدم الرئيسية ---
col_main, col_ads = st.columns([3, 1])

with col_main:
    st.title("📐 المحلل الذكي بالتفاضل والتكامل الرياضي للأسواق")
    
    # اختيار نوع السوق
    market_type = st.radio("اختر نوع السوق الأساسي:", ["العملات الرقمية 🪙", "الأسهم العالمية 🏢"], horizontal=True)
    
    if market_type == "العملات الرقمية 🪙":
        options = ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "BNB-USD", "XRP-USD", "DOGE-USD"]
    else:
        options = ["AAPL", "TSLA", "NVDA", "AMZN", "MSFT", "GOOGL", "META", "NFLX"]

    # طريقة الإدخال
    input_method = st.radio("اختر طريقتك لتحديد الأصل:", ["اختيار من القائمة الجاهزة 📋", "كتابة الرمز يدوياً ✍️"], horizontal=True)

    if input_method == "اختيار من القائمة الجاهزة 📋":
        final_symbol = st.selectbox("اختر العملة أو السهم:", options)
    else:
        manual_text = st.text_input("اكتب رمز الأصل بنفسك (مثال: AVAX-USD أو 2222.SR):", "")
        final_symbol = manual_text.strip().upper() if manual_text.strip() != "" else options[0]

    # سطر الحالة وزر التحديث المباشر
    col_status, col_btn = st.columns([3, 1])
    with col_status:
        st.info(f"📊 جارٍ تحليل الأصل الحالي رياضياً: **{final_symbol}** (تحديث تلقائي كل دقيقة)")
    with col_btn:
        manual_refresh_btn = st.button("🔄 تحديث مباشر")

    # تنفيذ التحليل الرياضي وعرض النتائج
    if final_symbol:
        with st.spinner('جاري تطبيق النمذجة الرياضية (التفاضل والتكامل) على السعر...'):
            df = get_market_data(final_symbol)
            news = get_market_news(final_symbol)
            
            if df is not None:
                price, velocity, acceleration, base_level = analyze_with_calculus(df)
                trend, advice = get_calculus_recommendation(velocity, acceleration, price, base_level)
                
                # عرض السعر ومؤشرات التفاضل (السرعة والتسارع)
                c1, c2, c3 = st.columns(3)
                c1.metric("السعر الحالي", f"${price:,.2f}")
                c2.metric("سرعة التغير (المشتقة 1)", f"{velocity:.4f}")
                c3.metric("التسارع (المشتقة 2)", f"{acceleration:.4f}")
                
                # عرض النبذة والتوصية الرياضية الذكية
                st.markdown("---")
                st.subheader("💡 النبذة والتحليل الرياضي الدقيق:")
                st.write(f"📈 **حالة الاتجاه الهندسي:** {trend}")
                st.markdown(advice)
                
                # عرض نقاط الوقف والارتكاز المحسوبة رياضياً
                st.markdown("---")
                st.subheader("🎯 المستويات المحسوبة رياضياً:")
                st.write(f"⚖️ **مستوى الارتكاز التراكمي (التكامل التقريبي):** ${base_level:,.2f}")
                st.write(f"🔍 تفسير هندسي: السعر يميل للارتداد أو الاستقرار كلما اقترب من خط الارتكاز التراكمي طالما أن التسارع يقترب من الصفر.")
                
                # عرض الأخبار الاقتصادية
                st.markdown("---")
                st.subheader("📰 أحدث الأخبار الاقتصادية:")
                if news:
                    for item in news[:5]:
                        st.markdown(f"🔗 [{item['title']}]({item['link']})")
                else:
                    st.warning("لا توجد أخبار الاقتصادية متاحة حالياً لهذا الرمز.")
            else:
                st.error(f"عذراً، لم نتمكن من جلب بيانات للرمز ({final_symbol}). تأكد من صحة كتابة الرمز.")

with col_ads:
    st.subheader("📢 إعلانات")
    st.markdown("""
        <div style="background-color: #1e1e1e; border: 1px dashed #444; padding: 20px; border-radius: 10px; height: 500px; color: #888; text-align: center;">
            <p style="margin-top: 200px;">ضع كود الإعلان الجانبي هنا</p>
        </div>
    """, unsafe_allow_html=True)
