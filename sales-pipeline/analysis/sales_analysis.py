"""
sales_analysis.py
-------------------
Loads the cleaned dataset (or queries the warehouse directly), runs
Pandas aggregations that mirror the SQL analysis layer, and produces:

  1. A set of Matplotlib/Seaborn PNG charts in reports/figures/
  2. A summary text report in reports/summary_report.txt
  3. A dashboard_data.json consumed by the web dashboard (dashboard/)

Run:
    python analysis/sales_analysis.py
"""

import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_CSV = ROOT / "data" / "processed" / "sales_clean.csv"
SQLITE_DB = ROOT / "data" / "processed" / "sales.db"
FIG_DIR = ROOT / "reports" / "figures"
SUMMARY_PATH = ROOT / "reports" / "summary_report.txt"
DASHBOARD_JSON = ROOT / "dashboard" / "dashboard_data.json"

sns.set_theme(style="whitegrid", palette="deep")
plt.rcParams["figure.dpi"] = 120
plt.rcParams["axes.titleweight"] = "bold"
plt.rcParams["axes.titlesize"] = 13


def load_data() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_CSV, parse_dates=["order_date"])
    return df


def money(ax, axis="y"):
    fmt = mticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def chart_monthly_revenue(df, out_dir):
    monthly = (
        df.set_index("order_date")
        .resample("MS")["net_revenue"]
        .sum()
        .reset_index()
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=monthly, x="order_date", y="net_revenue", marker="o", ax=ax, linewidth=2.5)
    ax.set_title("Monthly Revenue Trend")
    ax.set_xlabel("")
    ax.set_ylabel("Net Revenue")
    money(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_dir / "01_monthly_revenue_trend.png")
    plt.close(fig)
    return monthly


def chart_top_products(df, out_dir, n=10):
    top = (
        df.groupby(["product_name"])["net_revenue"]
        .sum()
        .sort_values(ascending=False)
        .head(n)
        .reset_index()
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=top, y="product_name", x="net_revenue", ax=ax, hue="product_name", legend=False, palette="viridis")
    ax.set_title(f"Top {n} Products by Revenue")
    ax.set_xlabel("Net Revenue")
    ax.set_ylabel("")
    money(ax, "x")
    fig.tight_layout()
    fig.savefig(out_dir / "02_top_products.png")
    plt.close(fig)
    return top


