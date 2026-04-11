"""
mock_data.py — Scenario B: Mock Dataset Generator
--------------------------------------------------
Generates realistic FMCG beverages promotional data using
Faker + Manual Python (as recommended in the research doc).

Three marts are created:
  1. promo_performance_mart
  2. inventory_movement_mart
  3. regional_summary_mart

Run directly:  python data/mock_data.py
"""

import random
import sqlite3
from datetime import datetime, timedelta
from faker import Faker
import pandas as pd
import os

fake = Faker("en_GB")
random.seed(42)

# ─────────────────────────────────────────────
# REFERENCE DATA
# ─────────────────────────────────────────────
REGIONS = ["North", "South", "East", "West", "Central"]
CATEGORIES = ["Carbonates", "Juices", "Energy", "Water", "RTD Tea", "Sports"]
CAMPAIGNS = {
    "FEB_2025": {"weeks": list(range(5, 9)), "name": "February 2025 Price Promotion"},
    "SUMMER_2025": {"weeks": list(range(26, 35)), "name": "Summer 2025 Campaign"},
    "WINTER_2024": {"weeks": list(range(48, 53)), "name": "Winter 2024 Campaign"},
    "Q1_2025": {"weeks": list(range(1, 14)), "name": "Q1 2025 Campaign"},
}

SKUS = [
    {"sku_code": "BEV-001", "sku_name": "Cola 500ml Single-Serve", "category": "Carbonates"},
    {"sku_code": "BEV-002", "sku_name": "Cola 2L Family Pack", "category": "Carbonates"},
    {"sku_code": "BEV-003", "sku_name": "Orange Juice 1L", "category": "Juices"},
    {"sku_code": "BEV-004", "sku_name": "Apple Juice 330ml", "category": "Juices"},
    {"sku_code": "BEV-005", "sku_name": "Energy Drink Original 250ml", "category": "Energy"},
    {"sku_code": "BEV-006", "sku_name": "Energy Drink Zero 500ml", "category": "Energy"},
    {"sku_code": "BEV-007", "sku_name": "Still Water 750ml", "category": "Water"},
    {"sku_code": "BEV-008", "sku_name": "Sparkling Water 500ml", "category": "Water"},
    {"sku_code": "BEV-009", "sku_name": "Green Tea RTD 330ml", "category": "RTD Tea"},
    {"sku_code": "BEV-010", "sku_name": "Sports Drink Citrus 500ml", "category": "Sports"},
]


def _uplift_for(region: str, campaign_id: str, sku_code: str) -> float:
    """Generates plausible uplift % — South performs better in summer, etc."""
    base = random.uniform(5.0, 25.0)
    if region == "South" and campaign_id == "SUMMER_2025":
        base += random.uniform(5, 12)
    if region == "North" and campaign_id == "WINTER_2024":
        base += random.uniform(3, 8)
    if sku_code in ("BEV-001", "BEV-005"):  # hero SKUs perform better
        base += random.uniform(2, 6)
    # Introduce one suspicious outlier for validation testing
    if region == "East" and campaign_id == "FEB_2025" and sku_code == "BEV-009":
        base = random.uniform(210, 260)  # >200% → Validation Agent should flag
    return round(base, 1)


# ─────────────────────────────────────────────
# MART 1: promo_performance_mart
# ─────────────────────────────────────────────
def generate_promo_performance_mart() -> pd.DataFrame:
    rows = []
    for campaign_id, meta in CAMPAIGNS.items():
        for week in meta["weeks"]:
            for region in REGIONS:
                for sku in SKUS:
                    baseline = random.randint(500, 8000)
                    uplift = _uplift_for(region, campaign_id, sku["sku_code"])
                    promo = round(baseline * (1 + uplift / 100))
                    rows.append({
                        "campaign_id": campaign_id,
                        "campaign_name": meta["name"],
                        "week_number": week,
                        "region": region,
                        "sku_code": sku["sku_code"],
                        "sku_name": sku["sku_name"],
                        "category": sku["category"],
                        "baseline_sales_units": baseline,
                        "promo_sales_units": promo,
                        "uplift_pct": uplift,
                        "data_completeness": round(random.uniform(0.75, 1.0), 2),
                        "created_at": datetime.now().isoformat(),
                    })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# MART 2: inventory_movement_mart
# ─────────────────────────────────────────────
def generate_inventory_movement_mart() -> pd.DataFrame:
    rows = []
    for campaign_id, meta in CAMPAIGNS.items():
        for week in meta["weeks"]:
            for category in CATEGORIES:
                prior = random.randint(1000, 20000)
                delta_pct = random.uniform(10, 45)
                if category == "Carbonates":
                    delta_pct += random.uniform(5, 15)
                promo = round(prior * (1 + delta_pct / 100))
                rows.append({
                    "campaign_id": campaign_id,
                    "week_number": week,
                    "category": category,
                    "prior_week_units_cleared": prior,
                    "promo_week_units_cleared": promo,
                    "inventory_delta_pct": round(delta_pct, 1),
                    "created_at": datetime.now().isoformat(),
                })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# MART 3: regional_summary_mart
# ─────────────────────────────────────────────
def generate_regional_summary_mart() -> pd.DataFrame:
    rows = []
    for campaign_id, meta in CAMPAIGNS.items():
        for region in REGIONS:
            baseline = random.randint(15000, 60000)
            uplift = round(random.uniform(6, 18), 1)
            if region == "South" and campaign_id == "SUMMER_2025":
                uplift += random.uniform(4, 8)
            promo = round(baseline * (1 + uplift / 100))
            rows.append({
                "campaign_id": campaign_id,
                "campaign_name": meta["name"],
                "region": region,
                "baseline_sales_units": baseline,
                "promo_sales_units": promo,
                "regional_uplift_pct": uplift,
                "data_completeness": round(random.uniform(0.82, 1.0), 2),
                "created_at": datetime.now().isoformat(),
            })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# DB SETUP
# ─────────────────────────────────────────────
def setup_database(db_path: str = "data/fmcg.db") -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    promo_df = generate_promo_performance_mart()
    inventory_df = generate_inventory_movement_mart()
    regional_df = generate_regional_summary_mart()

    conn = sqlite3.connect(db_path)
    promo_df.to_sql("promo_performance_mart", conn, if_exists="replace", index=False)
    inventory_df.to_sql("inventory_movement_mart", conn, if_exists="replace", index=False)
    regional_df.to_sql("regional_summary_mart", conn, if_exists="replace", index=False)
    conn.close()

    print(f"✅ Database created at {db_path}")
    print(f"   promo_performance_mart: {len(promo_df)} rows")
    print(f"   inventory_movement_mart: {len(inventory_df)} rows")
    print(f"   regional_summary_mart: {len(regional_df)} rows")


if __name__ == "__main__":
    setup_database()
