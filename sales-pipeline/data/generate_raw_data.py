"""
generate_raw_data.py
---------------------
Simulates a raw sales export (e.g. from a POS / e-commerce system) complete
with the kind of mess real-world data actually has: duplicate rows, nulls,
inconsistent casing, stray whitespace, mixed date formats, and a few bad
numeric values. The ETL pipeline (etl/etl_pipeline.py) is responsible for
cleaning this into an analysis-ready dataset.

Run:
    python data/generate_raw_data.py
Produces:
    data/raw/sales_raw.csv
"""

import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)
np.random.seed(42)

N_ROWS = 6000
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)

REGIONS = ["North", "South", "East", "West", "Central"]
REGION_CASING_VARIANTS = {
    "North": ["North", "north", " North", "NORTH"],
    "South": ["South", "south", " South ", "SOUTH"],
    "East": ["East", "east", "East "],
    "West": ["West", "west", " West"],
    "Central": ["Central", "central", "CENTRAL"],
}

CATEGORIES = {
    "Electronics": ["Wireless Mouse", "Mechanical Keyboard", "USB-C Hub", "27in Monitor", "Webcam HD",
                    "Bluetooth Speaker", "Noise Cancelling Headphones", "Portable SSD 1TB", "Smartwatch", "Power Bank"],
    "Home & Kitchen": ["Air Fryer", "Coffee Maker", "Blender", "Electric Kettle", "Vacuum Cleaner",
                        "Non-stick Pan Set", "Toaster", "Rice Cooker"],
    "Apparel": ["Running Shoes", "Denim Jacket", "Cotton T-Shirt", "Wool Sweater", "Yoga Pants"],
    "Office Supplies": ["Ergonomic Chair", "Standing Desk", "Notebook Pack", "Desk Lamp", "Whiteboard"],
    "Sports & Outdoors": ["Yoga Mat", "Camping Tent", "Water Bottle", "Dumbbell Set", "Cycling Helmet"],
}

PRICE_RANGE = {
    "Electronics": (25, 450),
    "Home & Kitchen": (20, 220),
    "Apparel": (15, 120),
    "Office Supplies": (10, 350),
    "Sports & Outdoors": (12, 300),
}

PAYMENT_METHODS = ["Credit Card", "Debit Card", "PayPal", "UPI", "Cash on Delivery"]
CHANNELS = ["Online", "In-Store", "Mobile App"]

customers = [
    {"customer_id": f"CUST{1000+i}", "name": fake.name(), "email": fake.email()}
    for i in range(900)
]

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%Y/%m/%d"]


def random_date():
    delta_days = (END_DATE - START_DATE).days
    d = START_DATE + timedelta(days=random.randint(0, delta_days))
    fmt = random.choices(DATE_FORMATS, weights=[0.55, 0.25, 0.1, 0.1])[0]
    return d.strftime(fmt)


rows = []
for i in range(1, N_ROWS + 1):
    category = random.choices(
        list(CATEGORIES.keys()), weights=[0.32, 0.22, 0.18, 0.14, 0.14]
    )[0]
    product = random.choice(CATEGORIES[category])
    low, high = PRICE_RANGE[category]
    unit_price = round(random.uniform(low, high), 2)
    quantity = random.choices([1, 2, 3, 4, 5], weights=[0.5, 0.25, 0.12, 0.08, 0.05])[0]
    region_clean = random.choices(REGIONS, weights=[0.22, 0.2, 0.19, 0.21, 0.18])[0]
    region_raw = random.choice(REGION_CASING_VARIANTS[region_clean])
    customer = random.choice(customers)

    discount_pct = random.choices([0, 5, 10, 15, 20], weights=[0.55, 0.15, 0.15, 0.1, 0.05])[0]

    row = {
        "order_id": f"ORD{100000+i}",
        "order_date": random_date(),
        "customer_id": customer["customer_id"],
        "customer_name": customer["name"],
        "region": region_raw,
        "product_name": product,
        "category": category,
        "unit_price": unit_price,
        "quantity": quantity,
        "discount_pct": discount_pct,
        "payment_method": random.choice(PAYMENT_METHODS),
        "sales_channel": random.choice(CHANNELS),
    }
    rows.append(row)

df = pd.DataFrame(rows)

# ---- inject realistic messiness ----

# 1. Duplicate ~2% of rows (common in raw exports with retry/re-sync issues)
dupes = df.sample(frac=0.02, random_state=1)
df = pd.concat([df, dupes], ignore_index=True)

# 2. Null out a handful of fields
for col, frac in [("discount_pct", 0.03), ("payment_method", 0.02), ("customer_name", 0.01)]:
    idx = df.sample(frac=frac, random_state=2).index
    df.loc[idx, col] = np.nan

# 3. A few negative / bad quantities and prices (data entry errors, refunds miscoded)
bad_idx = df.sample(n=15, random_state=3).index
df.loc[bad_idx, "quantity"] = df.loc[bad_idx, "quantity"] * -1

bad_price_idx = df.sample(n=10, random_state=4).index
df.loc[bad_price_idx, "unit_price"] = 0

# 4. Some fully blank rows (export glitches)
blank_idx = df.sample(n=5, random_state=5).index
df.loc[blank_idx, ["unit_price", "quantity", "region"]] = np.nan

# 5. Shuffle rows so it doesn't look synthetically generated in order
df = df.sample(frac=1, random_state=6).reset_index(drop=True)

df.to_csv("data/raw/sales_raw.csv", index=False)
print(f"Generated {len(df):,} raw rows -> data/raw/sales_raw.csv")
