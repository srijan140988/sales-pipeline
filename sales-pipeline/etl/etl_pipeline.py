"""
etl_pipeline.py
----------------
End-to-end ETL pipeline for the sales dataset.

    EXTRACT  -> read the raw, messy CSV export
    TRANSFORM -> clean, standardize, deduplicate, engineer fields
    LOAD      -> write into a normalized star schema (dim_* + fact_sales)

Works against PostgreSQL by default. If no DATABASE_URL is configured
(or Postgres isn't reachable), it automatically falls back to a local
SQLite file (data/processed/sales.db) so the whole pipeline can be run
and demoed with zero external setup.

Usage:
    python etl/etl_pipeline.py
"""

import os
import sys
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("etl")

ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "data" / "raw" / "sales_raw.csv"
PROCESSED_PATH = ROOT / "data" / "processed" / "sales_clean.csv"
SCHEMA_PATH = ROOT / "sql" / "schema.sql"
SQLITE_PATH = ROOT / "data" / "processed" / "sales.db"

# postgresql+psycopg2://user:password@host:port/dbname
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


# ------------------------------------------------------------------
# EXTRACT
# ------------------------------------------------------------------
def extract(path: Path) -> pd.DataFrame:
    log.info("EXTRACT: reading raw file %s", path)
    df = pd.read_csv(path)
    log.info("EXTRACT: %d raw rows loaded", len(df))
    return df


# ------------------------------------------------------------------
# TRANSFORM
# ------------------------------------------------------------------
def transform(df: pd.DataFrame) -> pd.DataFrame:
    log.info("TRANSFORM: starting with %d rows", len(df))
    df = df.copy()

    # --- 1. Drop fully-blank / unusable rows ---
    before = len(df)
    df = df.dropna(subset=["order_id"])
    df = df.dropna(subset=["unit_price", "quantity", "region"], how="all")
    log.info("TRANSFORM: dropped %d unusable rows", before - len(df))

    # --- 2. De-duplicate exact duplicate order rows ---
    before = len(df)
    df = df.drop_duplicates(subset=["order_id"], keep="first")
    log.info("TRANSFORM: removed %d duplicate order_id rows", before - len(df))

    # --- 3. Standardize text fields (trim whitespace, fix casing) ---
    text_cols = ["customer_name", "region", "product_name", "category",
                 "payment_method", "sales_channel"]
    for col in text_cols:
        df[col] = df[col].astype(str).str.strip()
        df.loc[df[col].isin(["nan", "None", ""]), col] = np.nan

    df["region"] = df["region"].str.title()
    df["category"] = df["category"].str.title()
    df["payment_method"] = df["payment_method"].fillna("Unknown")

    # --- 4. Parse mixed date formats robustly ---
    df["order_date"] = pd.to_datetime(df["order_date"], format="mixed", dayfirst=False, errors="coerce")
    # A handful of ambiguous DD/MM vs MM/DD entries may fail the first pass; retry with dayfirst
    retry_mask = df["order_date"].isna()
    if retry_mask.any():
        df.loc[retry_mask, "order_date"] = pd.to_datetime(
            df.loc[retry_mask, "order_date"], dayfirst=True, errors="coerce"
        )
    before = len(df)
    df = df.dropna(subset=["order_date"])
    log.info("TRANSFORM: dropped %d rows with unparseable dates", before - len(df))

    # --- 5. Fix numeric anomalies ---
    # Negative quantities -> treat as data-entry sign errors, take absolute value
    df["quantity"] = df["quantity"].abs()
    # Zero-price or missing price/quantity/region rows can't be salvaged for revenue calcs
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    before = len(df)
    df = df[(df["unit_price"] > 0) & (df["quantity"] > 0)]
    log.info("TRANSFORM: dropped %d rows with invalid price/quantity", before - len(df))

    df["discount_pct"] = pd.to_numeric(df["discount_pct"], errors="coerce").fillna(0).clip(0, 100)

    # --- 6. Engineer revenue fields ---
    df["gross_revenue"] = (df["unit_price"] * df["quantity"]).round(2)
    df["net_revenue"] = (df["gross_revenue"] * (1 - df["discount_pct"] / 100)).round(2)

    # --- 7. Drop rows still missing a required dimension key ---
    before = len(df)
    df = df.dropna(subset=["customer_id", "region", "product_name", "category"])
    log.info("TRANSFORM: dropped %d rows missing required dimension keys", before - len(df))

    # --- 8. Customer name backfill (a few names were nulled) ---
    df["customer_name"] = df.groupby("customer_id")["customer_name"].transform(
        lambda s: s.ffill().bfill()
    )
    df["customer_name"] = df["customer_name"].fillna("Unknown Customer")

    df = df.reset_index(drop=True)
    log.info("TRANSFORM: finished with %d clean rows", len(df))
    return df


