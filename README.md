# FMCG Beverages — AI Analytics Assistant

> **Internal use only · Data & AI Team · March 2026**

An AI-powered analytics assistant for CXOs and commercial managers in the Beverages category. Business users ask questions in plain language about promotional performance, inventory movement, regional comparisons, and campaign impact — and receive validated, plain-language answers in seconds.

---

## Architecture: Six-Agent Pipeline

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  1. ORCHESTRATOR         Claude Haiku 4.5 · Routes pipeline  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  2. INTENT AGENT         Claude Haiku 4.5 · Classifies type  │
│     promotional_performance / inventory_movement /            │
│     regional_comparison / campaign_impact_by_product          │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  3. VOCABULARY AGENT     Claude Haiku 4.5 · FMCG trade terms │
│     "uplift" → uplift_pct · "south region" → "South"        │
│     "summer campaign" → SUMMER_2025                           │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  4. QUERY AGENT          Claude Sonnet 4.6 · Builds SQL       │
│     Parameterised queries only · Structural validation        │
│     WHERE clause required · Allowed tables only               │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  5. VALIDATION AGENT     Pure Python · NO LLM                 │
│     Empty result → blocked · Null uplift → removed           │
│     Uplift >200% → flagged · Completeness <80% → caveat      │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  6. NARRATIVE AGENT      Claude Sonnet 4.6 · Plain-language   │
│     Receives validated figures only · Never does arithmetic   │
│     Max 5 sentences · Caveats included                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
            Answer delivered via:
            Slack Bot · Email Digest · Streamlit Web App
```

---

## What Questions It Answers

| Question Type | Example | Primary Metric |
|---|---|---|
| Promotional Performance | *"Did the February campaign improve sales in the South?"* | `uplift_pct` |
| Inventory Movement | *"Which categories saw stock clearance during the summer campaign?"* | `inventory_delta_pct` |
| Regional Comparison | *"How did North perform versus South in Q1?"* | `regional_uplift_pct` |
| Campaign Impact by Product | *"Which SKUs drove the most volume in FEB_2025?"* | `sku_uplift_pct` |

---

## Project Structure

```
fmcg-ai-assistant/
├── main.py                    ← CLI entry point (start here)
├── requirements.txt
├── .env.example               ← Copy to .env, add your API keys
│
├── config/
│   └── semantic_config.py     ← Single source of truth for ALL metrics
│                                 (vocabulary, campaigns, dimensions, thresholds)
│
├── data/
│   ├── mock_data.py           ← Scenario B: generates mock FMCG dataset
│   └── db.py                  ← DB connector (SQLite → DuckDB → Snowflake)
│
├── agents/
│   ├── orchestrator.py        ← Agent 1: runs the full pipeline
│   ├── intent_agent.py        ← Agent 2: Claude Haiku 4.5
│   ├── vocabulary_agent.py    ← Agent 3: Claude Haiku 4.5
│   ├── query_agent.py         ← Agent 4: Claude Sonnet 4.6
│   ├── validation_agent.py    ← Agent 5: Pure Python (no LLM)
│   └── narrative_agent.py     ← Agent 6: Claude Sonnet 4.6
│
├── delivery/
│   ├── slack_bot.py           ← Slack Bolt bot (Stage 2+)
│   ├── streamlit_app.py       ← Web UI for analysts
│   └── email_digest.py        ← Weekly CXO digest via SendGrid
│
└── tests/
    ├── test_vocabulary_agent.py   ← Step 1: entity resolution
    ├── test_intent_agent.py       ← Step 2: classification
    ├── test_query_agent.py        ← Step 3: SQL structure + params
    ├── test_validation_agent.py   ← Step 4: all pass/fail scenarios
    └── test_pipeline_e2e.py       ← Step 6: 30+ question bank
```

### Slack Bot (Stage 2+)

1. Create a Slack App at https://api.slack.com/apps
2. Enable **Socket Mode**
3. Add Bot Token Scopes: `app_mentions:read`, `chat:write`, `im:history`, `im:read`, `im:write`
4. Add to `.env`: `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_APP_TOKEN`

```bash
python delivery/slack_bot.py
```

### Streamlit Web App (Analysts)

```bash
streamlit run delivery/streamlit_app.py
```

### CXO Weekly Email Digest

```bash
# Send immediately (test)
python delivery/email_digest.py

# Run on schedule (every Monday 7:30 AM)
python delivery/email_digest.py --schedule
```

---

## Running Tests

```bash
# All deterministic tests (run on every commit — zero API cost)
pytest tests/ -v

# Specific test step
pytest tests/test_validation_agent.py -v
pytest tests/test_query_agent.py -v

# E2E tests (full question bank, mocked API)
pytest tests/test_pipeline_e2e.py -v

# With coverage report
pytest tests/ --cov=agents --cov-report=term-missing
```

---

## Database Migration Path

| Stage | Database | Why | Monthly Cost |
|---|---|---|---|
| **1 — Development** | SQLite | Built into Python. Zero setup. Focus on agent logic. | Free |
| **2 — Mid-stage** | DuckDB | 10–50× faster than SQLite for analytical queries. | Free |
| **3 — Production** | Snowflake | RBAC, multi-user, Cortex Analyst native, governance. | £50–120/mo |

To switch stages, update `.env`:
```env
DB_STAGE=sqlite    # Stage 1
DB_STAGE=duckdb    # Stage 2
DB_STAGE=snowflake # Stage 3 (add Snowflake credentials)
```

---

## API Cost Estimate (1,000 queries/day)

| Agent | Model | £/month |
|---|---|---|
| Orchestrator | Claude Haiku 4.5 | ~£0.20 |
| Intent Agent | Claude Haiku 4.5 | ~£1.40 |
| Vocabulary Agent | Claude Haiku 4.5 | ~£2.00 |
| Query Agent | Claude Sonnet 4.6 | ~£13.00 |
| Validation Agent | Pure Python | £0 |
| Narrative Agent | Claude Sonnet 4.6 | ~£12.50 |
| **TOTAL** | | **~£29/month** |

---

## The Non-Negotiable Rules

1. **Every metric is defined in `config/semantic_config.py`** — never in a BI tool, dashboard, or ad-hoc script.
2. **Python computes all numbers** — the language model explains them. It never generates them.
3. **The Validation Agent runs before the Narrative Agent** — always. A wrong number never reaches a CXO.
4. **WHERE clause required on all SQL** — no full table scans, ever.
5. **Only `ALLOWED_TABLES` can be queried** — the assistant never touches raw transactional data.

---

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Run tests before committing: `pytest tests/ -v`
3. Add to the question bank in `tests/test_pipeline_e2e.py` for any new intent or edge case
4. Update `config/semantic_config.py` for any new metric, campaign, or vocabulary term
5. Open a pull request

---

*Data & AI Team · Internal Use Only · Built on Claude Haiku 4.5 + Sonnet 4.6*
