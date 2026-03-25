# Daily Mix: Designing a Personalised Playlist to Fix New-User Retention

**Vartika** | Product Analytics Case Study | Portfolio Project

---

## 1. Problem & Context

A mobile-first freemium music streaming app observed D30 retention for new users decline from ~28% to ~23% over two quarters. Early-life engagement - first-week listening minutes - also fell, particularly on mobile. Qualitative research (user interviews, session replays, support tickets) pointed to a consistent pattern: new users couldn't find an easy "press play" option, their early sessions were short and search-dominated, and many churned before discovering content they loved.

The business impact was material. With approximately 12,000 new signups per cohort window, every percentage point of D30 retention represented roughly 120 retained users, each of whom contributes to long-term LTV through ad impressions (free tier) or subscription conversion (premium tier). Leadership set a target: recover at least 3 percentage points of D30 retention within one quarter, without degrading content discovery or ecosystem diversity.

The hypothesis was simple: if we reduce the friction between "open the app" and "hear something good," new users will form listening habits faster and retain better.

---

## 2. Data Model & Tracking Design

The analytical dataset spans five tables designed to capture the full user journey:

**Users** (~12,000 rows) - one row per new signup, with signup date, platform (iOS 45%, Android 42%, Web 13%), country (US, UK, DE, IN, BR), acquisition channel (organic, paid, referral, social), initial plan (88% free, 12% premium), and experiment variant assignment (control or daily_mix, roughly 50/50 split).

**Tracks** (2,500 rows) and **Artists** (500 rows) - the content catalog. Tracks carry genre, duration, and popularity bucket (top 1%, top 10%, long tail). Artists carry a primary region and popularity tier. This structure lets us measure diversity and surface-level content health.

**Sessions** (~60K+ rows) - one row per app session, capturing session start/end timestamps, total play milliseconds, total skips, and device type. This is the primary source for engagement duration metrics.

**Events** (~690K rows) - the event stream. Every meaningful user action is logged: app opens, plays (with source attribution - home, search, playlist, library, daily_mix), daily mix impressions, clicks, saves, and more. Source attribution on events enables the cannibalization analysis that ultimately proved critical.

The tracking design was intentional about a few things. First, source attribution on every play event (not just sessions) makes it possible to distinguish whether Daily Mix listening is additive or substitutive. Second, separating `daily_mix_play` from generic `play` events allows clean funnel measurement without ambiguity. Third, storing `total_play_ms` at the session level (rather than summing track durations) gives a ground-truth measure of actual listening time.

**Methodology note:** All data in this project is synthetic, generated with a custom Python simulator. The generator embeds behavioural correlations via latent user traits (e.g., a "curiosity" factor that influences both discovery breadth and retention propensity) rather than hardcoding outcomes directly. This means the analysis recovers approximate effect sizes with realistic noise and variance - the same way a real dataset would behave. The value of this project is the analytical framework and decision-making process, not the specific numbers. Where I cite p-values or confidence intervals, they reflect real statistical tests on the generated data.

---

## 3. Baseline Analysis & Key Insights

Before designing the feature, I conducted a baseline analysis on the full user cohort (both variants, pre-experiment period behaviour) to understand what drives retention among new users. Three insights emerged:

**Insight 1: Speed to first play matters.** Users who played a track within 2 minutes of their first app open had 65.6% D7 retention, compared to 58.2% for the 2–5 minute group and 47.9% for users who took longer than 5 minutes. The fast-activator group represented 54.7% of users - meaning the app was already doing a reasonable job for the majority, but the ~45% who were slower to activate had substantially worse outcomes. The 37% relative lift (65.6 vs 47.9) suggested that removing friction at the moment of first open could meaningfully shift the retention curve.

**Insight 2: Deep early sessions predict long-term retention.** Users who had at least one 15+ minute listening session within their first 72 hours retained at 38.5% at D30, compared to 19.2% for those without a deep session - a 2.0x ratio. About 34.9% of users achieved this milestone organically. The implication: if we can engineer an experience that makes it easy to slip into a 15+ minute session early on, we can pull more users into the high-retention cohort.

**Insight 3: Discovery has an independent effect on retention.** To control for the obvious confound (heavy listeners discover more artists simply because they listen more), I stratified users into listening-time terciles and compared D30 retention between those who discovered 3+ new artists in week 1 versus those who didn't, within each tercile. In the low-listening tercile, the 3+ artist group retained at 19.6% vs 13.3% (1.5x). In the medium tercile, 26.1% vs 14.1% (1.9x). In the high tercile, 35.2% vs 33.3% (1.1x - less pronounced because heavy listeners tend to discover naturally). The pattern across the lower two terciles is consistent: discovery drives retention independently of total listening volume.

These three insights converged on a single design direction: give new users a low-friction, lean-back listening experience that surfaces diverse music from day one.

---

## 4. Daily Mix Feature Design

The proposed feature: a personalised **Daily Mix** playlist, pinned to the top of the Home screen for the user's first 30 days.

The design principles:

- **Zero friction.** One tap to start playing. No browsing, no searching, no decision fatigue. This directly targets Insight 1 (speed to first play).

