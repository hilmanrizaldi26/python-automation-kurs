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
BTN_URL = "https://www.btn.co.id/en/Simulation"
SPREADSHEET_ID = "1xQ9mH6YmrKaqG5rNNSQR2wfH3u8DXOteFo2ed_Sw_F0"
SERVICE_ACCOUNT_FILE = "service_account.json"

# Live scrape BTN
options = Options()
options.page_load_strategy = "none"
options.binary_location = "/usr/bin/chromium-browser"   # lokasi Chromium di runner
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)

try:
    print("Membuka halaman Bank BTN...")
    driver.get(BTN_URL)

    time.sleep(20)

    driver.execute_cdp_cmd("Page.stopLoading", {})
    time.sleep(2)

    html = driver.execute_script("return document.documentElement.outerHTML;")

    print("\nCEK HALAMAN")
    print("Title          :", driver.title)
    print("Panjang HTML   :", len(html))
    print("Ada Kurs Valas :", "Kurs Valas" in html)
    print("Ada TT         :", ">TT<" in html or "TT" in html)
finally:
    driver.quit()

# =====================================================
# 2. EKSTRAK DATA KURS
# =====================================================
soup = BeautifulSoup(html, "html.parser")
tables = soup.find_all("table")

target_table = None
for table in tables:
    text = table.get_text(" ", strip=True)
    if "Currency" in text and "TT" in text and "Bank Note" in text:
        target_table = table
        break

if target_table is None:
    raise RuntimeError("Tabel kurs BTN tidak ditemukan.")

rows = target_table.find("tbody").find_all("tr")
result = []

for row in rows:
    cells = row.find_all("td")
    if len(cells) < 5:
        continue

    currency = cells[0].get_text(strip=True)
    tt_bid = cells[1].get_text(strip=True)
    tt_ask = cells[2].get_text(strip=True)

    result.append({
        "currency": currency,
        "buyRateCounter": tt_bid,
        "sellRateCounter": tt_ask,
        "buyRateERate": None,
        "sellRateERate": None
    })

print("\nJumlah data ditemukan:", len(result))
if len(result) == 0:
    raise RuntimeError("Data kurs BTN tidak ditemukan.")

# =====================================================
# 3. JADIKAN DATAFRAME
# =====================================================
df = pd.DataFrame(result)
rate_cols = ["buyRateCounter", "sellRateCounter"]

for col in rate_cols:
    df[col] = df[col].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    df[col] = pd.to_numeric(df[col], errors="coerce")

df = df[["currency", "buyRateCounter", "sellRateCounter", "buyRateERate", "sellRateERate"]]

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
df.insert(0, "timestamp", timestamp)
df["BANK"] = "BTN"

print("\nDATA LIVE")
print(df)

# =====================================================
# 4. HUBUNGKAN KE GOOGLE SHEETS
# =====================================================
print("\nMenghubungkan ke Google Sheets...")
gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
spreadsheet = gc.open_by_key(SPREADSHEET_ID)
worksheet = spreadsheet.get_worksheet(3)

print("Spreadsheet:", spreadsheet.title)
print("Worksheet  :", worksheet.title)

header = ["timestamp", "currency", "buyRateCounter", "sellRateCounter",
          "buyRateERate", "sellRateERate", "BANK"]
if len(worksheet.get_all_values()) == 0:
    worksheet.append_row(header)

rows = df.values.tolist()
worksheet.append_rows(rows, value_input_option="USER_ENTERED")

print("\nBERHASIL")
print(f"{len(rows)} kurs live BTN masuk ke Google Sheets")
print("Waktu:", timestamp)
