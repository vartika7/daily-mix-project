# Designing "Daily Mix" to Fix New-User Retention in a Music Streaming App

A portfolio project demonstrating end-to-end product analytics: problem diagnosis, behavioural insights, feature design, A/B test analysis, and business impact modelling — all built on a realistic simulated dataset.

## The Problem

A mobile-first music streaming app (freemium model) saw D30 retention for new users decline from 28% → 25% over one quarter. Early-life engagement (first-week listening minutes) also dropped, especially on mobile. Qualitative signals pointed to a common issue: new users couldn't find an easy "press play" option and their early sessions were short and search-dominated.

## The Solution

A personalised **Daily Mix** playlist pinned on the Home screen for the first 30 days. The hypothesis: a low-friction, lean-back listening experience drives deeper early sessions and better retention.

## What's in This Repo

```
├── data_generator.py              # Generates ~12K users, ~500K+ events
├── daily_mix_data/                # Generated CSVs (not committed — run generator)
├── sql/
│   └── schema_and_queries.sql     # DDL + 12 analytical queries (PostgreSQL)
├── notebooks/
│   ├── 01_baseline_analysis.ipynb # Funnels, retention curves, behavioural insights
│   └── 02_experiment_analysis.ipynb # A/B test results, guardrails, trade-off decision
├── dashboard/                     # Interactive dashboard (Streamlit / Tableau)
├── docs/
│   ├── case_study.md              # 6–10 page written case study
│   └── decision_log.md            # Why every decision was made + AI usage log
└── requirements.txt
```

## Key Findings (from simulated data)

| Metric                   | Control  | Treatment | Δ                    |
| ------------------------ | -------- | --------- | -------------------- |
| D30 retention            | ~25%     | ~28.2%    | **+3.2 pp**          |
| Weekly listening minutes | baseline | +4.2%     | **significant**      |
| Search/Discover usage    | baseline | −3%       | acceptable           |
| Artist diversity index   | baseline | **−12%**  | ⚠️ exceeds threshold |

**The hard decision:** Despite strong retention uplift, the 12% drop in artist diversity crossed the acceptable guardrail. Recommendation was to _not_ ship the initial design — instead iterate on diversity constraints and re-test.

## Behavioural Insights That Motivated the Feature

1. **Speed to first play matters** — Users who played a track within 2 minutes of first app open had ~40% higher D7 retention.
2. **Deep early sessions matter** — Users with at least one 15+ minute session in the first 72 hours had ~3× higher D30 retention.
3. **Discovery drives retention** — Users who discovered 3+ new artists in week 1 retained at ~1.8× the rate of others, even controlling for total listening time.

## How to Run

### 1. Set up environment

```bash
git clone https://github.com/vartika7/daily-mix-project.git
cd daily-mix-project
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Generate the dataset

```bash
python data_generator.py
```

This creates 5 CSVs in `./daily_mix_data/` (~12K users, ~500K+ events). Takes ~30–60 seconds.

### 3. Load into DuckDB and query

```python
import duckdb
con = duckdb.connect()

for table in ['users', 'tracks', 'artists', 'sessions', 'events']:
    con.execute(f"""
        CREATE TABLE {table} AS
        SELECT * FROM read_csv_auto('./daily_mix_data/{table}.csv')
    """)

# Run any query from sql/schema_and_queries.sql
result = con.execute("SELECT * FROM users LIMIT 10").fetchdf()
```

### 4. Run the notebooks

Open `notebooks/01_baseline_analysis.ipynb` in VS Code (with Jupyter extension) or JupyterLab and run all cells.

## Methodology Notes

- **Data is synthetic.** Generated with known parameters to demonstrate the analytical workflow. Behavioural correlations are embedded via latent user traits, not hardcoded on outcomes — so analysis recovers them with realistic noise.
- **Statistical approach:** Retention reported as proportions with confidence intervals. Engagement uses median and Winsorized means to handle power-user skew. Discovery insight uses tercile stratification to control for total listening time.
- **AI usage:** Claude was used to accelerate SQL/Python drafting. All analytical decisions (metric selection, experiment design, trade-off judgment) are original. See `docs/decision_log.md` for a full transparency log.

## Tech Stack

- **Languages:** Python, SQL (PostgreSQL-compatible)
- **Database:** DuckDB (development), PostgreSQL (production-style)
- **Analysis:** pandas, numpy, scipy, matplotlib, seaborn
- **Dashboard:** Streamlit or Tableau Public
- **Versioning:** Git

## Author

Vartika — https://linkedin.com/in/vartika7 | vartika.career@gmail.com

Built as a portfolio project for product/data analytics roles. Feedback welcome.