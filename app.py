import ccxt
import pandas as pd
import time

# 1. إعداد الاتصال بالمنصة (مثال: Binance - وضع التجربة Testnet أو الحقيقي)
exchange = ccxt.binance({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET_KEY',
    'enableRateLimit': True,
})

# إذا كنت تريد التجربة بدون أموال حقيقية (تفعيل وضع الاختبار إن توفر):
# exchange.set_sandbox_mode(True)

def fetch_data(symbol, timeframe='1h', limit=100):
    """جلب الشموع اليابانية للعملة وتحويلها إلى جدول بيانات"""
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def analyze_market(df):
    """تحليل السوق وإعطاء إشارات (شراء، بيع، وقف خسارة)"""
    # حساب المتوسط المتحرك البسيط (SMA 50)
    df['sma50'] = df['close'].rolling(window=50).mean()
    
    # حساب مؤشر RSI (القوة النسبية البسيطة كمثال)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
آخر_سعر = df['close'].iloc[-1]
    آخر_rsi = df['rsi'].iloc[-1]
    آخر_sma = df['sma50'].iloc[-1]
    
    signal = "انتظار (HOLD)"
    stop_loss = 0
    
    # استراتيجية كمثال: الشراء إذا كان السعر فوق المتوسط و RSI منخفض (تشبع بيعي)
    if Last_price > Last_sma and Last_rsi < 30:
        Signal = "🟢 إشارة شراء (BUY)"
        Stop_loss = Last_price * 0.97 # وقف الخسارة 3.5% تحت سعر الدخول
    elif Last_price < Last_sma or Last_rsi > 70:
        Signal = "🔴 إشارة بيع (SELL)"
        Stop_loss = Last_price * 1.02
        
    Return signal, last_price, stop_loss, last_rsi

def run_bot(symbol, investment_amount):
    Print(f"🚀 بدء تشغيل بوت التداول للعملة {symbol} بمبلغ {investment_amount} دولار...")
    
    While True:
        Try:
            Df = fetch_data(symbol, timeframe='1h')
            Signal, current_price, stop_loss, rsi = analyze_market(df)
            
            Print(f"\n--- تحديث السوق [{symbol}] ---")
            Print(f"السعر الحالي: {current_price} | مؤشر RSI: {rsi:.2f}")
            Print(f"الحالة والإشارة: {signal}")
            If "شراء" in signal or "بيع" in signal:
                Print(f"🛑 مستوى وقف الخسارة المقترح: {stop_loss:.2f}")
                
        except Exception as e:
            Print(f"حدث خطأ: {e}")
            
        # الانتظار لمدة ساعة قبل الفحص التالي (حسب الإطار الزمني)
        Time.sleep(3600)

# تشغيل البوت: مراقبة عملة البيتكوين مقابل USDT بمبلغ 500 دولار
If __name__ == "__main__":
    Run_bot('BTC/USDT', 500)
