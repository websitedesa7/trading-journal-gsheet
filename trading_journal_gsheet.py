import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# --- Konfigurasi Streamlit ---
st.set_page_config(page_title="📒 Jurnal Trading - Google Sheets", layout="wide")
st.title("📒 Jurnal Trading – Google Sheets Version")

# --- Setup koneksi Google Sheets ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_gsheet_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return gspread.authorize(creds)

client = get_gsheet_client()

# --- Sheet utama & settings ---
SHEET_NAME = "JurnalTrading"
SETTINGS_NAME = "Settings"

try:
    sheet = client.open(SHEET_NAME).sheet1
except gspread.SpreadsheetNotFound:
    st.error(f"Spreadsheet '{SHEET_NAME}' tidak ditemukan. Pastikan nama sama persis.")
    st.stop()

# Cek / buat sheet Settings
spreadsheet = client.open(SHEET_NAME)
try:
    settings_sheet = spreadsheet.worksheet(SETTINGS_NAME)
except gspread.exceptions.WorksheetNotFound:
    settings_sheet = spreadsheet.add_worksheet(title=SETTINGS_NAME, rows=10, cols=2)
    settings_sheet.update("A1:B1", [["TipeAkun", "EquityAwal"]])

# Ambil data settings
settings_data = settings_sheet.get_all_records()
if settings_data:
    tipe_akun_saved = settings_data[0]["TipeAkun"]
    equity_awal_saved = float(settings_data[0]["EquityAwal"])
else:
    tipe_akun_saved = "Micro"
    equity_awal_saved = 1000.0

# --- Sidebar Pengaturan Akun ---
st.sidebar.header("⚙️ Pengaturan Akun")

tipe_akun = st.sidebar.selectbox("Tipe Akun", ["Micro", "Mini", "Standard"], index=["Micro","Mini","Standard"].index(tipe_akun_saved))
equity_awal = st.sidebar.number_input("Equity Awal", min_value=0.0, value=equity_awal_saved, step=10.0)

# Hitung equity sekarang
data = sheet.get_all_records()
df = pd.DataFrame(data)
if not df.empty and "Profit" in df.columns:
    equity_sekarang = equity_awal + df["Profit"].sum()
else:
    equity_sekarang = equity_awal

st.sidebar.metric("Equity Sekarang", f"{equity_sekarang:.2f}")

# Tombol reset
if st.sidebar.button("🔄 Reset Equity"):
    new_equity = st.number_input("Masukkan Equity Baru", min_value=0.0, value=1000.0, step=10.0, key="reset_equity")
    if st.button("✅ Konfirmasi Reset"):
        settings_sheet.update("A2:B2", [[tipe_akun, new_equity]])
        st.success(f"Equity berhasil direset ke {new_equity}")
        st.stop()

# Simpan setting terbaru jika berubah
if (tipe_akun != tipe_akun_saved) or (equity_awal != equity_awal_saved):
    settings_sheet.update("A2:B2", [[tipe_akun, equity_awal]])

# --- Form Input Transaksi Baru ---
st.subheader("✍️ Input Transaksi Baru")

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

# --- Tampilkan Data Transaksi ---
st.subheader("📊 Riwayat Transaksi")

data = sheet.get_all_records()
df = pd.DataFrame(data)

if not df.empty:
    st.dataframe(df, use_container_width=True)
else:
    st.info("Belum ada transaksi yang tercatat.")
