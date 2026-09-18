-- ============================================================
-- schema.sql
-- Analysis-ready star schema for the sales pipeline.
-- Target: PostgreSQL 13+ (also works on SQLite via the ETL script,
-- which auto-translates types where needed).
-- ============================================================

DROP TABLE IF EXISTS fact_sales CASCADE;
DROP TABLE IF EXISTS dim_customer CASCADE;
DROP TABLE IF EXISTS dim_product CASCADE;
DROP TABLE IF EXISTS dim_region CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;

CREATE TABLE dim_customer (
    customer_id     VARCHAR(20) PRIMARY KEY,
    customer_name   VARCHAR(150) NOT NULL
);

CREATE TABLE dim_product (
    product_id      SERIAL PRIMARY KEY,
    product_name    VARCHAR(150) NOT NULL,
    category        VARCHAR(80) NOT NULL,
    UNIQUE (product_name, category)
);

CREATE TABLE dim_region (
    region_id       SERIAL PRIMARY KEY,
    region_name     VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE dim_date (
    date_id         DATE PRIMARY KEY,
    year            INT NOT NULL,
    quarter         INT NOT NULL,
    month           INT NOT NULL,
    month_name      VARCHAR(15) NOT NULL,
    day             INT NOT NULL,
    day_of_week     VARCHAR(15) NOT NULL,
    is_weekend      BOOLEAN NOT NULL
);

CREATE TABLE fact_sales (
    order_id        VARCHAR(20) PRIMARY KEY,
    date_id         DATE REFERENCES dim_date(date_id),
    customer_id     VARCHAR(20) REFERENCES dim_customer(customer_id),
    product_id      INT REFERENCES dim_product(product_id),
    region_id       INT REFERENCES dim_region(region_id),
    payment_method  VARCHAR(30),
    sales_channel   VARCHAR(30),
    unit_price      NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    quantity        INT NOT NULL CHECK (quantity > 0),
    discount_pct    NUMERIC(5, 2) DEFAULT 0 CHECK (discount_pct >= 0 AND discount_pct <= 100),
    gross_revenue   NUMERIC(12, 2) NOT NULL,
    net_revenue     NUMERIC(12, 2) NOT NULL
);

CREATE INDEX idx_fact_sales_date ON fact_sales(date_id);
CREATE INDEX idx_fact_sales_region ON fact_sales(region_id);
CREATE INDEX idx_fact_sales_product ON fact_sales(product_id);
