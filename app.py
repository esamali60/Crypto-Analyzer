# استدعاء المكتبات المطلوبة لبناء الموقع والتحليل
import streamlit as st
import requests
import pandas as pd
import ta

# إعداد واجهة الموقع الأساسية
st.set_page_config(page_title="مُتابع العملات الرقمية", page_icon="🚀")

def get_crypto_data(symbol, timeframe="1hour"): # 🌟 تم إصلاح الإطار الزمني هنا إلى 1hour
    """
    دالة لجلب بيانات العملة من الإنترنت (منصة KuCoin).
    """
    # تنظيف الرمز من المسافات
    clean_symbol = symbol.replace(" ", "")
    
    # تحويل الرمز للصيغة المطلوبة للمنصة (مثال: ETH-USDT)
    formatted_symbol = clean_symbol.replace("/", "-").upper()
    
    # رابط جلب البيانات
    url = f"https://api.kucoin.com/api/v1/market/candles?symbol={formatted_symbol}&type={timeframe}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        # التحقق من وجود خطأ أو عدم توفر بيانات
        if data['code'] != '200000' or not data['data']:
            return None

        # تحويل البيانات إلى جدول ليسهل تحليلها
        raw_data = data['data']
        df = pd.DataFrame(raw_data, columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
        df['close'] = df['close'].astype(float)
        df = df.iloc[::-1].reset_index(drop=True) # ترتيب من الأقدم للأحدث
        return df
    except Exception:
        # في حال وجود مشكلة في الاتصال بالإنترنت
        return None

def analyze_technical(df):
    """
    دالة لحساب المؤشرات الفنية (RSI للاتجاه، و Bollinger Bands لنقاط الدخول)
    """
    # 1. حساب مؤشر القوة النسبية RSI
    rsi_indicator = ta.momentum.RSIIndicator(close=df['close'], window=14)
    df['rsi'] = rsi_indicator.rsi()
    
    # 2. حساب حدود بولينجر (للدعم والمقاومة)
    bb_indicator = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_high'] = bb_indicator.bollinger_hband() # المقاومة (نقطة البيع)
    df['bb_low'] = bb_indicator.bollinger_lband()  # الدعم (نقطة الشراء)
    
    latest_rsi = df['rsi'].iloc[-1]
    latest_price = df['close'].iloc[-1]
    support = df['bb_low'].iloc[-1]
    resistance = df['bb_high'].iloc[-1]
    
    return latest_price, latest_rsi, support, resistance

# ==========================================
# تصميم واجهة الموقع
# ==========================================

st.title("🚀 المحلل الذكي للعملات الرقمية")
st.write("أدخل الرمز لمعرفة الاتجاه وأفضل نقاط الدخول المحتملة.")

# مربع إدخال اسم العملة
user_symbol = st.text_input("رمز العملة (مثال: BTC/USDT):", "BTC/USDT")

# زر بدء التحليل
if st.button("تحليل الآن 🔍"):
    if user_symbol:
        st.info("جاري جلب بيانات السوق وتحليلها...")
        
        # استدعاء دالة جلب البيانات
        df = get_crypto_data(user_symbol)
        
        if df is not None:
            # استخراج النتائج من الدالة
            price, rsi, support, resistance = analyze_technical(df)
            
            st.success("تم التحليل بنجاح!")
            
            # عرض السعر والمؤشر العام
            col1, col2 = st.columns(2)
            col1.metric("السعر الحالي", f"${price:,.2f}")
            col2.metric("مؤشر (RSI)", f"{rsi:.2f}")
            
            st.markdown("---")
            
            # عرض حالة السوق
            st.subheader("📊 حالة السوق الآن:")
            if rsi <= 30:
                st.success("العملة في قاع (تشبع بيعي) - احتمالية الصعود أعلى 🟢")
            elif rsi >= 70:
                st.error("العملة في قمة (تشبع شرائي) - احتمالية الهبوط أعلى 🔴")
            else:
                st.warning("العملة في مسار محايد ومستقر ⚪")
                
            st.markdown("---")
            
            # عرض نقاط الدخول
            st.subheader("🎯 أقرب نقاط الدخول المقترحة:")
            st.write(f"**🟢 نقطة الدخول شراء (صعود - دعم):** بالقرب من مستوى السعر **${support:,.2f}**")
            st.write(f"**🔴 نقطة الدخول بيع (هبوط - مقاومة):** بالقرب من مستوى السعر **${resistance:,.2f}**")
            
            st.caption("ملاحظة: هذه البيانات مبنية على التحليل الفني الآلي، يرجى التداول بحذر.")
        else:
            st.error("❌ عذراً، لم نتمكن من جلب البيانات. تأكد من صحة الرمز أو أن المنصة تدعمه.")
    else:
        st.warning("الرجاء إدخال رمز العملة.")
