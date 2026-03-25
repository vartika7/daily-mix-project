# Daily Mix Project - Decision Log

Notes on why I made the choices I did, what went wrong along the way, and where I used AI.

---

## Why This Problem?

I picked music streaming retention because retention is the biggest problem with product companies and the domain makes the data intuitive (plays, skips, likes). Everyone's used Spotify. The feature design (playlist construction) is explainable without getting into ML territory, which keeps the focus on analytical thinking rather than model architecture.

I went with Daily Mix over alternatives like onboarding redesign or notification nudges because it targets all three behavioral levers at once (fast play, deep sessions, discovery), it's a single surface change that's clean to A/B test, and it's reversible with a feature flag. In a real company I'd run multiple experiments, but for a portfolio piece, going deep on one is more impressive than going shallow on three.

This is simulated data. The value is the analytical framework and decision-making, not the specific numbers.

---

## Phase 1: SQL Schema & Queries

**The schema** has five tables: `users`, `events`, `sessions`, `tracks`, `artists`. This mirrors how streaming companies actually structure their warehouse. Sessions are pre-aggregated because sessionisation typically happens upstream in a pipeline. I didn't want to force myself to re-derive sessions from raw events in every query.

**One design choice worth noting:** `experiment_variant` lives on both the `users` table (assignment) and the `events` table (exposure). This lets me do either intent-to-treat or per-protocol analysis. In a real setup you'd probably have a separate `experiment_assignments` table, but for this project that's unnecessary complexity.

**The discovery insight query** (2F) is the one I'm proudest of. It uses `NTILE(3)` to bin users by listening time, then checks the discovery-retention relationship within each bin. It's basically a lightweight stratified analysis. It doesn't prove causality, but it's much stronger than a naive correlation. If you ask "how do you know discovery isn't just a proxy for being a heavy user?" this is the answer.

**Limitations I'd mention if asked:** The schema is simplified (no partitions, no subscription tracking, no playlist_tracks junction table). The queries assume clean data. In production I'd add upstream quality checks for duplicates, bot traffic, timezone mismatches.

**AI usage:** I drafted the SQL using AI-assisted code generation, then reviewed and adjusted every query (the retention definitions, the Winsorisation approach, the tercile logic). The decisions about *which* queries to write and *why* those insights matter were mine.

| Decision | Why | Limitation | AI Role |
|----------|-----|------------|---------|
| 5-table schema, PG syntax | Mirrors real warehouses; portable SQL | Simplified vs production | I spec'd; AI drafted DDL; I reviewed |
| `experiment_variant` on users + events | Enables ITT and per-protocol analysis | Ideally separate assignment table | I validated AI's suggestion |
| Tercile binning for discovery insight | Controls for engagement without causal model | Stratification is not randomisation | I chose approach; used AI for NTILE implementation |

---

## Phase 2: Data Generator

### Why not use a Kaggle dataset?

I tried to think about this from the interviewer's perspective. If I use someone else's dataset, the schema won't match my queries, the behavioral signals I need won't be there, and there's no way to embed a proper A/B test. I'd spend more time wrangling than analysing, and the seams would show.

Generating synthetic data is more work upfront, but it gives me full control over the signals, schema alignment, and reproducibility. It's also more honest. I'm not pretending a Kaggle CSV is production data.

### The calibration nightmare

This took three rounds of iteration, and honestly, each round taught me something about how simulation works:

**Round 1:** D30 control came out at 37% instead of ~25%. The problem was multiplicative behavioral boosts. A user who was a fast activator AND had a deep session AND had high engagement got all three multipliers stacked on top of each other. I switched to additive boosts and the numbers came down.

**Round 2:** Retention was right (~24.5% control, ~27.9% treatment), but the diversity guardrail wasn't breaching. Treatment users listened more overall, so even with the diversity penalty, they heard more total artists just from volume. This is actually a realistic analytical trap: raw counts can be misleading when engagement differs between groups. I solved it by measuring **artists per 100 plays** instead of raw unique artists, and by concentrating the treatment track selection harder on a narrow pool of popular artists.

