import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="📒 Jurnal Trading - Google Sheets", layout="wide")

# --- Setup koneksi Google Sheets ---
def get_gsheet_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"])
    return gspread.authorize(creds)

client = get_gsheet_client()
# Ganti dengan nama spreadsheet yang kamu buat di Google Sheets
SHEET_NAME = "JurnalTrading"
sheet = client.open(SHEET_NAME).sheet1


# --- Sidebar ---
st.sidebar.header("⚙️ Pengaturan Akun")
tipe_akun = st.sidebar.selectbox("Tipe Akun", ["Micro", "Mini", "Standard"])
equity_awal = st.sidebar.number_input("Equity Awal", min_value=0.0, value=1000.0, step=10.0)

# Hitung equity sekarang dari data sheet
data = sheet.get_all_records()
df = pd.DataFrame(data)
if not df.empty and "Profit" in df.columns:
    equity_sekarang = equity_awal + df["Profit"].sum()
else:
    equity_sekarang = equity_awal

st.sidebar.metric("Equity Sekarang", f"{equity_sekarang:.2f}")
st.sidebar.write(f"Akun: {tipe_akun} | Equity Awal: {equity_awal}")


# --- Main Title ---
st.title("📒 Jurnal Trading – Google Sheets Version")

st.subheader("✍️ Input Transaksi Baru")

# --- Input form ---
with st.form("entry_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        pair = st.text_input("Pair", "XAUUSD")
        tanggal = st.date_input("Tanggal", datetime.today())
        jam = st.time_input("Jam", datetime.now().time())
        status = st.selectbox("Status", ["Running", "TP", "SL"])
    with col2:
        action = st.selectbox("BUY / SELL", ["BUY", "SELL"])
        entry = st.number_input("Entry", value=0.0, step=0.01)
        lot = st.number_input("Lot", value=0.10, step=0.01)
        sl = st.number_input("SL", value=0.0, step=0.01)
    with col3:
        tp1 = st.number_input("TP1", value=0.0, step=0.01)
        tp2 = st.number_input("TP2", value=0.0, step=0.01)
        profit = st.number_input("Profit", value=0.0, step=0.01)
        note = st.text_area("Note")

    link = st.text_input("Link Screenshot Entry")

    submitted = st.form_submit_button("💾 Simpan Transaksi")

    if submitted:
        row = [
            pair, action, tanggal.strftime("%Y-%m-%d"), jam.strftime("%H:%M"),
            entry, lot, sl, tp1, tp2, status, profit, note, link
        ]
        sheet.append_row(row)
        st.success("✅ Transaksi berhasil disimpan ke Google Sheets!")


# --- Tampilkan Data ---
st.subheader("📊 Riwayat Transaksi")

data = sheet.get_all_records()
df = pd.DataFrame(data)

if not df.empty:
    st.dataframe(df)
else:
    st.info("Belum ada transaksi yang tercatat.")
