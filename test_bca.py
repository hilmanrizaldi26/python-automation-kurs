from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from bs4 import BeautifulSoup
from datetime import datetime
import time

import pandas as pd
import gspread

# Configuration
BCA_URL = "https://www.bca.co.id/id/informasi/kurs"

SPREADSHEET_ID = "1xQ9mH6YmrKaqG5rNNSQR2wfH3u8DXOteFo2ed_Sw_F0"

SERVICE_ACCOUNT_FILE = "service_account.json"

# Live scrape BCA
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)

try:
    print("Membuka BCA...")

    driver.get(BCA_URL)

    time.sleep(15)

    html = driver.page_source

    print("\nCEK HALAMAN")
    print("Title              :", driver.title)
    print("Panjang HTML       :", len(html))
    print("Ada e-Rate         :", "e-Rate" in html)
    print("Ada TT Counter     :", "TT Counter" in html)
    print("Ada data-value-buy :", "data-value-buy" in html)

finally:
    driver.quit()

# Extract exchange rate data
soup = BeautifulSoup(html, "html.parser")

currency_elements = soup.select(
    ".content-currency1 .a-dropdown-currency1"
)

result = []
seen_currency = set()

for element in currency_elements:
    currency = element.get("data-text")

    if currency == "IDR":
        continue

    if currency in seen_currency:
        continue

    buy_values = element.get("data-value-buy", "").split("-")
    sell_values = element.get("data-value-sell", "").split("-")

    if len(buy_values) != 3 or len(sell_values) != 3:
        continue

    result.append(
        {
            "currency": currency,
            "buyRateCounter": buy_values[1],
            "sellRateCounter": sell_values[1],
            "buyRateERate": buy_values[0],
            "sellRateERate": sell_values[0]
        }
    )

    seen_currency.add(currency)

print("\nJumlah data ditemukan:", len(result))

if len(result) != 18:
    raise RuntimeError(
        f"Data kurs tidak lengkap. Ditemukan {len(result)} mata uang."
    )

# Convert to DataFrame
df = pd.DataFrame(result)

rate_cols = [
    "buyRateCounter",
    "sellRateCounter",
    "buyRateERate",
    "sellRateERate"
]

df[rate_cols] = df[rate_cols].apply(
    pd.to_numeric,
    errors = "coerce"
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

# Add bank name
df["BANK"] = "BCA"

print("\nDATA LIVE")
print(df)

# Connect to Google Sheets
print("\nMenghubungkan ke Google Sheets...")

gc = gspread.service_account(
    filename = SERVICE_ACCOUNT_FILE
)

spreadsheet = gc.open_by_key(
    SPREADSHEET_ID
)

worksheet = spreadsheet.get_worksheet(2)

print("Spreadsheet:", spreadsheet.title)
print("Worksheet  :", worksheet.title)

# Create header if sheet is empty
header = [
    "timestamp",
    "currency",
    "buyRateCounter",
    "sellRateCounter",
    "buyRateERate",
    "sellRateERate",
    "BANK"
]

if len(worksheet.get_all_values()) == 0:
    worksheet.append_row(header)

# Append 18 rows
rows = df.values.tolist()

worksheet.append_rows(
    rows,
    value_input_option = "USER_ENTERED"
)

print("\nBERHASIL")
print("18 kurs live BCA masuk ke Google Sheets")
print("Waktu:", timestamp)
