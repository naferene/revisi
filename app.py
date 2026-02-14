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

    pair = st.text_input("Pair", "BTCUSDT")
    dummy_input = st.number_input("Dummy Score Input", value=0.0)

    if st.button("Analyze"):
        st.session_state.analysis = {
            "score": dummy_input,
            "verdict": "TEST"
        }

    if st.session_state.analysis:

        st.metric("Composite Score", st.session_state.analysis["score"])
        st.markdown("### TEST VERDICT")

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
                "Score": st.session_state.analysis["score"],
                "Verdict": st.session_state.analysis["verdict"],
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
