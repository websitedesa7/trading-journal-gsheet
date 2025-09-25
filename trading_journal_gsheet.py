# trading_journal_gsheet.py (final dengan safe_float)
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="📒 Trading Journal", layout="wide")

# -----------------------
# Konfigurasi access GSheet
# -----------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_client_from_secrets_or_file():
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"], scopes=SCOPES
            )
        else:
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error("Gagal autentikasi Google Sheets.\n\n" + str(e))
        st.stop()

client = get_client_from_secrets_or_file()

# -----------------------
# Nama Spreadsheet
# -----------------------
SHEET_NAME = "JurnalTrading"

try:
    spreadsheet = client.open(SHEET_NAME)
except Exception as e:
    st.error(f"Gagal membuka spreadsheet '{SHEET_NAME}'. Pastikan service account punya akses.\n\n{e}")
    st.stop()

sheet = spreadsheet.sheet1

# -----------------------
# Header standar
# -----------------------
HEADER = [
    "ID", "Pair", "Jam", "Tanggal", "Buy/Sell", "Entry", "Exit", "Lot",
    "SL", "TP1", "TP2", "Status", "P/L", "Note", "SS Before", "SS After", "Equity"
]

values = sheet.get_all_values()
if not values or values[0] != HEADER:
    sheet.clear()
    sheet.insert_row(HEADER, 1)

# -----------------------
# Settings sheet
# -----------------------
SETTINGS_NAME = "Settings"
try:
    try:
        settings_sheet = spreadsheet.worksheet(SETTINGS_NAME)
    except gspread.exceptions.WorksheetNotFound:
        settings_sheet = spreadsheet.add_worksheet(title=SETTINGS_NAME, rows=10, cols=3)
        settings_sheet.update("A1:C1", [["TipeAkun", "EquityAwal", "Multiplier"]])
        settings_sheet.update("A2:C2", [["Micro", 1000, 100.0]])
except Exception as e:
    st.error("Gagal baca/siapkan sheet Settings:\n" + str(e))
    st.stop()

settings = settings_sheet.get_all_records()
if settings:
    tipe_akun_saved = settings[0].get("TipeAkun", "Micro")
    equity_awal_saved = float(settings[0].get("EquityAwal", 1000.0))
    multiplier_saved = float(settings[0].get("Multiplier", 100.0))
else:
    tipe_akun_saved = "Micro"
    equity_awal_saved = 1000.0
    multiplier_saved = 100.0

# -----------------------
# Sidebar
# -----------------------
st.sidebar.header("⚙️ Pengaturan Akun")
tipe_akun = st.sidebar.selectbox("Tipe Akun", ["Micro", "Mini", "Standard"], index=["Micro","Mini","Standard"].index(tipe_akun_saved))
equity_awal_input = st.sidebar.number_input("Equity Awal", min_value=0.0, value=equity_awal_saved, step=1.0)
multiplier_input = st.sidebar.number_input("Multiplier per lot", value=multiplier_saved, step=1.0)

if st.sidebar.button("🔄 Reset Equity (set new equity)"):
    with st.sidebar.form("reset_form", clear_on_submit=True):
        new_tipe = st.selectbox("Tipe Akun", ["Micro","Mini","Standard"], index=["Micro","Mini","Standard"].index(tipe_akun))
        new_eq = st.number_input("Equity Baru", min_value=0.0, value=1000.0)
        new_mult = st.number_input("Multiplier per lot", value=multiplier_input)
        submit_reset = st.form_submit_button("✅ Konfirmasi Reset")
        if submit_reset:
            settings_sheet.update("A2:C2", [[new_tipe, new_eq, new_mult]])
            st.success(f"Equity direset ke {new_eq}. Reload app jika perlu.")
            st.experimental_rerun()

