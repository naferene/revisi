import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime

st.set_page_config(layout="centered")
st.title("📱 Mini Institutional Futures Engine")

DATA_DIR = "data"
LOG_FILE = os.path.join(DATA_DIR, "trade_log.csv")
STATE_FILE = os.path.join(DATA_DIR, "state.json")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ================= STATE =================
DEFAULT_STATE = {
    "equity": 1000.0,
    "risk_percent": 1.0,
    "leverage": 5,
    "daily_loss": 0.0,
    "current_streak": 0,
    "last_reset": datetime.now().strftime("%Y-%m-%d")
}

def load_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f:
            json.dump(DEFAULT_STATE, f)
        return DEFAULT_STATE.copy()
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def reset_daily(state):
    today = datetime.now().strftime("%Y-%m-%d")
    if state["last_reset"] != today:
        state["daily_loss"] = 0
        state["last_reset"] = today
        save_state(state)
    return state

def update_streak(state, r):
    if r > 0:
        state["current_streak"] = state["current_streak"] + 1 if state["current_streak"] >= 0 else 1
    elif r < 0:
        state["current_streak"] = state["current_streak"] - 1 if state["current_streak"] <= 0 else -1

state = reset_daily(load_state())

if "analysis" not in st.session_state:
    st.session_state.analysis = None

tab1, tab2, tab3 = st.tabs(["Analyze", "Trade Log", "Statistics"])

# ================= TAB 1 =================
with tab1:

    st.subheader("Account Snapshot")
    col1, col2, col3 = st.columns(3)
    col1.metric("Equity", f"${round(state['equity'],2)}")
    col2.metric("Daily Loss", f"${round(state['daily_loss'],2)}")
    col3.metric("Streak", state["current_streak"])

    st.divider()

    # ================= INPUT =================
    pair = st.text_input("Pair", "BTCUSDT")
    price = st.number_input("Current Price", value=0.0)

    trend = st.selectbox("Trend", ["Uptrend", "Downtrend"])
    hl = st.number_input("Last HL / LH", value=0.0)
    hh = st.number_input("Last HH / LL", value=0.0)
    break_confirmed = st.checkbox("Break Confirmed")

    funding = st.number_input("Funding (%)", value=0.0)
    oi_trend = st.selectbox("OI Trend", ["Rising", "Falling", "Flat"])
    ls_ratio = st.number_input("L/S Ratio", value=1.0)

    rsi = st.number_input("RSI (10)", value=50.0)
    high_24 = st.number_input("24h High", value=0.0)
    low_24 = st.number_input("24h Low", value=0.0)
    change_24 = st.number_input("24h % Change", value=0.0)
    volume_24 = st.number_input("24h Volume (USDT)", value=0.0)

    micro = st.selectbox("Micro Confirmation", ["None", "Weak", "Strong"])

    # ================= ANALYZE =================
    if st.button("Analyze"):

        breakdown = {}

        # ---------- Structure (20)
        structure = 0
        if trend == "Uptrend":
            structure += 10
            if price > hl:
                structure += 5
        elif trend == "Downtrend":
            structure += 10
            if price < hl:
                structure += 5

        if break_confirmed:
            structure += 5

        breakdown["Structure"] = structure

        # ---------- Supply-Demand (20)
        sd = 0
        if hh != hl:
            swing = abs(hh - hl)
            proximity = abs(price - hl) / swing if swing != 0 else 0
            if proximity < 0.25:
                sd += 10
            elif proximity < 0.75:
                sd += 5

        if high_24 > low_24:
            range_pos = (price - low_24) / (high_24 - low_24)
            if range_pos < 0.9:
                sd += 5
            else:
                sd -= 5

        breakdown["SupplyDemand"] = sd

        # ---------- Positioning (20)
        positioning = 0
        if oi_trend == "Rising":
            positioning += 7

        if funding < 0.05:
            positioning += 5
        else:
            positioning -= 5

        if ls_ratio < 1:
            positioning += 3

        breakdown["Positioning"] = positioning

        # ---------- RSI (15)
        rsi_layer = 0
        if 40 <= rsi <= 65:
            rsi_layer += 5
        if rsi < 75:
            rsi_layer += 5

        breakdown["RSI"] = rsi_layer

        # ---------- Micro (15)
        micro_score = 0
        if micro == "Strong":
            micro_score = 10
        elif micro == "Weak":
            micro_score = 5

        breakdown["Micro"] = micro_score

        # ---------- Extreme Penalty (10)
        penalty = 0
        if high_24 > low_24:
            range_pos = (price - low_24) / (high_24 - low_24)
            if range_pos > 0.9 and rsi > 75:
                penalty = -10

        breakdown["ExtremePenalty"] = penalty

        score = sum(breakdown.values())
        score = max(min(score, 100), 0)

        if score >= 70:
            verdict = "🟢 GO"
        elif score >= 60:
            verdict = "🟡 Conditional"
        else:
            verdict = "🔴 NO-GO"

        st.session_state.analysis = {
            "score": score,
            "verdict": verdict,
            "breakdown": breakdown
        }

    # ================= DISPLAY =================
    if st.session_state.analysis:

        a = st.session_state.analysis

        st.metric("Composite Score", f"{a['score']} / 100")
        st.markdown(f"### {a['verdict']}")

        with st.expander("Breakdown"):
            st.write(a["breakdown"])

        r_input = st.number_input("Trade Result (R Multiple)", value=0.0)

        if st.button("Save Trade"):

            risk_amount = state["equity"] * (state["risk_percent"] / 100)
            pnl = risk_amount * r_input

            state["equity"] += pnl

            if r_input < 0:
                state["daily_loss"] += abs(pnl)

            update_streak(state, r_input)
            save_state(state)

            row = pd.DataFrame([{
                "Date": datetime.now(),
                "Pair": pair,
                "Score": a["score"],
                "Verdict": a["verdict"],
                "R": r_input,
                "Equity": state["equity"]
            }])

            if os.path.exists(LOG_FILE):
                row.to_csv(LOG_FILE, mode="a", header=False, index=False)
            else:
                row.to_csv(LOG_FILE, index=False)

            st.success(f"Trade Saved → Equity ${round(state['equity'],2)}")

# ================= TAB 2 =================
with tab2:
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        st.dataframe(df)
    else:
        st.write("No Trade Logs Yet.")

# ================= TAB 3 =================
with tab3:
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        total = len(df)
        winrate = len(df[df["R"] > 0]) / total * 100 if total > 0 else 0
        avg_r = df["R"].mean() if total > 0 else 0

        st.metric("Total Trades", total)
        st.metric("Winrate (%)", round(winrate,2))
        st.metric("Average R", round(avg_r,2))

        df["Cumulative_R"] = df["R"].cumsum()
        st.line_chart(df["Cumulative_R"])
    else:
        st.write("No Statistics Yet.")
