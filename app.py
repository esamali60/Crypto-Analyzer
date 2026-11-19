import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="مكتب التداول الذكي + مختبر الاختبار", layout="wide")

defaults = {
    "trade_active": False,
    "entry_price": 0.0,
    "stop_loss": 0.0,
    "initial_sl": 0.0,
    "take_profit": 0.0,
    "position_size_usd": 0.0,
    "coins_bought": 0.0,
    "trade_symbol": "",
    "trade_type": "شراء",
    "selected_symbol": "BTC-USD",
    "trade_history": []
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.title("🏆 بوت التداول الاحترافي + مختبر الاختبار التاريخي (Backtest)")

WATCHLIST = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "NEAR-USD", "BNB-USD"]

def format_price(val):
    return f"${val:,.4f}" if abs(val) < 10 else f"${val:,.2f}"

def fetch_live_data(pair, period="5d", interval="5m"):
    try:
        df = yf.download(pair, period=period, interval=interval, progress=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        time_col = 'Datetime' if 'Datetime' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
        df = df.rename(columns={
            time_col: 'timestamp',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df = df.dropna(subset=['close']).reset_index(drop=True)
        return df if not df.empty else None
    except Exception:
        return None

def compute_indicators(df):
    close = df['close']
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9, adjust=False).mean()

    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    upper_band = sma20 + (std20 * 2)
    lower_band = sma20 - (std20 * 2)

    return pd.DataFrame({
        "close": close,
        "rsi": rsi,
        "ema9": ema9,
        "ema21": ema21,
        "macd": macd,
        "signal_line": signal_line,
        "upper_band": upper_band,
        "lower_band": lower_band
    })

def score_at_index(ind_df, idx):
    current_price = float(ind_df['close'].iloc[idx])
    curr_rsi = float(ind_df['rsi'].iloc[idx]) if not pd.isna(ind_df['rsi'].iloc[idx]) else 50.0
    curr_ema9 = float(ind_df['ema9'].iloc[idx])
    curr_ema21 = float(ind_df['ema21'].iloc[idx])
    curr_macd = float(ind_df['macd'].iloc[idx])
    curr_sig = float(ind_df['signal_line'].iloc[idx])
    upper_band = ind_df['upper_band'].iloc[idx]
    lower_band = ind_df['lower_band'].iloc[idx]

    score = 0
    reasons = []

    if curr_rsi < 35:
        score += 30
        reasons.append("تشبع بيعي قوي (RSI)")
    elif curr_rsi < 45:
        score += 15
        reasons.append("منطقة تجميع جيدة (RSI)")
    elif curr_rsi > 65:
        score -= 30
        reasons.append("تشبع شرائي مرتفع (RSI)")
    elif curr_rsi > 55:
        score -= 15
        reasons.append("ضعف في زخم الصعود (RSI)")

    if curr_ema9 > curr_ema21:
        score += 25
        reasons.append("اتجاه صاعد قصير المدى (EMA9 > EMA21)")
    else:
        score -= 25
        reasons.append("اتجاه هابط قصير المدى (EMA9 < EMA21)")

    if curr_macd > curr_sig:
        score += 25
        reasons.append("تقاطع إيجابي للماكد (MACD)")
    else:
        score -= 25
        reasons.append("تقاطع سلبي للماكد (MACD)")

    if not pd.isna(lower_band) and current_price <= float(lower_band) * 1.005:
        score += 20
        reasons.append("ارتداد من الحد السفلي لبولينجر")
    elif not pd.isna(upper_band) and current_price >= float(upper_band) * 0.995:
        score -= 20
        reasons.append("ملامسة القمة السعرية لبولينجر")

    if score >= 30:
        decision = "BUY"
    elif score <= -30:
        decision = "SELL"
    else:
        decision = "NEUTRAL"

    return {
        "price": current_price,
        "rsi": curr_rsi,
        "score": score,
        "decision": decision,
        "reasons": reasons
    }

def run_backtest(df, pos_usd, sl_pct, tp_pct):
    if df is None or len(df) < 40:
        return None
    ind = compute_indicators(df)
    trades = []
    in_pos = False
    pos_side = None
    entry = 0.0
    sl = 0.0
    tp = 0.0
    coins = 0.0
    equity = 0.0
    peak_equity = 0.0
    max_dd = 0.0

    for i in range(28, len(ind)):
        price = float(ind['close'].iloc[i])
        res = score_at_index(ind, i)

        if not in_pos:
            if res['decision'] == "BUY":
                in_pos = True
                pos_side = "شراء"
                entry = price
                sl = entry * (1 - sl_pct / 100.0)
                tp = entry * (1 + tp_pct / 100.0)
                coins = pos_usd / entry
            elif res['decision'] == "SELL":
                in_pos = True
                pos_side = "بيع"
                entry = price
                sl = entry * (1 + sl_pct / 100.0)
                tp = entry * (1 - tp_pct / 100.0)
                coins = pos_usd / entry
        else:
            exit_reason = None
            if pos_side == "شراء":
                if price <= sl:
                    exit_reason = "وقف خسارة"
                elif price >= tp:
                    exit_reason = "هدف ربح"
                elif res['decision'] == "SELL":
                    exit_reason = "إشارة عكسية"
            else:
                if price >= sl:
                    exit_reason = "وقف خسارة"
                elif price <= tp:
                    exit_reason = "هدف ربح"
                elif res['decision'] == "BUY":
                    exit_reason = "إشارة عكسية"

            if exit_reason:
                pnl = (price - entry) * coins if pos_side == "شراء" else (entry - price) * coins
                pnl_pct = ((price - entry) / entry * 100) if pos_side == "شراء" else ((entry - price) / entry * 100)
                equity += pnl
                peak_equity = max(peak_equity, equity)
                max_dd = min(max_dd, equity - peak_equity)
                trades.append({
                    "النوع": pos_side,
                    "الدخول": round(entry, 4 if entry < 10 else 2),
                    "الخروج": round(price, 4 if price < 10 else 2),
                    "السبب": exit_reason,
                    "الربح/الخسارة ($)": round(pnl, 2),
                    "النسبة (%)": round(pnl_pct, 2)
                })
                in_pos = False

    if not trades:
        return {"count": 0, "win_rate": 0.0, "net_pnl": 0.0, "max_dd": 0.0, "log": pd.DataFrame()}

    tdf = pd.DataFrame(trades)
    wins = int((tdf["الربح/الخسارة ($)"] > 0).sum())
    return {
        "count": len(tdf),
        "win_rate": (wins / len(tdf)) * 100.0,
        "net_pnl": float(tdf["الربح/الخسارة ($)"].sum()),
        "max_dd": float(max_dd),
        "log": tdf
    }

def get_higher_tf_trend(pair):
    df_1h = fetch_live_data(pair, period="5d", interval="1h")
    if df_1h is None or len(df_1h) < 22:
        return "غير محدد"
    ema20 = df_1h['close'].ewm(span=20, adjust=False).mean()
    last_close = float(df_1h['close'].iloc[-1])
    last_ema = float(ema20.iloc[-1])
    if last_close > last_ema * 1.003:
        return "صاعد على فريم الساعة 🟢"
    elif last_close < last_ema * 0.997:
        return "هابط على فريم الساعة 🔴"
    return "عرضي على فريم الساعة 🟡"

# الشريط الجانبي
st.sidebar.header("📡 رادار اقتناص الفرص الحية")
if st.sidebar.button("🔍 ابحث لي عن أفضل عملة الآن", type="primary", use_container_width=True):
    with st.sidebar.status("جاري مسح السوق وتحليل 10 عملات..."):
        best_coin = None
        highest_abs_score = 0
        for coin in WATCHLIST:
            d = fetch_live_data(coin, period="2d", interval="5m")
            if d is not None and len(d) >= 30:
                ind_d = compute_indicators(d)
                res = score_at_index(ind_d, len(ind_d) - 1)
                if abs(res['score']) > highest_abs_score:
                    highest_abs_score = abs(res['score'])
                    best_coin = (coin, res)

        if best_coin and highest_abs_score >= 30:
            coin_name, coin_data = best_coin
            st.session_state.selected_symbol = coin_name
            action_ar = "شراء 🟢" if coin_data['decision'] == "BUY" else "بيع 🔴"
            st.sidebar.success(f"🎯 **أفضل فرصة الآن: {coin_name}**\n\nالتوصية: **{action_ar}** بقوة **{abs(coin_data['score'])}%**")
        else:
            st.sidebar.warning("السوق هادئ حالياً، لا توجد عملة وصلت لقوة إشارة عالية.")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ إعدادات الصفقة والمخاطر")
symbol = st.sidebar.text_input("رمز العملة", value=st.session_state.selected_symbol).upper()
st.session_state.selected_symbol = symbol

capital = st.sidebar.number_input("إجمالي رأس المال ($)", min_value=10.0, value=500.0, step=50.0)
max_risk_per_trade_pct = st.sidebar.slider("أقصى مخاطرة في الصفقة (%)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)
stop_distance_pct = st.sidebar.slider("مسافة وقف الخسارة (%)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)
trailing_stop_enabled = st.sidebar.checkbox("تفعيل وقف الخسارة المتحرك", value=True)
timeframe = st.sidebar.selectbox("الإطار الزمني", options=["1m", "5m", "15m"], index=1)
refresh_rate = st.sidebar.selectbox("سرعة التحديث (ثانية)", options=[10, 15, 30, 60], index=1)

tab_live, tab_backtest = st.tabs(["📡 غرفة التداول اللحظية", "🧪 مختبر الاختبار التاريخي (Backtest)"])

with tab_live:
    @st.fragment(run_every=refresh_rate)
    def live_trading_dashboard():
        df = fetch_live_data(symbol, period="2d", interval=timeframe)
        if df is None or len(df) < 30:
            st.error(f"تعذر جلب بيانات كافية للعملة {symbol}.")
            return

        ind_df = compute_indicators(df)
        analysis = score_at_index(ind_df, len(ind_df) - 1)
        htf_trend = get_higher_tf_trend(symbol)

        current_price = analysis['price']
        current_rsi = analysis['rsi']
        decision = analysis['decision']
        score = analysis['score']
        last_update = datetime.now().strftime("%H:%M:%S")

        risk_budget_usd = capital * (max_risk_per_trade_pct / 100.0)
        calculated_position_usd = min(capital, risk_budget_usd / (stop_distance_pct / 100.0))

        if decision == "BUY":
            signal_text = f"شراء (BUY) 🟢 | قوة {score}%"
            signal_color = "#28a745"
            btn_color_class = "🟢 شراء"
        elif decision == "SELL":
            signal_text = f"بيع (SELL) 🔴 | قوة {abs(score)}%"
            signal_color = "#dc3545"
            btn_color_class = "🔴 بيع"
        else:
            signal_text = f"انتظار / تذبذب ⏳ | {score}"
            signal_color = "#ffc107"
            btn_color_class = "🟡 دخول حذر (شراء)"

        st.caption(f"🔄 آخر تحديث: **{last_update}** | الإطار: **{timeframe}** | الفريم الأعلى: **{htf_trend}** (كل {refresh_rate} ثانية)")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric(f"سعر {symbol}", format_price(current_price))
        col2.metric("مؤشر القوة (RSI)", f"{current_rsi:.2f}")
        col3.metric("حجم الصفقة المقترح", f"${calculated_position_usd:,.2f}", f"مخاطرة قصوى ${risk_budget_usd:,.2f}")

        with col4:
            st.markdown(f"""
            <div style="background-color: {signal_color}; padding: 12px; border-radius: 8px; text-align: center; color: white; font-weight: bold; font-size: 16px; box-shadow: 0px 0px 12px {signal_color};">
                {signal_text}
            </div>
            """, unsafe_allow_html=True)

        with st.expander("📋 تفاصيل قراءة الخبير للمؤشرات الأربعة", expanded=True):
            st.write(" • ".join([f"**{r}**" for r in analysis['reasons']]))

        st.markdown("---")

        if not st.session_state.trade_active:
            st.subheader(f"🚀 بدء صفقة جديدة على {symbol}")
            is_sell = (decision == "SELL")

            if is_sell:
                suggested_sl = current_price * (1 + (stop_distance_pct / 100.0))
                suggested_tp = current_price * (1 - (stop_distance_pct * 2 / 100.0))
                sl_label = f"+{stop_distance_pct}%"
                tp_label = f"-{stop_distance_pct * 2}%"
            else:
                suggested_sl = current_price * (1 - (stop_distance_pct / 100.0))
                suggested_tp = current_price * (1 + (stop_distance_pct * 2 / 100.0))
                sl_label = f"-{stop_distance_pct}%"
                tp_label = f"+{stop_distance_pct * 2}%"

            c1, c2, c3 = st.columns(3)
            c1.info(f"**سعر الدخول المتوقع:** {format_price(current_price)}")
            c2.warning(f"**وقف الخسارة ({sl_label}):** {format_price(suggested_sl)}")
            c3.success(f"**هدف الربح ({tp_label}):** {format_price(suggested_tp)}")

            if st.button(f"✅ بدء الصفقة الآن ({btn_color_class}) بحجم ${calculated_position_usd:,.2f}", type="primary", use_container_width=True):
                st.session_state.trade_active = True
                st.session_state.entry_price = current_price
                st.session_state.stop_loss = suggested_sl
                st.session_state.initial_sl = suggested_sl
                st.session_state.take_profit = suggested_tp
                st.session_state.position_size_usd = calculated_position_usd
                st.session_state.coins_bought = calculated_position_usd / current_price
                st.session_state.trade_symbol = symbol
                st.session_state.trade_type = "بيع" if is_sell else "شراء"
                st.rerun()
        else:
            t_type = st.session_state.trade_type
            entry = st.session_state.entry_price
            coins = st.session_state.coins_bought
            pos_usd = st.session_state.position_size_usd

            if trailing_stop_enabled:
                if t_type == "شراء":
                    new_sl = current_price * (1 - (stop_distance_pct / 100.0))
                    if new_sl > st.session_state.stop_loss:
                        st.session_state.stop_loss = new_sl
                else:
                    new_sl = current_price * (1 + (stop_distance_pct / 100.0))
                    if new_sl < st.session_state.stop_loss:
                        st.session_state.stop_loss = new_sl

            sl = st.session_state.stop_loss
            tp = st.session_state.take_profit

            if t_type == "بيع":
                pnl_dollar = (entry - current_price) * coins
                pnl_percent = ((entry - current_price) / entry) * 100
                hit_stop_loss = current_price >= sl
                hit_take_profit = current_price <= tp
            else:
                pnl_dollar = (current_price - entry) * coins
                pnl_percent = ((current_price - entry) / entry) * 100
                hit_stop_loss = current_price <= sl
                hit_take_profit = current_price >= tp

            st.subheader(f"📡 مراقبة الصفقة الحية: {st.session_state.trade_symbol} ({t_type}) | حجمها ${pos_usd:,.2f}")

            if hit_stop_loss:
                st.error("🚨 **تنبيه وقف الخسارة!** السعر وصل لحد الوقف المحدد. اضغط على **خروج الآن**.")
            elif hit_take_profit:
                st.success("🎉 **تنبيه جني الأرباح!** الصفقة حققت الهدف المطلوب. اضغط على **خروج الآن**.")
            elif (t_type == "شراء" and decision == "SELL") or (t_type == "بيع" and decision == "BUY"):
                st.warning("⚠️ **تنبيه انعكاس الاتجاه!** المؤشرات انعكست ضد صفقتك، يُنصح بالخروج.")
            else:
                st.info("🟢 **الصفقة مستمرة بأمان...** جاري متابعة السعر والوقف المتحرك لحظياً.")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("سعر الدخول", format_price(entry))
            m2.metric("الربح / الخسارة", f"${pnl_dollar:,.2f}", f"{pnl_percent:.2f}%")
            m3.metric("وقف الخسارة الحالي", format_price(sl))
            m4.metric("هدف الربح", format_price(tp))

            if st.button("🚨 خروج الآن (إغلاق الصفقة وتسجيلها)", type="primary", use_container_width=True):
                st.session_state.trade_history.append({
                    "الوقت": datetime.now().strftime("%H:%M:%S"),
                    "العملة": st.session_state.trade_symbol,
                    "النوع": t_type,
                    "الدخول": round(entry, 4 if entry < 10 else 2),
                    "الخروج": round(current_price, 4 if current_price < 10 else 2),
                    "الربح/الخسارة ($)": round(pnl_dollar, 2),
                    "النسبة (%)": round(pnl_percent, 2)
                })
                st.session_state.trade_active = False
                st.rerun()

        st.markdown("---")
        plot_df = df.tail(60).copy()
        plot_df['EMA 9'] = ind_df['ema9'].tail(60)
        plot_df['EMA 21'] = ind_df['ema21'].tail(60)

        fig = px.line(plot_df, x='timestamp', y=['close', 'EMA 9', 'EMA 21'], title=f"الشارت اللحظي مع متوسطات الخبير - {symbol}")
        if st.session_state.trade_active:
            fig.add_hline(y=st.session_state.entry_price, line_dash="dash", line_color="blue", annotation_text="دخول")
            fig.add_hline(y=st.session_state.stop_loss, line_dash="dot", line_color="red", annotation_text="وقف الخسارة")
            fig.add_hline(y=st.session_state.take_profit, line_dash="dot", line_color="green", annotation_text="هدف الربح")
        st.plotly_chart(fig, use_container_width=True)

        if st.session_state.trade_history:
            st.markdown("---")
            st.subheader("📒 سجل صفقات الجلسة وأداء الخبير")
            hist_df = pd.DataFrame(st.session_state.trade_history)
            total_pnl = hist_df["الربح/الخسارة ($)"].sum()
            win_trades = int((hist_df["الربح/الخسارة ($)"] > 0).sum())
            win_rate = (win_trades / len(hist_df)) * 100

            s1, s2, s3 = st.columns(3)
            s1.metric("إجمالي الصفقات المغلقة", len(hist_df))
            s2.metric("نسبة النجاح (Win Rate)", f"{win_rate:.1f}%")
            s3.metric("صافي ربح/خسارة الجلسة", f"${total_pnl:,.2f}")
            st.dataframe(hist_df, use_container_width=True, hide_index=True)

    live_trading_dashboard()

with tab_backtest:
    st.subheader(f"🧪 اختبار أداء الاستراتيجية تاريخياً على {symbol}")
    st.caption("يختبر البوت قواعده الحالية على البيانات التاريخية المتاحة لحساب نسبة النجاح وأقصى تراجع قبل التداول.")

    bt_col1, bt_col2, bt_col3 = st.columns(3)
    bt_sl = bt_col1.number_input("وقف الخسارة للاختبار (%)", min_value=0.5, max_value=15.0, value=float(stop_distance_pct), step=0.5)
    bt_tp = bt_col2.number_input("هدف الربح للاختبار (%)", min_value=0.5, max_value=30.0, value=float(stop_distance_pct * 2), step=0.5)
    bt_pos = bt_col3.number_input("مبلغ الصفقة للاختبار ($)", min_value=10.0, max_value=100000.0, value=float(capital), step=50.0)

    if st.button("▶️ تشغيل الاختبار التاريخي الآن", type="primary"):
        with st.spinner("جاري محاكاة الصفقات التاريخية..."):
            hist_raw = fetch_live_data(symbol, period="5d", interval=timeframe)
            bt_res = run_backtest(hist_raw, bt_pos, bt_sl, bt_tp)

        if not bt_res or bt_res["count"] == 0:
            st.warning("لم يتم العثور على صفقات مكتملة خلال الفترة التاريخية المختارة بهذه الإعدادات.")
        else:
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("عدد الصفقات المختبرة", bt_res["count"])
            b2.metric("نسبة النجاح التاريخية", f"{bt_res['win_rate']:.1f}%")
            b3.metric("صافي الربح/الخسارة التقديري", f"${bt_res['net_pnl']:,.2f}")
            b4.metric("أقصى تراجع (Max Drawdown)", f"${bt_res['max_dd']:,.2f}")
            st.dataframe(bt_res["log"], use_container_width=True, hide_index=True)

---

### تنبيه مهم حول المخاطر والتنفيذ
* هذا التطبيق أداة تحليل ومحاكاة تعليمية ولا ينفذ أوامر حقيقية على محفظتك، كما أن الأداء التاريخي في الأسواق الرقمية لا يضمن تكرار النتائج مستقبلاً.

هل تود أن نختبر عملة معينة في **مختبر الاختبار التاريخي** الآن، أو نضبط قواعد الدخول لتكون أكثر تحفظاً مع الفريم الأعلى؟
