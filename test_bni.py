from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from bs4 import BeautifulSoup
from datetime import datetime
import time

import pandas as pd
import gspread

# Configuration
BNI_URL = "https://www.bni.co.id/id-id/beranda/informasi-valas"

SPREADSHEET_ID = "1xQ9mH6YmrKaqG5rNNSQR2wfH3u8DXOteFo2ed_Sw_F0"

SERVICE_ACCOUNT_FILE = "service_account.json"

# Live scrape BNI
options = Options()
options.page_load_strategy = "none"

driver = webdriver.Chrome(options = options)

try:
    print("Membuka BNI...")

    driver.get(BNI_URL)

    # Wait for BNI content to render
    time.sleep(20)

    # Stop remaining resources
    driver.execute_cdp_cmd(
        "Page.stopLoading",
        {}
    )

    time.sleep(2)

    # Get rendered HTML
    html = driver.execute_script(
        "return document.documentElement.outerHTML;"
    )

    print("\nCEK HALAMAN")
    print("Title              :", driver.title)
    print("Panjang HTML       :", len(html))
    print("Ada Special Rates  :", "Special Rates" in html)
    print("Ada TT Counter     :", "TT Counter" in html)
    print("Ada Bank Notes     :", "Bank Notes" in html)

finally:
    driver.quit()

# Parse rendered HTML
soup = BeautifulSoup(html, "html.parser")

# Extract BNI exchange-rate table
def extract_table(title_id):
    title = soup.find(
        "span",
        id = title_id
    )

    if title is None:
        raise RuntimeError(
            f"Bagian {title_id} tidak ditemukan."
        )

    container = title.find_parent(
        "div",
        class_ = lambda x: x and "col-sm-4" in x
    )

    if container is None:
        raise RuntimeError(
            f"Container {title_id} tidak ditemukan."
        )

    table = container.find("table")

    if table is None:
        raise RuntimeError(
            f"Tabel {title_id} tidak ditemukan."
        )

    table_rows = table.find("tbody").find_all("tr")

    data = {}

    for row in table_rows:
        cells = row.find_all("td")

        if len(cells) < 3:
            continue

        currency = cells[0].get_text(
            " ",
            strip = True
        ).split()[-1]

        buy = cells[1].get_text(strip = True)
        sell = cells[2].get_text(strip = True)

        data[currency] = {
            "buy": buy,
            "sell": sell
        }

    return data

# Extract Special Rates
special_rates = extract_table(
    "dnn_ctr6793_BNIValasInfoView_lblTitleCounter"
)

# Extract TT Counter
tt_counter = extract_table(
    "dnn_ctr6793_BNIValasInfoView_lblTitleBankNotes"
)

print("\nJumlah Special Rates ditemukan:", len(special_rates))
print("Jumlah TT Counter ditemukan   :", len(tt_counter))

if len(tt_counter) != 16:
    raise RuntimeError(
        f"Data kurs tidak lengkap. Ditemukan {len(tt_counter)} mata uang."
    )

# Combine TT Counter and Special Rates
result = []

for currency, counter_rate in tt_counter.items():
    special_rate = special_rates.get(
        currency,
        {}
    )

    result.append(
        {
            "buyRateCounter": counter_rate["buy"],
            "buyRateERate": special_rate.get("buy"),
            "currency": currency,
            "sellRateCounter": counter_rate["sell"],
            "sellRateERate": special_rate.get("sell")
        }
    )

# Convert data to DataFrame
df = pd.DataFrame(
    result,
    columns = [
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

for col in rate_cols:
    df[col] = (
        df[col]
        .astype("string")
        .str.replace(".", "", regex = False)
        .str.replace(",", ".", regex = False)
    )

    df[col] = pd.to_numeric(
        df[col],
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

df.insert(
    0,
    "timestamp",
    timestamp
)

# Add bank name
df["BANK"] = "BNI"

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

worksheet = spreadsheet.get_worksheet(4)

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

# Convert missing values to empty cells
df = df.astype(object).where(
    pd.notna(df),
    None
)

rows = df.values.tolist()

worksheet.append_rows(
    rows,
    value_input_option = "USER_ENTERED"
)

print("\nBERHASIL")
print("16 kurs live BNI masuk ke Google Sheets")
print("Waktu:", timestamp)