**Round 3:** The behavioral insights were too flat. All users activated fast (no slow bucket to compare against), deep session ratio was only 1.4x instead of ~2x, and the discovery effect was barely visible. I had to rework the activation logic to create explicit speed buckets, increase the deep session boost, and add a direct discovery-to-retention link.

**Final numbers the generator produces:**
- D30: control ~23.3%, treatment ~28.6% (+5.3pp)
- Insight 1: fast activators 65.6% D7 vs slow 47.9% (1.4x, 37% lift)
- Insight 2: deep session 38.5% D30 vs no deep 19.2% (2.0x)
- Insight 3: 3+ artists ~1.5x D30 within Low and Medium listening terciles
- Diversity: -19.8% (FAIL, threshold was 10%)
- Search: -3.5% (PASS, threshold was 5%)

**AI usage:** I built the generator script with AI-assisted drafting, defining all the parameters, effect sizes, and behavioral structure. The calibration iterations were a back-and-forth: I'd diagnose what was wrong, test parameter changes, and check whether the numbers landed. The judgment about what "right" looks like was always mine.

| Decision | Why | Limitation | AI Role |
|----------|-----|------------|---------|
| Synthetic generator (not Kaggle) | Full control, schema-aligned | Not real data | I defined parameters; AI-assisted drafting |
| Hash-based variant assignment | Deterministic, reproducible | MD5 isn't needed but is standard practice | I specified; AI-assisted implementation |
| Beta(2,5) engagement distribution | Realistic right-skew | Shape params are educated guesses | I chose distribution; AI-assisted coding |
| Additive (not multiplicative) boosts | Prevents compounding inflation | Less flexible than multiplicative | I diagnosed calibration failure; iterated on fix |
| 3 calibration cycles | Each cycle revealed a new issue | Trial-and-error inherent to synthetic data | I ran and diagnosed each cycle |
| Ultra-safe track pool (top_1%) | Creates measurable diversity penalty | Makes treatment selection very aggressive | I identified the mechanism and specified fix |

---

## Phase 3: Baseline Analysis Notebook

This notebook answers "what's wrong and why?" before anyone proposes a solution. The structure follows how I'd actually present findings at work: context, problem, behavioral patterns, then heading towards a solution.

**A few decisions worth noting:**

- The engagement histograms are capped at p95. If you don't cap them, a handful of power users stretch the x-axis and make the bulk of the distribution unreadable. I hid the y-axis too. The shape of the distribution matters, not the exact counts.

- Insight 3 (discovery) uses an inner join on discovery + listening, which drops users with zero first-week plays. This is intentional. I'm analysing discovery behavior among users who engaged at least minimally. Worth mentioning if someone asks about the sample size.

- I replaced the original pie chart for source mix with a horizontal bar chart. Pie charts are genuinely hard to read when you have 4-5 categories of similar size.

- The summary markdown cell at the bottom explicitly calls out that these are correlations, not causal claims. The stratified analysis controls for engagement level, but true causal evidence requires the experiment, which is the next notebook.

**AI usage:** I built each cell using AI-assisted drafting for query + chart code. I chose the narrative structure, decided which insights to highlight, and iterated on the chart formatting until it was readable (this took longer than the queries themselves, honestly).

### Final insight numbers (from data)

| Insight | Effect | Metric |
|---------|--------|--------|
| Speed to first play | 37% higher D7 retention (65.6% vs 47.9%) | 1.4x ratio |
| Deep session (15+ min, 72h) | 2.0x D30 retention (38.5% vs 19.2%) | 34.9% achieved organically |
| Discovery (3+ artists, controlled) | ~1.5x D30 within Low and Medium terciles | Holds after stratification |

| Decision | Why | Limitation | AI Role |
|----------|-----|------------|---------|
| 11-cell narrative structure | Mirrors how analysts present | Charts use capped distributions | I defined narrative; AI-assisted query + chart code |
| Tercile stratification for Insight 3 | Controls for engagement level | Not causal | I chose approach; AI-assisted implementation |
| Source mix as bar chart | Pie charts are hard to read | Source attribution is imperfect | I chose chart type; AI-assisted query |
| Artists-per-100-plays (not raw count) | Normalizes for engagement volume differences | Slightly less intuitive than raw count | I identified normalization need after raw counts were misleading |

