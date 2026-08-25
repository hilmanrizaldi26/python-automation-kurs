from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from datetime import datetime
import time
import re

import pandas as pd
import gspread


# =====================================================
# KONFIGURASI
# =====================================================

BRI_URL = "https://bri.co.id/web/guest/id/kurs-detail"

SPREADSHEET_ID = "1xQ9mH6YmrKaqG5rNNSQR2wfH3u8DXOteFo2ed_Sw_F0"

SERVICE_ACCOUNT_FILE = "service_account.json"

# =====================================================
# 1. LIVE SCRAPING BRI
# =====================================================

options = Options()

# Untuk awal jangan headless dulu
driver = webdriver.Chrome(options=options)

try:
    print("Membuka BRI...")

    driver.get(BRI_URL)

    time.sleep(15)

    html = driver.page_source

    print("\n=== CEK HALAMAN ===")
    print("Title              :", driver.title)
    print("Panjang HTML       :", len(html))
    print("Ada listTable      :", "listTable" in html)
    print("Ada buyRateCounter :", "buyRateCounter" in html)

finally:
    driver.quit()


# =====================================================
# 2. EKSTRAK DATA KURS
# =====================================================

pattern = (
    r'\{\\"buyRateCounter\\":\\"([^"]+)\\",'
    r'\\"buyRateERate\\":\\"([^"]+)\\",'
    r'\\"currency\\":\\"([^"]+)\\".*?'
    r'\\"sellRateCounter\\":\\"([^"]+)\\",'
    r'\\"sellRateERate\\":\\"([^"]+)\\"'
)

matches = re.findall(pattern, html)

print("\nJumlah data ditemukan:", len(matches))

if len(matches) != 22:
    raise RuntimeError(
        f"Data kurs tidak lengkap. Ditemukan {len(matches)} mata uang."
    )


# =====================================================
# 3. JADIKAN DATAFRAME
# =====================================================

df = pd.DataFrame(
    matches,
    columns=[
        "buyRateCounter",
        "buyRateERate",
        "currency",
        "sellRateCounter",
        "sellRateERate"
    ]
)

rate_cols = [
    "buyRateCounter",
    "buyRateERate",
    "sellRateCounter",
    "sellRateERate"
]

df[rate_cols] = df[rate_cols].apply(
    pd.to_numeric,
    errors="coerce"
)

df = df[
    [
        "currency",
        "buyRateCounter",
        "sellRateCounter",
        "buyRateERate",
        "sellRateERate"
    ]
]

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

df.insert(0, "timestamp", timestamp)

# Tambahkan nama bank
df["BANK"] = "BRI"

print("\n=== DATA LIVE ===")
print(df)


# =====================================================
# 4. HUBUNGKAN KE GOOGLE SHEETS
# =====================================================

print("\nMenghubungkan ke Google Sheets...")

gc = gspread.service_account(
    filename=SERVICE_ACCOUNT_FILE
)

spreadsheet = gc.open_by_key(
    SPREADSHEET_ID
)

worksheet = spreadsheet.get_worksheet(0)

print("Spreadsheet:", spreadsheet.title)
print("Worksheet  :", worksheet.title)


# =====================================================
# 5. HEADER JIKA SHEET KOSONG
# =====================================================

header = [
    "timestamp",
    "currency",
    "buyRateCounter",
    "sellRateCounter",
    "buyRateERate",
    "sellRateERate",
    "BANK"
]s

if len(worksheet.get_all_values()) == 0:
    worksheet.append_row(header)


# =====================================================
# 6. APPEND 22 BARIS
# =====================================================

rows = df.values.tolist()

worksheet.append_rows(
    rows,
    value_input_option="USER_ENTERED"
)

print("\n======================================")
print("BERHASIL")
print("22 kurs live masuk ke Google Sheets")
print("Waktu:", timestamp)
print("======================================")
