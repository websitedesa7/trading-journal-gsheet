import streamlit as st
import pandas as pd
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime

# === KONEKSI GOOGLE SHEETS ===
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Ganti dengan nama Google Sheets kamu
SHEET_NAME = "Jurnal_Trading"
sheet = client.open(SHEET_NAME).sheet1

# === SETUP STREAMLIT ===
st.set_page_config(page_title="Jurnal Trading", layout="wide")
st.title("📓 Jurnal Trading – Google Sheets Version")

if "equity" not in st.session_state:
    st.session_state.equity = 0.0
if "equity_awal" not in st.session_state:
    st.session_state.equity_awal = 0.0

# === SIDEBAR PENGATURAN AKUN ===
with st.sidebar:
    st.header("⚙️ Pengaturan Akun")
    akun_type = st.selectbox("Tipe Akun", ["Micro", "Standard"])
    eq_awal = st.number_input("Equity Awal", value=1000.0, step=100.0)

    if st.session_state.equity_awal == 0.0:
        st.session_state.equity_awal = eq_awal
        st.session_state.equity = eq_awal

    st.metric("Equity Sekarang", value=st.session_state.equity)
    st.caption(f"Akun: {akun_type} | Equity Awal: {st.session_state.equity_awal}")

# === FORM INPUT TRANSAKSI ===
st.subheader("✍️ Input Transaksi Baru")

with st.form("trade_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        pair = st.text_input("Pair", value="XAUUSD")
        tanggal = st.date_input("Tanggal")
        jam = st.time_input("Jam")
    with col2:
        arah = st.selectbox("BUY / SELL", ["BUY", "SELL"])
        entry = st.number_input("Entry", value=0.0, step=0.01)
        lot = st.number_input("Lot", value=0.10, step=0.10)
    with col3:
        sl = st.number_input("SL", value=0.0, step=0.01)
        tp1 = st.number_input("TP1", value=0.0, step=0.01)
        tp2 = st.number_input("TP2", value=0.0, step=0.01)

    status = st.selectbox("Status", ["SL", "TP", "BE", "Manual"])
    note = st.text_area("Note")
    ss_entry = st.text_input("Link Screenshot Entry")
    ss_exit = st.text_input("Link Screenshot Exit")
    exit_price = st.number_input("Exit Price", value=0.0, step=0.01)
    pl_manual = st.number_input("P/L Manual (opsional)", value=0.0, step=0.01)

    submitted = st.form_submit_button("💾 Simpan Transaksi")

# === SIMPAN DATA KE GOOGLE SHEETS ===
if submitted:
    # Hitung P/L
    pl_value = pl_manual
    hasil = "Profit" if pl_value > 0 else "Loss" if pl_value < 0 else "BE"

    # Update equity
    st.session_state.equity += pl_value

    trade = {
        "ID": len(sheet.get_all_values()),  # auto increment
        "Pair": pair,
        "Tanggal": tanggal.strftime("%Y-%m-%d"),
        "Jam": jam.strftime("%H:%M:%S"),
        "Arah": arah,
        "Entry": entry,
        "Lot": lot,
        "SL": sl,
        "TP1": tp1,
        "TP2": tp2,
        "Status": status,
        "Note": note,
        "SS Entry": ss_entry,
        "Exit": exit_price,
        "Hasil": hasil,
        "SS Exit": ss_exit,
        "P/L": pl_value,
        "Equity": st.session_state.equity,
        "Evaluasi": ""
    }

    row = list(trade.values())
    sheet.append_row(row, value_input_option="USER_ENTERED")
    st.success(f"Transaksi berhasil disimpan ke Google Sheets ✅ | Equity Sekarang: {st.session_state.equity}")

# === TAMPILKAN DATA DARI GOOGLE SHEETS ===
st.subheader("📋 Daftar Transaksi")
data = sheet.get_all_records()
df = pd.DataFrame(data)

if not df.empty:
    # Filter
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_date = st.date_input("Filter Tanggal", value=None)
    with col2:
        filter_pair = st.selectbox("Filter Pair", ["All"] + df["Pair"].unique().tolist())
    with col3:
        filter_status = st.selectbox("Filter Status", ["All"] + df["Status"].unique().tolist())

    filtered_df = df.copy()
    if filter_date:
        filtered_df = filtered_df[filtered_df["Tanggal"] == filter_date.strftime("%Y-%m-%d")]
    if filter_pair != "All":
        filtered_df = filtered_df[filtered_df["Pair"] == filter_pair]
    if filter_status != "All":
        filtered_df = filtered_df[filtered_df["Status"] == filter_status]

    st.dataframe(filtered_df, use_container_width=True)

    # Export Excel
    excel_buffer = io.BytesIO()
    filtered_df.to_excel(excel_buffer, index=False, engine="openpyxl")
    st.download_button("📥 Download Excel", data=excel_buffer.getvalue(),
                       file_name="jurnal_trading.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Export PDF
    def create_pdf(dataframe):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph("📊 Jurnal Trading", styles['Title']))
        story.append(Spacer(1, 12))

        table_data = [list(dataframe.columns)] + dataframe.values.tolist()
        table = Table(table_data)
        table.setStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ])
        story.append(table)
        doc.build(story)
        buffer.seek(0)
        return buffer

    pdf_file = create_pdf(filtered_df)
    st.download_button("📥 Download PDF", data=pdf_file,
                       file_name="jurnal_trading.pdf", mime="application/pdf")
else:
    st.info("Belum ada transaksi tersimpan di Google Sheets.")
