# trading_journal_gsheet.py
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
    """
    Pakai st.secrets['gcp_service_account'] (Streamlit Cloud) jika ada,
    kalau tidak ada fallback ke local credentials.json
    """
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"], scopes=SCOPES
            )
        else:
            # lokal: pastikan file credentials.json ada di folder yang sama
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error("Gagal autentikasi Google Sheets. Periksa credentials/secrets.\n\n" + str(e))
        st.stop()

client = get_client_from_secrets_or_file()

# -----------------------
# Nama Spreadsheet (ubah jika perlu)
# -----------------------
SHEET_NAME = "JurnalTrading"   # pastikan ini nama file spreadsheet di Google Drive

# buka spreadsheet
try:
    spreadsheet = client.open(SHEET_NAME)
except Exception as e:
    st.error(f"Gagal membuka spreadsheet '{SHEET_NAME}'. Pastikan nama benar dan service account punya akses Editor.\n\n{e}")
    st.stop()

# ambil worksheet pertama (sheet1) supaya tidak tergantung nama tab
sheet = spreadsheet.sheet1

# -----------------------
# Header standar yang kita pakai (pastikan urutan ini sama saat append_row)
# -----------------------
HEADER = [
    "ID", "Pair", "Jam", "Tanggal", "Buy/Sell", "Entry", "Exit", "Lot",
    "SL", "TP1", "TP2", "Status", "P/L", "Note", "SS Before", "SS After", "Equity"
]

# pastikan header ada di baris 1 (insert jika kosong atau berbeda)
try:
    vals = sheet.get_all_values()
    if not vals:
        sheet.insert_row(HEADER, 1)
    else:
        first_row = sheet.row_values(1)
        if first_row != HEADER:
            # Sisipkan header di atas (jika misal data sudah ada tapi header tidak)
            sheet.insert_row(HEADER, 1)
except Exception as e:
    st.error("Gagal memastikan header di sheet:\n" + str(e))
    st.stop()

# -----------------------
# Settings sheet (simpan Equity Awal & Multiplier per lot)
# -----------------------
SETTINGS_NAME = "Settings"
try:
    try:
        settings_sheet = spreadsheet.worksheet(SETTINGS_NAME)
    except gspread.exceptions.WorksheetNotFound:
        settings_sheet = spreadsheet.add_worksheet(title=SETTINGS_NAME, rows=10, cols=3)
        # header dan default
        settings_sheet.update("A1:C1", [["TipeAkun", "EquityAwal", "Multiplier"]])
        settings_sheet.update("A2:C2", [["Micro", 1000, 100.0]])
except Exception as e:
    st.error("Gagal membaca/menyiapkan sheet Settings:\n" + str(e))
    st.stop()

# baca settings
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
# Sidebar (Pengaturan)
# -----------------------
st.sidebar.header("⚙️ Pengaturan Akun")
tipe_akun = st.sidebar.selectbox("Tipe Akun", ["Micro", "Mini", "Standard"], index=["Micro","Mini","Standard"].index(tipe_akun_saved))
equity_awal_input = st.sidebar.number_input("Equity Awal", min_value=0.0, value=equity_awal_saved, step=1.0)
multiplier_input = st.sidebar.number_input("Multiplier per lot (untuk P/L)", value=multiplier_saved, step=1.0)

# Tombol Reset Equity (simple)
if st.sidebar.button("🔄 Reset Equity (set new equity)"):
    with st.sidebar.form("reset_form", clear_on_submit=True):
        new_tipe = st.selectbox("Tipe Akun", ["Micro","Mini","Standard"], index=["Micro","Mini","Standard"].index(tipe_akun))
        new_eq = st.number_input("Equity Baru", min_value=0.0, value=1000.0)
        new_mult = st.number_input("Multiplier per lot", value=multiplier_input)
        submit_reset = st.form_submit_button("✅ Konfirmasi Reset")
        if submit_reset:
            settings_sheet.update("A2:C2", [[new_tipe, new_eq, new_mult]])
            st.success(f"Equity direset ke {new_eq}. Silakan reload app jika perlu.")
            st.experimental_rerun()

# kalau setting berubah, simpan ke sheet (agar persistence)
if (tipe_akun != tipe_akun_saved) or (abs(equity_awal_input - equity_awal_saved) > 1e-9) or (abs(multiplier_input - multiplier_saved) > 1e-9):
    try:
        settings_sheet.update("A2:C2", [[tipe_akun, equity_awal_input, multiplier_input]])
        # update local saved vars
        tipe_akun_saved = tipe_akun
        equity_awal_saved = float(equity_awal_input)
        multiplier_saved = float(multiplier_input)
    except Exception as e:
        st.warning("Gagal menyimpan Settings ke Google Sheets: " + str(e))