- **Session depth by default.** The mix is long enough (30+ tracks, ~90 minutes) that users can naturally drift into 15+ minute sessions without conscious effort. This targets Insight 2 (deep sessions).

- **Diversity as a core ingredient.** The mix algorithm is seeded with a broad genre palette, drawing from at least 10–15 distinct artists per daily refresh. This targets Insight 3 (discovery), while also ensuring the playlist feels fresh day after day.

- **Home surface placement.** Pinning the mix on Home (rather than burying it in a playlist tab) means it's the first thing users see on every open. This maximises impression-to-play conversion and reinforces the habit loop.

- **30-day window.** The feature is explicitly time-bounded to the new-user period. After 30 days, the mix transitions to a regular recommendation feature. This scopes the experiment cleanly and avoids long-term UI clutter.

The hypothesis: Daily Mix will increase early listening depth, accelerate habit formation, and improve D30 retention by at least 3 percentage points - without cannibalising search or degrading content diversity.

---

## 5. Experiment Design

The experiment was a standard two-variant A/B test:

- **Control** (~6,065 users): Standard home screen, no Daily Mix tile. Users discover music through search, editorial playlists, and algorithmic recommendations.

- **Treatment** (~5,935 users): Daily Mix tile pinned at the top of the Home screen. All other features remain identical.

**Randomisation** was at the user level, assigned at signup. The ~50/50 split yielded roughly balanced groups across platform, country, and acquisition channel. The signup window spanned 6 weeks (42 days), with a 30-day observation period after each user's signup date.

**Primary metric:** D30 retention (binary - did the user have any active event on exactly day 30 post-signup). Secondary: D7 retention, weekly listening minutes (median, to handle power-user skew).

**Guardrail metrics** (pre-registered thresholds):
- Artist diversity: unique artists per 100 plays. Threshold: no more than 10% decline vs control.
- Search usage: average searches per user. Threshold: no more than 5% decline.
- Cannibalization: net listening minutes by source. Monitored for directional shifts.

**Statistical approach:** Retention is reported as proportions with 95% confidence intervals and two-proportion z-tests. Engagement metrics use medians and Winsorized means (capped at p95) to handle right-skew. Non-parametric tests (Mann-Whitney U) for diversity. All tests are two-sided. No multiple-testing correction was applied (this is a portfolio project; in production, I would use Bonferroni or a sequential testing framework).

---

## 6. Results, Trade-offs, and the Hard Decision

### Primary Results

| Metric | Control | Treatment | Delta | Significance |
| --- | --- | --- | --- | --- |
| D30 retention | 23.3% | 28.6% | +5.3 pp | p < 0.0001 |
| D7 retention | 55.1% | 64.5% | +9.3 pp | p < 0.0001 |
| Weekly listening (median) | 45.6 min | 52.4 min | +14.7% | Significant |

The retention uplift exceeded the 3 pp target by a wide margin. D7 showed an even larger gap (+9.3 pp), suggesting Daily Mix accelerates early habit formation. Weekly listening was 14.7% higher in treatment (median), confirming deeper engagement.

Segment analysis showed the effect was robust across platforms (Android +6.8 pp, iOS +5.1 pp, Web +1.3 pp) and geographies (Brazil +8.7 pp, UK +6.5 pp, India +4.7 pp, US +4.5 pp, Germany +3.8 pp). The smaller Web and Germany deltas warrant monitoring but don't undermine the overall finding.

### Guardrail Results

| Guardrail | Control | Treatment | Delta | Verdict |
| --- | --- | --- | --- | --- |
| Artist diversity (per 100 plays) | 66.81 | 53.55 | -19.8% | **FAILS** (>10% threshold) |
| Search usage (searches/user) | 12.04 | 11.62 | -3.5% | Passes (<5% threshold) |
| Net listening min | baseline | +11.2% | Additive | Monitor |

**Artist diversity dropped 19.8%** - nearly double the acceptable threshold. The Daily Mix algorithm, despite its design intent, concentrated listening around a narrower set of popular artists. This is a classic recommender-system failure mode: optimising for immediate engagement (play-through rate, skip rate) at the expense of breadth. The Mann-Whitney U test confirmed the difference was highly significant (p < 0.0001).

**Search usage declined only 3.5%**, well within the 5% threshold. Users in the treatment group still searched at nearly the same rate, suggesting Daily Mix supplemented rather than replaced active discovery behaviour.

**Cannibalization analysis** revealed a nuanced picture. Daily Mix added 37.5 min/user of listening, but Home surface listening fell from 46.8 to 23.1 min/user (-50.6%). Search listening was roughly flat (30.4 vs 31.5 min/user). Net listening increased by 11.2%. In other words, Daily Mix partially substituted for Home browsing but generated enough incremental listening to be net-positive on total minutes.

### The Hard Decision

This is where the analysis gets interesting - and where a less careful team might have shipped the feature.

The retention uplift is large and statistically significant. Weekly listening is up. Search isn't cannibalised. By most metrics, Daily Mix is a clear win.

