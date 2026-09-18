# Sales Pipeline — End-to-End ETL, Analytics & Reporting

A complete data analytics pipeline that ingests raw, messy sales data, cleans and
transforms it with Python, loads it into a normalized SQL data warehouse, and
produces both static reports (Matplotlib/Seaborn) and a live interactive
dashboard.

**[Live Dashboard →](#)** _(deploy to Vercel — see below — then drop your link here)_

---

## What this project does

```
 raw CSV export          PostgreSQL / SQLite         Pandas + SQL              Charts +
 (messy, real-world) --> star-schema warehouse   --> analysis layer      -->   Dashboard
      |                        |                          |                       |
 data/raw/            etl/etl_pipeline.py         analysis/sales_analysis.py   dashboard/
 sales_raw.csv         sql/schema.sql              sql/analysis_queries.sql    index.html
```

1. **Extract** — reads a raw sales export (`data/raw/sales_raw.csv`) with realistic
   data-quality issues: duplicate rows, inconsistent casing, mixed date formats,
   nulls, and bad numeric values.
2. **Transform** — `etl/etl_pipeline.py` cleans the data with Pandas: deduplicates,
   standardizes text fields, parses mixed date formats, fixes sign errors on
   quantity, drops unsalvageable rows, and engineers `gross_revenue` /
   `net_revenue` fields.
3. **Load** — writes the cleaned data into a normalized **star schema**
   (`fact_sales` + `dim_customer`, `dim_product`, `dim_region`, `dim_date`) in
   PostgreSQL. If no database is configured, it automatically falls back to a
   local SQLite file so the whole pipeline runs with zero setup.
4. **Analyze** — `sql/analysis_queries.sql` contains 9 business-facing SQL
   queries (revenue trends, top products, regional performance, MoM growth via
   window functions, etc.). `analysis/sales_analysis.py` mirrors these in
   Pandas and generates the charts + dashboard data.
5. **Report** — Matplotlib/Seaborn charts are saved to `reports/figures/`, a
   text summary to `reports/summary_report.txt`, and a `dashboard_data.json`
   is exported for the web dashboard.
6. **Visualize** — `dashboard/index.html` is a self-contained, static
   dashboard (Chart.js) that reads that JSON and renders it as an interactive
   report — deployable to Vercel in one click.

## Tech stack

- **Python** — Pandas, NumPy, Faker (synthetic data)
- **SQL / PostgreSQL** — star schema, joins, window functions, aggregations
  (SQLite fallback for zero-config local runs)
- **SQLAlchemy** / **psycopg2** — database connectivity
- **Matplotlib / Seaborn** — static chart generation
- **Chart.js** — interactive web dashboard (no build step, deploys as-is)

## Project structure

```
sales-pipeline/
├── data/
│   ├── generate_raw_data.py     # synthetic-but-realistic raw sales generator
│   ├── raw/sales_raw.csv        # raw export (messy, as extracted)
│   └── processed/sales_clean.csv# cleaned output of the ETL transform step
├── etl/
│   └── etl_pipeline.py          # extract -> clean/transform -> load
├── sql/
│   ├── schema.sql               # star schema DDL (PostgreSQL)
│   └── analysis_queries.sql     # 9 analysis queries incl. window functions
├── analysis/
│   └── sales_analysis.py        # Pandas aggregations + chart + JSON export
├── reports/
│   ├── figures/                 # generated PNG charts
│   └── summary_report.txt       # generated text summary
├── dashboard/
│   ├── index.html               # interactive dashboard (deploy to Vercel)
│   └── dashboard_data.json      # data consumed by the dashboard
├── requirements.txt
├── vercel.json
└── README.md
```

## Running it locally

```bash
git clone <your-repo-url>
cd sales-pipeline
python -m venv venv && source venv/bin/activate      # optional but recommended
pip install -r requirements.txt

# 1. Generate the raw (messy) dataset
python data/generate_raw_data.py

# 2. Run the ETL pipeline (Extract -> Transform -> Load)
python etl/etl_pipeline.py

# 3. Run the analysis + generate charts and dashboard data
python analysis/sales_analysis.py
```

This produces:
- `data/processed/sales_clean.csv` — the cleaned, analysis-ready dataset
- `data/processed/sales.db` — a SQLite warehouse (star schema) you can query directly
- `reports/figures/*.png` — six charts (revenue trend, top products, regional
  performance, category share, channel/payment heatmap, weekday vs weekend)
- `reports/summary_report.txt` — a plain-text KPI summary
- `dashboard/dashboard_data.json` — refreshed data for the dashboard

### Using a real PostgreSQL database instead of SQLite

Set a `DATABASE_URL` environment variable before running the ETL step:

```bash
export DATABASE_URL="postgresql+psycopg2://user:password@host:5432/salesdb"
python etl/etl_pipeline.py
```

The pipeline applies `sql/schema.sql` automatically and loads into Postgres.
If the connection fails, it transparently falls back to SQLite so the demo
never breaks.

### Querying the warehouse directly

```bash
sqlite3 data/processed/sales.db < sql/analysis_queries.sql
```

(or point any PostgreSQL client / BI tool at your `DATABASE_URL` and run the
same queries — they were written for Postgres syntax first.)

## Deploying the dashboard to Vercel

The dashboard is a single self-contained static HTML file — no build step,
no server, no environment variables required.

**Option A — Vercel dashboard (easiest):**
1. Push this repo to GitHub.
2. Go to [vercel.com/new](https://vercel.com/new) and import the repo.
3. Vercel will detect `vercel.json`, which points the output directory at
   `dashboard/`. Click **Deploy**.
4. Your dashboard is live at `https://<project-name>.vercel.app`.

**Option B — Vercel CLI:**
```bash
npm i -g vercel
vercel --prod
```

To refresh the dashboard with new data, re-run `analysis/sales_analysis.py`
after changing the underlying data, re-inject the JSON into `dashboard/index.html`
(or wire the dashboard to `fetch('./dashboard_data.json')` instead of the inlined
copy if you'd rather it load at runtime), commit, and Vercel will redeploy on push.

## Publishing to GitHub

```bash
cd sales-pipeline
git init
git add .
git commit -m "Sales pipeline: ETL, SQL analytics, and dashboard"
git branch -M main
git remote add origin https://github.com/<your-username>/sales-pipeline.git
git push -u origin main
```

## Sample results (from the included synthetic dataset)

- **Total net revenue:** ~$1.79M across 5,986 orders (Jan 2024 – Dec 2025)
- **Top product:** USB-C Hub (~$100K revenue)
- **Best region:** West (~$388K revenue)
- **Weekday orders outsell weekend orders** by roughly 2.5:1 in volume, with
  similar average order value across both

## Notes on the sample data

`data/generate_raw_data.py` generates a synthetic dataset that mimics a real
POS/e-commerce export — including the kind of messiness real sales data
actually has (duplicates, inconsistent region casing, mixed date formats,
nulls, sign errors). This makes the ETL step meaningfully demonstrate data
cleaning, not just a straight CSV-to-database load. Swap in your own raw
export by matching the same column structure (see `data/raw/sales_raw.csv`)
and the rest of the pipeline runs unchanged.