# ------------------------------------------------------------------
# LOAD
# ------------------------------------------------------------------
def build_dim_date(dates: pd.Series) -> pd.DataFrame:
    unique_dates = pd.to_datetime(dates.unique())
    dim = pd.DataFrame({"date_id": unique_dates})
    dim["year"] = dim["date_id"].dt.year
    dim["quarter"] = dim["date_id"].dt.quarter
    dim["month"] = dim["date_id"].dt.month
    dim["month_name"] = dim["date_id"].dt.strftime("%B")
    dim["day"] = dim["date_id"].dt.day
    dim["day_of_week"] = dim["date_id"].dt.strftime("%A")
    dim["is_weekend"] = dim["date_id"].dt.dayofweek.isin([5, 6])
    return dim.sort_values("date_id").reset_index(drop=True)


def get_engine():
    if DATABASE_URL:
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info("LOAD: connected to PostgreSQL at DATABASE_URL")
            return engine, "postgresql"
        except Exception as e:
            log.warning("LOAD: could not connect to DATABASE_URL (%s). Falling back to SQLite.", e)

    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{SQLITE_PATH}")
    log.info("LOAD: using local SQLite database at %s", SQLITE_PATH)
    return engine, "sqlite"


def load(df: pd.DataFrame, engine, dialect: str):
    log.info("LOAD: building star schema tables")

    dim_customer = (
        df[["customer_id", "customer_name"]]
        .drop_duplicates(subset=["customer_id"])
        .reset_index(drop=True)
    )

    dim_product = (
        df[["product_name", "category"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    dim_product.insert(0, "product_id", range(1, len(dim_product) + 1))

    dim_region = pd.DataFrame({"region_name": sorted(df["region"].unique())})
    dim_region.insert(0, "region_id", range(1, len(dim_region) + 1))

    dim_date = build_dim_date(df["order_date"])
    if dialect == "sqlite":
        dim_date["date_id"] = dim_date["date_id"].dt.strftime("%Y-%m-%d")
        dim_date["is_weekend"] = dim_date["is_weekend"].astype(int)

    # Build fact table with foreign keys resolved
    fact = df.merge(dim_product, on=["product_name", "category"], how="left")
    fact = fact.merge(dim_region, left_on="region", right_on="region_name", how="left")

    fact_sales = fact[[
        "order_id", "order_date", "customer_id", "product_id", "region_id",
        "payment_method", "sales_channel", "unit_price", "quantity",
        "discount_pct", "gross_revenue", "net_revenue",
    ]].rename(columns={"order_date": "date_id"})

    if dialect == "sqlite":
        fact_sales["date_id"] = pd.to_datetime(fact_sales["date_id"]).dt.strftime("%Y-%m-%d")

    # Apply schema.sql for Postgres (SQLite gets simple inferred types via to_sql)
    if dialect == "postgresql":
        with engine.begin() as conn:
            schema_sql = SCHEMA_PATH.read_text()
            for statement in schema_sql.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))
        if_exists = "append"
    else:
        if_exists = "replace"

    dim_customer.to_sql("dim_customer", engine, if_exists=if_exists, index=False)
    dim_product.to_sql("dim_product", engine, if_exists=if_exists, index=False)
    dim_region.to_sql("dim_region", engine, if_exists=if_exists, index=False)
    dim_date.to_sql("dim_date", engine, if_exists=if_exists, index=False)
    fact_sales.to_sql("fact_sales", engine, if_exists=if_exists, index=False)

    log.info(
        "LOAD: wrote %d customers, %d products, %d regions, %d dates, %d fact rows",
        len(dim_customer), len(dim_product), len(dim_region), len(dim_date), len(fact_sales),
    )


def main():
    if not RAW_PATH.exists():
        log.error("Raw data not found at %s. Run data/generate_raw_data.py first.", RAW_PATH)
        sys.exit(1)

    raw_df = extract(RAW_PATH)
    clean_df = transform(raw_df)

    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(PROCESSED_PATH, index=False)
    log.info("Saved cleaned dataset -> %s", PROCESSED_PATH)

    engine, dialect = get_engine()
    load(clean_df, engine, dialect)

    log.info("ETL pipeline complete. Backend: %s", dialect)


if __name__ == "__main__":
    main()