def chart_regional_performance(df, out_dir):
    region = (
        df.groupby("region")["net_revenue"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=region, x="region", y="net_revenue", ax=ax, hue="region", legend=False, palette="mako")
    ax.set_title("Revenue by Region")
    ax.set_xlabel("")
    ax.set_ylabel("Net Revenue")
    money(ax)
    fig.tight_layout()
    fig.savefig(out_dir / "03_regional_performance.png")
    plt.close(fig)
    return region


def chart_category_breakdown(df, out_dir):
    cat = df.groupby("category")["net_revenue"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(7, 7))
    colors = sns.color_palette("Set2", len(cat))
    ax.pie(
        cat.values, labels=cat.index, autopct="%1.1f%%", startangle=90,
        colors=colors, wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    ax.set_title("Revenue Share by Category")
    fig.tight_layout()
    fig.savefig(out_dir / "04_category_share.png")
    plt.close(fig)
    return cat.reset_index()


def chart_channel_payment_heatmap(df, out_dir):
    pivot = df.pivot_table(
        index="sales_channel", columns="payment_method", values="net_revenue", aggfunc="sum", fill_value=0
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.heatmap(pivot, annot=True, fmt=",.0f", cmap="YlGnBu", ax=ax, cbar_kws={"label": "Net Revenue"})
    ax.set_title("Revenue: Sales Channel vs Payment Method")
    fig.tight_layout()
    fig.savefig(out_dir / "05_channel_payment_heatmap.png")
    plt.close(fig)


def chart_weekday_vs_weekend(df, out_dir):
    df = df.copy()
    df["is_weekend"] = df["order_date"].dt.dayofweek.isin([5, 6])
    grp = df.groupby("is_weekend")["net_revenue"].agg(["sum", "mean", "count"]).reset_index()
    grp["label"] = grp["is_weekend"].map({True: "Weekend", False: "Weekday"})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    sns.barplot(data=grp, x="label", y="sum", ax=axes[0], hue="label", legend=False, palette="crest")
    axes[0].set_title("Total Revenue")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("")
    money(axes[0])
    sns.barplot(data=grp, x="label", y="mean", ax=axes[1], hue="label", legend=False, palette="flare")
    axes[1].set_title("Avg Order Value")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("")
    money(axes[1])
    fig.suptitle("Weekday vs Weekend Performance", fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_dir / "06_weekday_vs_weekend.png")
    plt.close(fig)
    return grp


def build_kpis(df):
    total_revenue = float(df["net_revenue"].sum())
    total_orders = int(len(df))
    aov = total_revenue / total_orders if total_orders else 0
    total_units = int(df["quantity"].sum())
    unique_customers = int(df["customer_id"].nunique())
    date_min, date_max = df["order_date"].min(), df["order_date"].max()
    return {
        "total_revenue": round(total_revenue, 2),
        "total_orders": total_orders,
        "avg_order_value": round(aov, 2),
        "total_units_sold": total_units,
        "unique_customers": unique_customers,
        "date_range": f"{date_min.date()} to {date_max.date()}",
    }


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()

    kpis = build_kpis(df)
    monthly = chart_monthly_revenue(df, FIG_DIR)
    top_products = chart_top_products(df, FIG_DIR)
    region = chart_regional_performance(df, FIG_DIR)
    category = chart_category_breakdown(df, FIG_DIR)
    chart_channel_payment_heatmap(df, FIG_DIR)
    weekday = chart_weekday_vs_weekend(df, FIG_DIR)

    top_customers = (
        df.groupby(["customer_id", "customer_name"])["net_revenue"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )

    # ---- text summary report ----
    lines = [
        "SALES ANALYSIS SUMMARY REPORT",
        "=" * 40,
        f"Period: {kpis['date_range']}",
        f"Total Net Revenue: ${kpis['total_revenue']:,.2f}",
        f"Total Orders: {kpis['total_orders']:,}",
        f"Average Order Value: ${kpis['avg_order_value']:,.2f}",
        f"Units Sold: {kpis['total_units_sold']:,}",
        f"Unique Customers: {kpis['unique_customers']:,}",
        "",
        "Top 5 Products by Revenue:",
    ]
    for _, r in top_products.head(5).iterrows():
        lines.append(f"  - {r['product_name']}: ${r['net_revenue']:,.2f}")
    lines.append("")
    lines.append("Regional Performance:")
    for _, r in region.iterrows():
        lines.append(f"  - {r['region']}: ${r['net_revenue']:,.2f}")
    SUMMARY_PATH.write_text("\n".join(lines))

    # ---- dashboard JSON export ----
    dashboard_data = {
        "kpis": kpis,
        "monthly_revenue": [
            {"month": d.strftime("%b %Y"), "revenue": round(v, 2)}
            for d, v in zip(monthly["order_date"], monthly["net_revenue"])
        ],
        "top_products": top_products.rename(columns={"net_revenue": "revenue"}).round(2).to_dict("records"),
        "regional_performance": region.rename(columns={"net_revenue": "revenue"}).round(2).to_dict("records"),
        "category_share": category.rename(columns={"net_revenue": "revenue"}).round(2).to_dict("records"),
        "top_customers": top_customers.rename(columns={"net_revenue": "revenue"}).round(2).to_dict("records"),
        "weekday_vs_weekend": weekday[["label", "sum", "mean", "count"]]
            .rename(columns={"sum": "total_revenue", "mean": "avg_order_value", "count": "orders"})
            .round(2).to_dict("records"),
    }
    DASHBOARD_JSON.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_JSON.write_text(json.dumps(dashboard_data, indent=2))

    print("Analysis complete.")
    print(f"  Charts       -> {FIG_DIR}")
    print(f"  Summary      -> {SUMMARY_PATH}")
    print(f"  Dashboard JSON -> {DASHBOARD_JSON}")


if __name__ == "__main__":
    main()