---

## Phase 4: Experiment Analysis Notebook

This is the A/B test notebook, the analytical core of the project.

### Statistical choices

- **Retention:** Two-proportion z-test from `statsmodels` (not `scipy`; I learned this the hard way when it threw an AttributeError). Reported with 95% CI.
- **Listening minutes:** Mann-Whitney U instead of t-test, because listening data is heavily right-skewed. If an interviewer asks why not a t-test, I'd say "the distribution violates normality assumptions, and the sample is large enough that the non-parametric test has good power."
- **No multiple-testing correction:** Noted as a limitation. In production I'd use Bonferroni or sequential testing. For a portfolio project with pre-registered primary and guardrail metrics, this is standard.

### The diversity metric pivot

This was the most important analytical decision in the project. The original metric was raw unique artists per user. Treatment users had *more* unique artists (+10.8%) because they listened more overall. The guardrail passed, and the narrative ("do not ship") fell apart.

Switching to **artists per 100 plays** changed everything. This normalizes for engagement volume and reveals what's actually happening: treatment users hear the same popular artists on repeat. The metric dropped to -19.8%, clearly failing the 10% threshold.

This is exactly the kind of thing I'd want to talk about in an interview. The naive metric gave the wrong answer. The normalized metric told the real story. That's the difference between running an analysis and understanding one.

### The hard decision

Despite +5.3pp D30 retention (well above the 3pp target), I recommended not shipping. The 19.8% diversity drop is nearly double the threshold. In a two-sided marketplace, concentrating listening on fewer artists harms long-tail artist economics, creates filter bubble risk, and sets a precedent that guardrails are negotiable.

If someone pushes back ("but the retention lift is huge, why not ship?"), my answer is: the retention signal is strong enough to survive algorithm constraints. Add diversity floors (min 12 artists per mix, 20% long-tail tracks), re-test, and you'll likely keep 80% of the uplift while passing guardrails. One extra sprint to get it right is worth it.

**AI usage:** I built the statistical tests, guardrail checks, and charts with AI-assisted coding. I chose the test types, defined the thresholds, identified the diversity metric problem, and made the ship/no-ship call. The judgment under ambiguity is the whole point of this section. AI can run a z-test, but it can't decide whether to ship.

### Final experiment numbers (from data)

| Metric | Control | Treatment | Delta | Status |
|--------|---------|-----------|-------|--------|
| D30 retention | 23.3% | 28.6% | +5.3 pp | Significant |
| D7 retention | 55.1% | 64.5% | +9.3 pp | Significant |
| Weekly listening (median) | 45.6 min | 52.4 min | +14.7% | Significant |
| Search usage | 12.04/user | 11.62/user | -3.5% | PASS |
| Diversity (per 100 plays) | 66.81 | 53.55 | -19.8% | FAIL |
| Cannibalization | -- | -- | +11.2% net | Monitor |

| Decision | Why | Limitation | AI Role |
|----------|-----|------------|---------|
| Two-proportion z-test for retention | Standard frequentist test; universally understood | Assumes independence | I chose test type; AI-assisted coding |
| Mann-Whitney U for listening | Non-parametric; better for skewed data | Less familiar to some | I chose due to skew; AI-assisted implementation |
| Artists-per-100-plays metric | Raw counts were misleading (more listening = more artists) | Slightly harder to explain | I identified issue and designed normalization |
| Pre-registered guardrail thresholds | Objective ship/no-ship decision | Teams debate thresholds in practice | I defined thresholds and pass/fail criteria |
| "Do not ship" recommendation | Shows judgment under ambiguity, the project's highlight | A real team might disagree | My call; AI helped structure the write-up |

---

## Phase 5: Interactive Dashboard

Built as a single HTML file with 4 tabs: Experiment Results, Guardrail Monitoring, Daily Mix Funnel, Baseline Insights. The reason for HTML over Streamlit or Tableau: an interviewer can open `index.html` directly from the repo without installing anything.