# -----------------------
# Baca data terakhir dari sheet
# -----------------------
try:
    raw_data = sheet.get_all_records()
    df = pd.DataFrame(raw_data)
except Exception as e:
    st.error("Gagal membaca data dari sheet:\n" + str(e))
    st.stop()

# pastikan kolom P/L ada (jika tidak, buat kolom dengan 0)
if df.empty:
    existing_pl_sum = 0.0
else:
    # convert P/L to numeric safely (menangani string)
    if "P/L" in df.columns:
        df["P/L"] = pd.to_numeric(df["P/L"], errors="coerce").fillna(0.0)
    elif "Profit" in df.columns:  # fallback bila kolom sebelumnya bernama Profit
        df["P/L"] = pd.to_numeric(df["Profit"], errors="coerce").fillna(0.0)
    else:
        df["P/L"] = 0.0
    existing_pl_sum = float(df["P/L"].sum())

# compute equity sekarang
equity_awal = float(equity_awal_saved)
equity_sekarang = equity_awal + existing_pl_sum

st.sidebar.metric("Equity Sekarang", f"{equity_sekarang:.2f}")
st.sidebar.caption(f"Akun: {tipe_akun_saved} | Multiplier: {multiplier_saved}")

# -----------------------
# FORM INPUT (lebih lengkap offline)
# -----------------------
st.header("✍️ Input Transaksi Baru")

with st.form("trade_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        pair = st.text_input("Pair (mis: XAUUSD)", "")
        jam = st.text_input("Jam (HH:MM, optional)", datetime.now().strftime("%H:%M"))
        entry_price = st.number_input("Entry (price)", value=0.0, format="%.5f")
        sl_price = st.number_input("SL (price)", value=0.0, format="%.5f")
        pl_manual = st.number_input("P/L Manual (opsional, kosongkan 0 untuk otomatis)", value=0.0, format="%.2f")
    with col2:
        tanggal = st.date_input("Tanggal", value=datetime.today())
        buy_sell = st.selectbox("Buy/Sell", ["BUY", "SELL"])
        exit_price = st.number_input("Exit (price, optional untuk otomatis)", value=0.0, format="%.5f")
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
    # compute P/L logic:
    # priority:
    # 1) if status == 'BE' -> P/L = 0
    # 2) elif pl_manual != 0 -> use pl_manual
    # 3) elif entry and exit present -> compute (exit-entry)*lot*multiplier with direction
    # 4) else -> 0
    try:
        multiplier = float(multiplier_saved)
    except:
        multiplier = float(multiplier_input)

    if status == "BE":
        pl_value = 0.0
    elif abs(pl_manual) > 1e-9:
        pl_value = float(pl_manual)
    elif (entry_price != 0.0) and (exit_price != 0.0):
        direction = 1 if buy_sell == "BUY" else -1
        # simple P/L calculation; sesuaikan multiplier jika ingin mencerminkan nilai kontrak sebenarnya
        pl_value = (exit_price - entry_price) * lot * multiplier * direction
    else:
        pl_value = 0.0

    # compute new ID and equity
    # Note: get_all_values includes header, so number_of_records = len(vals)-1
    vals = sheet.get_all_values()
    num_existing = max(0, len(vals) - 1)
    new_id = num_existing + 1

    new_equity = equity_awal + existing_pl_sum + pl_value

    # prepare row consistent with HEADER
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

    try:
        sheet.append_row(row, value_input_option="USER_ENTERED")
        st.success("✅ Transaksi berhasil disimpan ke Google Sheets!")
        # re-read data and refresh display immediately
        raw_data = sheet.get_all_records()
        df = pd.DataFrame(raw_data)
        if "P/L" in df.columns:
            df["P/L"] = pd.to_numeric(df["P/L"], errors="coerce").fillna(0.0)
    except Exception as e:
        st.error("Gagal menyimpan transaksi ke Google Sheets:\n" + str(e))

# -----------------------
# Tampilkan data (sudah re-read setelah simpan)
# -----------------------
st.subheader("📊 Riwayat Transaksi")
try:
    raw_data = sheet.get_all_records()
    df = pd.DataFrame(raw_data)
    if not df.empty:
        # convert numeric columns
        if "P/L" in df.columns:
            df["P/L"] = pd.to_numeric(df["P/L"], errors="coerce").fillna(0.0)
        if "Entry" in df.columns:
            df["Entry"] = pd.to_numeric(df["Entry"], errors="coerce")
        if "Exit" in df.columns:
            df["Exit"] = pd.to_numeric(df["Exit"], errors="coerce")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Belum ada transaksi yang tercatat.")
except Exception as e:
    st.error("Gagal menampilkan data:\n" + str(e))
