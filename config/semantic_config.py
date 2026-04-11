"""
semantic_config.py — Stage 1 Semantic Layer
--------------------------------------------
Single source of truth for every metric, dimension, and FMCG trade
term used across all agents and queries.

Migration path:
  Stage 1 (now)        → This Python file
  Stage 2 (production) → Snowflake Semantic Views
  Stage 3 (governed)   → dbt MetricFlow (YAML)

The Non-Negotiable Rule: Never define a metric inside a BI tool.
Every metric lives here and every agent queries from here.
"""

# ─────────────────────────────────────────────
# DATA MARTS (tables the Query Agent may read)
# ─────────────────────────────────────────────
ALLOWED_TABLES = [
    "promo_performance_mart",
    "inventory_movement_mart",
    "regional_summary_mart",
]

# ─────────────────────────────────────────────
# METRIC DEFINITIONS
# All SQL expressions reference ALLOWED_TABLES only.
# The Query Agent substitutes {filters} at runtime.
# ─────────────────────────────────────────────
METRICS = {
    "uplift_pct": {
        "description": "Percentage sales uplift during the promotional window vs baseline",
        "sql": """
            ROUND(
                100.0 * (SUM(promo_sales_units) - SUM(baseline_sales_units))
                / NULLIF(SUM(baseline_sales_units), 0),
            1) AS uplift_pct
        """,
        "table": "promo_performance_mart",
        "requires": ["promo_sales_units", "baseline_sales_units"],
    },
    "promo_units": {
        "description": "Total units sold during the promotional window",
        "sql": "SUM(promo_sales_units) AS promo_units",
        "table": "promo_performance_mart",
        "requires": ["promo_sales_units"],
    },
    "baseline_units": {
        "description": "Expected (baseline) units without promotion",
        "sql": "SUM(baseline_sales_units) AS baseline_units",
        "table": "promo_performance_mart",
        "requires": ["baseline_sales_units"],
    },
    "inventory_delta_pct": {
        "description": "Percentage change in inventory clearance rate during promo week vs prior week",
        "sql": """
            ROUND(
                100.0 * (SUM(promo_week_units_cleared) - SUM(prior_week_units_cleared))
                / NULLIF(SUM(prior_week_units_cleared), 0),
            1) AS inventory_delta_pct
        """,
        "table": "inventory_movement_mart",
        "requires": ["promo_week_units_cleared", "prior_week_units_cleared"],
    },
    "regional_uplift_pct": {
        "description": "Uplift percentage broken down per region for comparison",
        "sql": """
            region,
            ROUND(
                100.0 * (SUM(promo_sales_units) - SUM(baseline_sales_units))
                / NULLIF(SUM(baseline_sales_units), 0),
            1) AS regional_uplift_pct,
            SUM(promo_sales_units) AS promo_units
        """,
        "table": "regional_summary_mart",
        "requires": ["promo_sales_units", "baseline_sales_units", "region"],
    },
    "sku_uplift_pct": {
        "description": "Uplift percentage by individual SKU for campaign impact analysis",
        "sql": """
            sku_code,
            sku_name,
            ROUND(
                100.0 * (SUM(promo_sales_units) - SUM(baseline_sales_units))
                / NULLIF(SUM(baseline_sales_units), 0),
            1) AS sku_uplift_pct,
            SUM(promo_sales_units) AS promo_units
        """,
        "table": "promo_performance_mart",
        "requires": ["sku_code", "sku_name", "promo_sales_units", "baseline_sales_units"],
    },
}

# ─────────────────────────────────────────────
# DIMENSIONS (filterable columns)
# ─────────────────────────────────────────────
DIMENSIONS = {
    "region": {
        "column": "region",
        "type": "string",
        "valid_values": ["North", "South", "East", "West", "Central"],
        "tables": ["promo_performance_mart", "regional_summary_mart"],
    },
    "campaign_id": {
        "column": "campaign_id",
        "type": "string",
        "tables": ["promo_performance_mart", "inventory_movement_mart", "regional_summary_mart"],
    },
    "week_number": {
        "column": "week_number",
        "type": "integer",
        "tables": ["promo_performance_mart", "inventory_movement_mart"],
    },
    "category": {
        "column": "category",
        "type": "string",
        "valid_values": ["Carbonates", "Juices", "Energy", "Water", "RTD Tea", "Sports"],
        "tables": ["promo_performance_mart", "inventory_movement_mart"],
    },
    "sku_code": {
        "column": "sku_code",
        "type": "string",
        "tables": ["promo_performance_mart"],
    },
}