A couple of bugs came up during review. The funnel chart showed "Infinity%" labels (Plotly division error) and one of the baseline charts had an inverted y-axis. Both were caught and fixed before final commit.

The threshold lines on the guardrail charts (orange dashed lines at -10% diversity, -5% search) were a deliberate design choice. They make the PASS/FAIL verdict visually obvious without needing to read the numbers.

**AI usage:** I built the dashboard with AI-assisted coding, defining the layout, tab structure, which metrics go where, and the visual design. I also caught and flagged the bugs from visual inspection.

| Decision | Why | Limitation | AI Role |
|----------|-----|------------|---------|
| 4-tab HTML dashboard | Self-contained, no install needed | Static (no live data connection) | I defined layout and metrics; AI-assisted build |
| Threshold lines on guardrails | Makes pass/fail visually obvious | Hardcoded values | I specified design; AI-assisted implementation |
| Funnel as HTML bars (not Plotly) | Plotly funnel had Infinity% bug | Less interactive | I caught bug and directed rebuild |

---

## Phase 6: Case Study & Deck

**Case study** is 9 sections, about 8 pages. Structure follows how product teams actually present: problem, data, insights, feature, experiment, results, impact, alternatives, roadmap. I put the methodology note prominently in Section 2 rather than hiding it in a footnote. Anyone who reads the case study knows immediately that this is simulated data and what that means.

**Deck** is 5 slides. The final slide ("The Hard Decision") is the closer. It's what the audience remembers. Every number on every slide was cross-checked against the notebook outputs after the final data generation.

All numbers across case study, deck, dashboard, notebooks, and README were verified in a full audit (58 data points checked against raw CSVs). Three mismatches were found and fixed before the final commit.

**AI usage:** I created both deliverables with AI-assisted drafting. I wrote the narrative framing, ensured every number matched, and edited the case study to sound like me rather than a template. The deck layout went through multiple rounds of visual review and iteration.

| Decision | Why | Limitation | AI Role |
|----------|-----|------------|---------|
| 9-section case study | Comprehensive but scannable | Long, interviewers may skim | I designed structure and wrote narrative; AI-assisted drafting |
| Prominent methodology note | Protects against "is this real data?" questions | Might over-explain | I decided placement and content |
| 5-slide deck | Concise for a 10-min walkthrough | Omits some detail | I defined content and layout; AI-assisted build |

---

## How I Used AI on This Project

I used AI as a drafting tool for code and documentation: SQL queries, Python scripts, chart code, dashboard HTML, and document scaffolds. I also used AI tools for batch file edits and cross-file consistency checks. Every piece of generated code was reviewed, tested, and modified before use.

The analytical work (the part that actually matters) was mine:

- I framed the problem and chose retention as the lens (not engagement, not revenue, not NPS)
- I decided which three behavioral hypotheses to investigate and why those specific ones motivate a playlist feature
- I designed the experiment: the metrics, the randomisation approach, the guardrail thresholds, and the pre-registered pass/fail criteria
- I identified that raw unique artist counts were giving a misleading result and switched to a normalized diversity metric (artists per 100 plays). This single decision changed the project's conclusion from "ship" to "do not ship"
- I ran three calibration cycles on the data generator, diagnosing why each round produced wrong numbers (multiplicative boost compounding, engagement-volume confound on diversity, flat behavioral signals) and specifying what to fix
- I made the ship/no-ship judgment, recommending against shipping a feature with strong positive retention because a guardrail failed, and built the argument for why that's the right call
- I caught visual bugs in the dashboard and deck through manual review
- I wrote the case study narrative and edited every deliverable to be consistent and interview-ready

Where AI added value was implementation speed. Writing 12 SQL queries from scratch would take a day; with AI drafting from my spec, it took an hour. Same for the Python generator, the notebook scaffolding, and the dashboard. That time savings let me spend more cycles on calibration, interpretation, and polish, the parts that differentiate a strong portfolio piece from a generic one.

I'm transparent about this because using AI well is a skill in itself. Knowing what to ask for, how to validate the output, and where AI can't help (analytical judgment, business framing, the hard trade-off decision): that's the muscle I'm demonstrating.