if (tipe_akun != tipe_akun_saved) or (abs(equity_awal_input - equity_awal_saved) > 1e-9) or (abs(multiplier_input - multiplier_saved) > 1e-9):
    try:
        settings_sheet.update("A2:C2", [[tipe_akun, equity_awal_input, multiplier_input]])
        tipe_akun_saved = tipe_akun
        equity_awal_saved = float(equity_awal_input)
        multiplier_saved = float(multiplier_input)
    except Exception as e:
        st.warning("Gagal simpan Settings: " + str(e))

# -----------------------
# Baca data
# -----------------------
raw_data = sheet.get_all_records()
df = pd.DataFrame(raw_data)

def safe_float(x):
    try:
        return float(str(x).replace(",", "."))
    except:
        return 0.0

if not df.empty:
    df["P/L"] = df["P/L"].apply(safe_float)
    existing_pl_sum = df["P/L"].sum()
else:
    existing_pl_sum = 0.0

equity_awal = float(equity_awal_saved)
equity_sekarang = equity_awal + existing_pl_sum

st.sidebar.metric("Equity Sekarang", f"{equity_sekarang:.2f}")
st.sidebar.caption(f"Akun: {tipe_akun_saved} | Multiplier: {multiplier_saved}")

# -----------------------
# Form Input
# -----------------------
st.header("✍️ Input Transaksi Baru")

with st.form("trade_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        pair = st.text_input("Pair (mis: XAUUSD)", "")
        jam = st.text_input("Jam (HH:MM)", datetime.now().strftime("%H:%M"))
        entry_price = st.number_input("Entry (price)", value=0.0, format="%.5f")
        sl_price = st.number_input("SL (price)", value=0.0, format="%.5f")
        pl_manual = st.number_input("P/L Manual (opsional, isi 0 untuk otomatis)", value=0.0, format="%.2f")
    with col2:
        tanggal = st.date_input("Tanggal", value=datetime.today())
        buy_sell = st.selectbox("Buy/Sell", ["BUY", "SELL"])
        exit_price = st.number_input("Exit (price)", value=0.0, format="%.5f")
        tp1 = st.number_input("TP1 (price)", value=0.0, format="%.5f")
    with col3:
        lot = st.number_input("Lot (min 0.10)", value=0.10, step=0.01, format="%.2f")
        tp2 = st.number_input("TP2 (price)", value=0.0, format="%.5f")
        status = st.selectbox("Status", ["-", "SL", "TP", "BE", "Manual"])
        note = st.text_area("Note (opsional)")

    ss_before = st.text_input("Link SS Before (opsional)")
    ss_after = st.text_input("Link SS After (opsional)")

    submitted = st.form_submit_button("💾 Simpan Transaksi")

if submitted:
    multiplier = float(multiplier_saved)

    if status == "BE":
        pl_value = 0.0
    elif abs(pl_manual) > 1e-9:
        pl_value = pl_manual
    elif (entry_price != 0.0) and (exit_price != 0.0):
        direction = 1 if buy_sell == "BUY" else -1
        pl_value = (exit_price - entry_price) * lot * multiplier * direction
    else:
        pl_value = 0.0

    vals = sheet.get_all_values()
    new_id = max(0, len(vals) - 1) + 1

    new_equity = equity_awal + existing_pl_sum + pl_value

    row = [
        new_id,
        pair,
        jam,
        tanggal.strftime("%Y-%m-%d"),
        buy_sell,
        entry_price,
        exit_price,
        lot,
        sl_price,
        tp1,
        tp2,
        status,
        pl_value,
        note,
        ss_before,
        ss_after,
        new_equity
    ]

    sheet.append_row(row, value_input_option="USER_ENTERED")
    st.success(f"✅ Transaksi tersimpan! Equity Sekarang: {new_equity:.2f}")

# -----------------------
# Tampilkan data
# -----------------------
st.subheader("📊 Riwayat Transaksi")
raw_data = sheet.get_all_records()
df = pd.DataFrame(raw_data)

if not df.empty:
    df["P/L"] = df["P/L"].apply(safe_float)
    st.dataframe(df, use_container_width=True)
else:
    st.info("Belum ada transaksi yang tercatat.")