But the 19.8% drop in artist diversity is a serious ecosystem concern. In a two-sided marketplace, artist diversity isn't just a nice-to-have metric - it directly affects long-tail artist economics, catalog utilisation, and long-term user satisfaction (filter bubble effects). Shipping a feature that concentrates listening on fewer artists could harm artist retention on the supply side and create homogeneity fatigue on the demand side.

**Recommendation: Do not ship the initial design.** Instead, iterate on the mix algorithm with explicit diversity constraints (minimum artist count per mix, genre distribution requirements, long-tail quota) and re-test. The retention signal is strong enough that a diversity-improved variant should still outperform control while respecting ecosystem guardrails.

---

## 7. Business Impact Model

To quantify the opportunity, I modelled the potential impact of a diversity-constrained Daily Mix variant that achieves 80% of the observed retention uplift while passing all guardrails.

**Assumptions:**
- Conservative uplift: +4.2 pp D30 retention (80% of observed +5.3 pp)
- Cohort size: ~12,000 new users per 6-week window (~2,000/week)
- Monthly cohorts: ~8,600 new users/month
- Free-to-premium conversion rate: 4.5% (industry benchmark)
- Premium ARPU: $9.99/month
- Average premium lifetime: 14 months
- Ad-supported free-user ARPU: $0.50/month
- Average free-user lifetime: 6 months

**Incremental retained users per month:** 8,600 × 0.042 = ~361 users

**Annual incremental revenue:**
- Premium path: 361 × 4.5% × $9.99 × 14 = ~$2,270/month → ~$27K/year
- Free path: 361 × 95.5% × $0.50 × 6 = ~$1,035/month → ~$12K/year
- Combined: ~$39K/year from a single feature change

These are conservative estimates for a portfolio-scale dataset. At production scale (millions of new users per month), the same 4.2 pp uplift would translate to tens of thousands of incremental retained users and proportionally larger revenue impact. The key insight isn't the absolute number - it's that early-life retention is a high-leverage intervention point because it compounds across every subsequent cohort.

---

## 8. Alternatives & Prioritisation

Daily Mix isn't the only possible intervention. Here's how it compares to alternatives I considered:

**Option A: Onboarding quiz → personalised seed playlist.** A 3-question taste quiz at signup, generating an immediate personalised playlist. Pros: faster personalisation, no cold-start problem. Cons: adds friction at the highest-churn moment (first open), quiz fatigue is real, and it doesn't solve the recurring-session problem. Estimated impact: moderate D7 lift, limited D30 effect.

**Option B: Push notification nudges.** Time-based nudges ("Your evening mix is ready") at optimal engagement windows. Pros: low engineering cost, no UI changes. Cons: notification fatigue, doesn't improve session quality, doesn't address the core "nothing to play" problem for new users. Estimated impact: small D7 lift (~1–2 pp), negligible D30 effect.

**Option C: Social listening feed.** Show what friends or similar users are listening to. Pros: social proof, discovery. Cons: requires social graph (cold-start problem for new users), privacy concerns, significant engineering effort. Estimated impact: unknown - high variance.

**Option D: Daily Mix with diversity constraints (recommended).** The tested feature, re-engineered with explicit diversity floors. Pros: proven retention uplift, addresses all three baseline insights, low ongoing maintenance. Cons: requires algorithm iteration, needs re-test. Estimated impact: +4–5 pp D30, passing all guardrails.

**Prioritisation:** Option D is the clear winner on impact/effort ratio. Option B is a low-cost complement. Option A could be layered on later to improve cold-start personalisation for the mix itself.

---

## 9. Future Roadmap

The Daily Mix experiment opens several follow-on workstreams:

**Immediate (next sprint):** Implement diversity constraints in the mix algorithm. Minimum 12 unique artists per daily mix, at least 20% long-tail tracks, genre distribution matching the user's stated preferences (from optional onboarding) or a broad default. Re-run the A/B test with the constrained variant.

**Short-term (next quarter):** If the constrained variant ships, instrument deeper engagement metrics - skip rate per track position, save rate by genre, repeat-listen patterns. These feed back into the recommendation model to improve mix quality over time. Also, extend the analysis to premium conversion: does the Daily Mix cohort convert to paid at a higher rate?

**Medium-term (next half):** Evolve Daily Mix beyond the 30-day new-user window. Test whether a permanent Daily Mix feature sustains engagement for all users or only benefits the onboarding period. Explore contextual variants (morning mix, workout mix) based on session timing patterns.

**Long-term:** Build a unified home-screen recommendation framework where Daily Mix, editorial playlists, and algorithmic recommendations coexist with dynamic ranking based on user state (new vs returning, time of day, recent listening). The Daily Mix experiment provides the first evidence that lean-back, curated experiences outperform search-dominant interfaces for new users - a finding that should reshape the entire home-screen strategy.

---

*Portfolio project demonstrating end-to-end product analytics: problem framing → data modelling → baseline analysis → feature design → experiment design → results interpretation → business case. Analytical decisions are original. AI tools were used to accelerate SQL/Python drafting and dashboard implementation.*
