from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from bs4 import BeautifulSoup
from datetime import datetime
import time
import pandas as pd
import gspread

# =====================================================
# KONFIGURASI
# =====================================================
MANDIRI_URL = "https://www.bankmandiri.co.id/kurs"
SPREADSHEET_ID = "1xQ9mH6YmrKaqG5rNNSQR2wfH3u8DXOteFo2ed_Sw_F0"
SERVICE_ACCOUNT_FILE = "service_account.json"

# Konfigurasi umum untuk semua bank
def get_driver():
    options = Options()
    options.binary_location = "/usr/bin/chromium-browser"  # lokasi Chromium di runner
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)

# =====================================================
# 1. LIVE SCRAPING MANDIRI
# =====================================================
print("Membuka Bank Mandiri...")
driver = get_driver()
try:
    driver.get(MANDIRI_URL)
    time.sleep(15)
    html = driver.page_source

    print("\nCEK HALAMAN")
    print("Title         :", driver.title)
    print("Panjang HTML  :", len(html))
    print("Ada TT Counter:", "TT Counter" in html)
    print("Ada Mata Uang :", "Mata Uang" in html)
finally:
    driver.quit()

# =====================================================
# 2. EKSTRAK DATA KURS
# =====================================================
soup = BeautifulSoup(html, "html.parser")
table = soup.find("table", id="_Exchange_Rate_Portlet_INSTANCE_9070nSEKk62r_display")

if table is None:
    raise RuntimeError("Tabel kurs Bank Mandiri tidak ditemukan.")

rows = table.find("tbody").find_all("tr")
result = []

for row in rows:
    cells = row.find_all("td")
    if len(cells) < 7:
        continue

    currency = cells[0].get_text(strip=True)
    special_buy = cells[1].get_text(strip=True)
    special_sell = cells[2].get_text(strip=True)
    tt_buy = cells[3].get_text(strip=True)
    tt_sell = cells[4].get_text(strip=True)

    result.append({
        "currency": currency,
        "buyRateCounter": tt_buy,
        "sellRateCounter": tt_sell,
        "buyRateERate": special_buy,
        "sellRateERate": special_sell
    })

print("\nJumlah data ditemukan:", len(result))
if len(result) != 19:
    raise RuntimeError(f"Data kurs tidak lengkap. Ditemukan {len(result)} mata uang.")

# =====================================================
# 3. JADIKAN DATAFRAME
# =====================================================
df = pd.DataFrame(result)
rate_cols = ["buyRateCounter", "sellRateCounter", "buyRateERate", "sellRateERate"]

for col in rate_cols:
    df[col] = df[col].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    df[col] = pd.to_numeric(df[col], errors="coerce")

df = df[["currency", "buyRateCounter", "sellRateCounter", "buyRateERate", "sellRateERate"]]

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
df.insert(0, "timestamp", timestamp)
df["BANK"] = "MANDIRI"

print("\nDATA LIVE")
print(df)

# =====================================================
# 4. HUBUNGKAN KE GOOGLE SHEETS
# =====================================================
print("\nMenghubungkan ke Google Sheets...")
gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
spreadsheet = gc.open_by_key(SPREADSHEET_ID)
worksheet = spreadsheet.get_worksheet(1)

print("Spreadsheet:", spreadsheet.title)
print("Worksheet  :", worksheet.title)

# =====================================================
# 5. HEADER JIKA SHEET KOSONG
# =====================================================
header = ["timestamp", "currency", "buyRateCounter", "sellRateCounter",
          "buyRateERate", "sellRateERate", "BANK"]
if len(worksheet.get_all_values()) == 0:
    worksheet.append_row(header)

# =====================================================
# 6. APPEND 19 BARIS
# =====================================================
rows = df.values.tolist()
worksheet.append_rows(rows, value_input_option="USER_ENTERED")

print("\nBERHASIL")
print("19 kurs live Bank Mandiri masuk ke Google Sheets")
print("Waktu:", timestamp)
