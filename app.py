import streamlit as st
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from cryptography.fernet import Fernet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import bcrypt
import os

st.set_page_config(layout="wide")

# ------------------- SIMPLE AUTH SYSTEM -------------------
if "users" not in st.session_state:
    st.session_state.users = {}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        "glucose","carbs","insulin","exercise"
    ])

# ------------------- ENCRYPTION -------------------
if "key" not in st.session_state:
    st.session_state.key = Fernet.generate_key()

cipher = Fernet(st.session_state.key)

def encrypt(val):
    return cipher.encrypt(str(val).encode()).decode()

def decrypt(val):
    return float(cipher.decrypt(val.encode()).decode())

# ------------------- LOGIN / REGISTER -------------------
st.sidebar.title("Account")

if not st.session_state.logged_in:
    mode = st.sidebar.radio("Select", ["Login","Register"])
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")

    if mode == "Register":
        if st.sidebar.button("Register"):
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            st.session_state.users[email] = hashed
            st.success("Registered. Please login.")

    if mode == "Login":
        if st.sidebar.button("Login"):
            if email in st.session_state.users and \
               bcrypt.checkpw(password.encode(), st.session_state.users[email]):
                st.session_state.logged_in = True
                st.success("Logged in")
            else:
                st.error("Invalid credentials")

    st.stop()

# ------------------- MAIN DASHBOARD -------------------
st.title("🩸 AI Diabetes Management Platform")

# ------------------- ADD ENTRY -------------------
st.subheader("Add Entry")

col1, col2 = st.columns(2)

with col1:
    glucose = st.number_input("Glucose (mg/dL)", min_value=0)
    carbs = st.number_input("Carbs (g)", min_value=0)

with col2:
    insulin = st.number_input("Insulin (units)", min_value=0)
    exercise = st.number_input("Exercise (minutes)", min_value=0)

if st.button("Add Entry"):
    new_row = {
        "glucose": encrypt(glucose),
        "carbs": encrypt(carbs),
        "insulin": encrypt(insulin),
        "exercise": encrypt(exercise)
    }
    st.session_state.data = pd.concat(
        [st.session_state.data, pd.DataFrame([new_row])],
        ignore_index=True
    )
    st.success("Entry Added")

# ------------------- CGM IMPORT -------------------
st.subheader("Import CGM CSV")

uploaded_file = st.file_uploader("Upload CGM CSV")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    if "Glucose Value (mg/dL)" in df.columns:
        df.rename(columns={"Glucose Value (mg/dL)": "glucose"}, inplace=True)

    for _, row in df.iterrows():
        new_row = {
            "glucose": encrypt(row["glucose"]),
            "carbs": encrypt(0),
            "insulin": encrypt(0),
            "exercise": encrypt(0)
        }
        st.session_state.data = pd.concat(
            [st.session_state.data, pd.DataFrame([new_row])],
            ignore_index=True
        )

    st.success("CGM Imported")

# ------------------- ANALYTICS -------------------
if not st.session_state.data.empty:

    df = st.session_state.data.copy()

    df["glucose"] = df["glucose"].apply(decrypt)
    df["carbs"] = df["carbs"].apply(decrypt)
    df["insulin"] = df["insulin"].apply(decrypt)
    df["exercise"] = df["exercise"].apply(decrypt)

    avg_glucose = df["glucose"].mean()
    time_in_range = len(df[(df["glucose"] >= 70) & (df["glucose"] <= 180)]) / len(df) * 100
    hypo = len(df[df["glucose"] < 70])

    a1c = (avg_glucose + 46.7) / 28.7

    risk = 0
    if avg_glucose > 180:
        risk += 40
    if time_in_range < 70:
        risk += 30
    if hypo > 3:
        risk += 30

    st.subheader("📊 Metrics")
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Average Glucose", f"{avg_glucose:.1f}")
    col2.metric("Time in Range", f"{time_in_range:.1f}%")
    col3.metric("Estimated A1C", f"{a1c:.2f}")
    col4.metric("Risk Score", min(risk,100))

    # AI Prediction
    if len(df) > 5:
        X = df[["glucose","carbs","insulin","exercise"]]
        y = df["glucose"].shift(-1).dropna()
        X = X[:-1]
        model = LinearRegression()
        model.fit(X, y)
        prediction = model.predict([X.iloc[-1]])[0]
        st.subheader("🤖 AI Prediction")
        st.info(f"Predicted Next Glucose: {prediction:.1f}")

    # Chart
    st.line_chart(df["glucose"])

    # PDF Export
    if st.button("Generate Doctor PDF"):
        filename = "report.pdf"
        doc = SimpleDocTemplate(filename)
        styles = getSampleStyleSheet()
        elements = []
        elements.append(Paragraph("Diabetes Clinical Report", styles["Title"]))
        elements.append(Spacer(1,12))
        elements.append(Paragraph(f"Average Glucose: {avg_glucose:.2f}", styles["Normal"]))
        elements.append(Paragraph(f"Estimated A1C: {a1c:.2f}", styles["Normal"]))
        elements.append(Paragraph(f"Risk Score: {risk}", styles["Normal"]))
        doc.build(elements)
        st.success("PDF Generated (saved locally)")
