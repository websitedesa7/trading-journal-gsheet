import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

# ------------------------
# Google Sheets Connection
# ------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

if "GSPREAD_CREDENTIALS" in st.secrets:
    # Baca dari secrets di Streamlit Cloud
    creds_dict = json.loads(st.secrets["GSPREAD_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
else:
    # Fallback offline lokal, pastikan ada file credentials.json
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

client = gspread.authorize(creds)

# Nama Sheet (ganti sesuai kebutuhanmu)
SHEET_NAME = "Jurnal_Trading"
try:
    sheet = client.open(SHEET_NAME).sheet1
except Exception as e:
    st.error(f"Gagal membuka Google Sheet: {e}")
    st.stop()

# ------------------------
# Helper Functions
# ------------------------
def load_data():
    """Ambil data dari Google Sheet"""
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    return df

def append_data(row):
    """Tambah baris ke Google Sheet"""
    sheet.append_row(row)

def clear_data():
    """Hapus semua data di Google Sheet (kecuali header)"""
    values = sheet.get_all_values()
    if len(values) > 1:
        sheet.delete_rows(2, len(values))

# ------------------------
# Streamlit App
# ------------------------
st.title("📊 Jurnal Trading (Google Sheets Version)")

menu = ["Tambah Entry", "Lihat Data", "Export"]
choice = st.sidebar.selectbox("Menu", menu)

# Sidebar Equity Tracking
if "equity" not in st.session_state:
    st.session_state["equity"] = 1000  # default equity awal

st.sidebar.write(f"💰 Equity Saat Ini: **{st.session_state['equity']}**")

if choice == "Tambah Entry":
    st.subheader("➕ Tambah Transaksi Baru")

    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("Tanggal")
        pair = st.text_input("Pair/Symbol", "XAUUSD")
        entry_type = st.selectbox("Tipe Order", ["BUY", "SELL"])
        lot_size = st.number_input("Lot Size", min_value=0.01, step=0.01)
    with col2:
        entry_price = st.number_input("Entry Price", step=0.01)
        exit_price = st.number_input("Exit Price", step=0.01)
        status = st.selectbox("Status", ["-", "SL", "TP", "BE"])
        notes = st.text_area("Catatan")

    pl_manual = st.number_input("Profit/Loss Manual", step=0.01, value=0.0)
    link_before = st.text_input("Chart Before (Link opsional)")
    link_after = st.text_input("Chart After (Link opsional)")

    if st.button("Simpan Transaksi"):
        # Hitung P/L otomatis bila pl_manual = 0
        if pl_manual == 0.0 and entry_price and exit_price:
            if entry_type == "BUY":
                pl = (exit_price - entry_price) * lot_size * 100
            else:
                pl = (entry_price - exit_price) * lot_size * 100
        else:
            pl = pl_manual

        # Update equity di session_state
        st.session_state["equity"] += pl

        row = [
            str(date),
            pair,
            entry_type,
            lot_size,
            entry_price,
            exit_price,
            status,
            pl,
            st.session_state["equity"],
            notes,
            link_before,
            link_after,
        ]
        append_data(row)
        st.success("Transaksi berhasil disimpan ✅")

elif choice == "Lihat Data":
    st.subheader("📑 Riwayat Transaksi")
    df = load_data()
    if df.empty:
        st.info("Belum ada data tersimpan.")
    else:
        st.dataframe(df, use_container_width=True)

        # Filter opsional
        with st.expander("🔍 Filter Data"):
            symbol_filter = st.text_input("Cari Pair/Symbol")
            if symbol_filter:
                df = df[df["pair"].str.contains(symbol_filter, case=False)]

            status_filter = st.selectbox("Filter Status", ["-", "ALL", "SL", "TP", "BE"])
            if status_filter != "ALL":
                df = df[df["status"] == status_filter]

            st.dataframe(df, use_container_width=True)

elif choice == "Export":
    st.subheader("⬇️ Export Data")
    df = load_data()
    if df.empty:
        st.warning("Tidak ada data untuk di-export.")
    else:
        # Download Excel
        excel_file = df.to_excel(index=False, engine="openpyxl")
        st.download_button("Download Excel", data=excel_file, file_name="jurnal_trading.xlsx")

        # Download CSV
        csv_file = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", data=csv_file, file_name="jurnal_trading.csv")