# ─────────────────────────────────────────────
# FMCG VOCABULARY MAP
# Maps trade terms → canonical database field names.
# This is the domain vocabulary layer referenced in the design doc.
# ─────────────────────────────────────────────
VOCABULARY = {
    # Uplift synonyms
    "uplift": "uplift_pct",
    "sales uplift": "uplift_pct",
    "incremental uplift": "uplift_pct",
    "lift": "uplift_pct",
    "sales lift": "uplift_pct",
    "performance": "uplift_pct",
    "sales growth": "uplift_pct",

    # Baseline synonyms
    "baseline": "baseline_units",
    "pre-promo baseline": "baseline_units",
    "benchmark": "baseline_units",
    "normal sales": "baseline_units",
    "non-promotional sales": "baseline_units",
    "base sales": "baseline_units",

    # Volume synonyms
    "units sold": "promo_units",
    "volume": "promo_units",
    "sales volume": "promo_units",
    "sell-through": "promo_units",
    "offtake": "promo_units",

    # Inventory synonyms
    "stock clearance": "inventory_delta_pct",
    "inventory reduction": "inventory_delta_pct",
    "stock movement": "inventory_delta_pct",
    "sell-through rate": "inventory_delta_pct",

    # Region synonyms
    "south region": "South",
    "southern": "South",
    "north region": "North",
    "northern": "North",
    "east region": "East",
    "eastern": "East",
    "west region": "West",
    "western": "West",

    # Time synonyms
    "last month": "LAST_MONTH",    # resolved by Query Agent to actual week_numbers
    "last week": "LAST_WEEK",
    "this month": "THIS_MONTH",
    "summer campaign": "SUMMER_2025",
    "february campaign": "FEB_2025",
    "winter campaign": "WINTER_2024",
    "q1 campaign": "Q1_2025",
}

# ─────────────────────────────────────────────
# CAMPAIGN REGISTRY
# Maps campaign short-names → campaign_ids in the DB
# ─────────────────────────────────────────────
CAMPAIGN_REGISTRY = {
    "FEB_2025": {"campaign_id": "FEB_2025", "name": "February 2025 Price Promotion", "weeks": list(range(5, 9))},
    "SUMMER_2025": {"campaign_id": "SUMMER_2025", "name": "Summer 2025 Campaign", "weeks": list(range(26, 35))},
    "WINTER_2024": {"campaign_id": "WINTER_2024", "name": "Winter 2024 Campaign", "weeks": list(range(48, 53))},
    "Q1_2025": {"campaign_id": "Q1_2025", "name": "Q1 2025 Campaign", "weeks": list(range(1, 14))},
    "LAST_MONTH": {"campaign_id": None, "resolve": "last_month"},  # resolved dynamically
    "LAST_WEEK": {"campaign_id": None, "resolve": "last_week"},
    "THIS_MONTH": {"campaign_id": None, "resolve": "this_month"},
}

# ─────────────────────────────────────────────
# INTENT TYPES (maps to analytical paths)
# ─────────────────────────────────────────────
INTENT_TYPES = {
    "promotional_performance": {
        "description": "Whether a specific promotion drove measurable sales growth",
        "required_dimensions": ["campaign_id"],
        "primary_metric": "uplift_pct",
        "mart": "promo_performance_mart",
        "example_queries": [
            "Did last month's campaign improve sales in the South?",
            "How did the February promotion perform?",
            "What was the uplift from the summer campaign?",
        ],
    },
    "inventory_movement": {
        "description": "Whether stock moved faster during the promotional window",
        "required_dimensions": ["campaign_id"],
        "primary_metric": "inventory_delta_pct",
        "mart": "inventory_movement_mart",
        "example_queries": [
            "Which categories saw inventory reduction during the promotion?",
            "How did stock levels change during the campaign?",
            "What was the sell-through rate improvement?",
        ],
    },
    "regional_comparison": {
        "description": "Which region responded better to the same promotional mechanic",
        "required_dimensions": ["campaign_id"],
        "primary_metric": "regional_uplift_pct",
        "mart": "regional_summary_mart",
        "example_queries": [
            "How did the North perform versus the South during the summer campaign?",
            "Compare regional performance for the February promotion",
            "Which region had the best uplift?",
        ],
    },
    "campaign_impact_by_product": {
        "description": "Which individual products drove the most incremental volume",
        "required_dimensions": ["campaign_id"],
        "primary_metric": "sku_uplift_pct",
        "mart": "promo_performance_mart",
        "example_queries": [
            "Which SKUs benefited most from the February price promotion?",
            "What products drove the most volume during the campaign?",
            "Which SKU had the highest incremental lift?",
        ],
    },
}

# ─────────────────────────────────────────────
# VALIDATION THRESHOLDS
# Used by the Validation Agent (pure Python — no LLM)
# ─────────────────────────────────────────────
VALIDATION_RULES = {
    "max_uplift_pct": 200.0,      # >200% uplift is flagged as suspicious
    "min_baseline_units": 100,    # Baselines below this are flagged as unreliable
    "min_data_completeness": 0.8, # <80% data coverage triggers a caveat
    "max_uplift_flag": 200.0,     # uplift above this triggers a warning in narrative
}
