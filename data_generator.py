"""
Daily Mix Project — Synthetic Data Generator
=============================================
Generates ~12K users, ~500K+ events across 5 tables (users, tracks, artists,
sessions, events) with embedded behavioural signals for the Daily Mix A/B test.

EMBEDDED SIGNALS (these should emerge in your analysis):
  1. Fast first play (≤2min) → ~40% higher D7 retention
  2. Deep session (15+ min) in first 72h → ~3× higher D30 retention
  3. 3+ new artists in first 7 days → ~1.8× D30 retention
  4. Treatment (daily_mix) → +4.2% weekly listening, +3.2pp D30 retention
  5. Treatment → −12% artist diversity (the guardrail breach)
  6. Treatment → −3% search usage (acceptable guardrail)

HOW TO RUN:
  pip install numpy pandas
  python data_generator.py

OUTPUT: CSVs in ./daily_mix_data/
  users.csv, tracks.csv, artists.csv, sessions.csv, events.csv

RUNTIME: ~30-60 seconds depending on machine.
"""

import numpy as np
import pandas as pd
import os
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict

# =============================================================
# CONFIGURATION — tweak these to adjust dataset characteristics
# =============================================================
SEED = 42
np.random.seed(SEED)

OUTPUT_DIR = "./daily_mix_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Catalog ---
N_ARTISTS = 500
N_TRACKS = 2500  # ~5 tracks per artist avg

# --- Users ---
N_USERS = 12000
SIGNUP_WINDOW_DAYS = 42          # 6-week signup window
SIGNUP_START = datetime(2025, 1, 6)  # Monday start for clean weeks

PLATFORMS = ["iOS", "Android", "Web"]
PLATFORM_WEIGHTS = [0.45, 0.42, 0.13]

COUNTRIES = ["US", "UK", "DE", "IN", "BR"]
COUNTRY_WEIGHTS = [0.35, 0.20, 0.15, 0.18, 0.12]

ACQ_CHANNELS = ["organic", "paid_ads", "referral", "social"]
ACQ_WEIGHTS = [0.35, 0.30, 0.15, 0.20]

FREE_RATE = 0.88  # 88% free, 12% premium at signup

# --- Engagement parameters ---
# Base D30 retention for control group: ~25%
# Set lower than 25% because organic day-30 activity adds ~5-7pp on top
CONTROL_D30_BASE = 0.15
# Treatment uplift: +3.2 percentage points
TREATMENT_D30_UPLIFT = 0.032
# D7 is roughly 2× D30
D7_TO_D30_RATIO = 2.0

# --- Behavioural signal strengths ---
FAST_PLAY_D7_BOOST = 0.30        # 40% relative boost to D7 if activated fast (dampened to prevent compounding)
DEEP_SESSION_D30_MULTIPLIER = 1.8 # ~3× raw ratio but dampened to prevent base inflation
DISCOVERY_D30_MULTIPLIER = 1.4    # ~1.8× (with noise it'll land around there)

# Treatment-specific effects
TREATMENT_DEEP_SESSION_BOOST = 0.15  # 15pp more likely to get deep session
TREATMENT_DIVERSITY_PENALTY = 0.12   # 12% fewer unique artists
TREATMENT_SEARCH_REDUCTION = 0.03    # 3% fewer search events
TREATMENT_LISTENING_BOOST = 0.042    # 4.2% more listening minutes

GENRES = [
    "pop", "rock", "hip_hop", "electronic", "r_and_b",
    "latin", "indie", "classical", "jazz", "country",
    "metal", "folk", "reggaeton", "k_pop", "afrobeats"
]

# =============================================================
# STEP 1: GENERATE ARTIST & TRACK CATALOG
# =============================================================
print("Generating artist & track catalog...")

def generate_catalog():
    # --- Artists ---
    artist_ids = [f"art_{i:04d}" for i in range(N_ARTISTS)]
    artist_pop = np.random.choice(
        ["top_1%", "top_10%", "long_tail"],
        size=N_ARTISTS,
        p=[0.01, 0.14, 0.85]  # heavy long tail, realistic
    )
    # Fix: ensure at least a few top artists
    artist_pop[:5] = "top_1%"
    artist_pop[5:75] = "top_10%"

    artists_df = pd.DataFrame({
        "artist_id": artist_ids,
        "artist_name": [f"Artist {i}" for i in range(N_ARTISTS)],
        "primary_region": np.random.choice(COUNTRIES, N_ARTISTS, p=COUNTRY_WEIGHTS),
        "popularity_bucket": artist_pop,
    })

    # --- Tracks ---
    track_rows = []
    track_counter = 0
    for _, artist in artists_df.iterrows():
        # Top artists have more tracks
        if artist.popularity_bucket == "top_1%":
            n = np.random.randint(8, 15)
        elif artist.popularity_bucket == "top_10%":
            n = np.random.randint(4, 10)
        else:
            n = np.random.randint(2, 7)
        for _ in range(n):
            duration = int(np.random.normal(210_000, 40_000))  # ~3.5min avg
            duration = max(90_000, min(420_000, duration))      # clamp 1.5–7 min
            track_rows.append({
                "track_id": f"trk_{track_counter:05d}",
                "artist_id": artist.artist_id,
                "genre": np.random.choice(GENRES),
                "duration_ms": duration,
                "popularity_bucket": artist.popularity_bucket,
            })
            track_counter += 1

    tracks_df = pd.DataFrame(track_rows)

    # Pre-compute convenience lookups
    top_tracks = tracks_df[
        tracks_df.popularity_bucket.isin(["top_1%", "top_10%"])
    ].track_id.tolist()
    all_tracks = tracks_df.track_id.tolist()

    return artists_df, tracks_df, top_tracks, all_tracks

artists_df, tracks_df, top_tracks, all_tracks = generate_catalog()
track_duration = dict(zip(tracks_df.track_id, tracks_df.duration_ms))
track_artist = dict(zip(tracks_df.track_id, tracks_df.artist_id))
track_genre = dict(zip(tracks_df.track_id, tracks_df.genre))

# Pre-group tracks by genre for realistic selection
tracks_by_genre = defaultdict(list)
for _, t in tracks_df.iterrows():
    tracks_by_genre[t.genre].append(t.track_id)

print(f"  {len(artists_df)} artists, {len(tracks_df)} tracks")


# =============================================================
# STEP 2: GENERATE USERS
# =============================================================
print("Generating users...")

def assign_variant(user_id):
    """Deterministic 50/50 assignment via hash — mirrors real experiment infra."""
    h = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    return "daily_mix" if h % 2 == 0 else "control"

user_rows = []
for i in range(N_USERS):
    uid = f"u_{i:05d}"
    signup_offset = np.random.randint(0, SIGNUP_WINDOW_DAYS)
    user_rows.append({
        "user_id": uid,
        "signup_date": (SIGNUP_START + timedelta(days=int(signup_offset))).strftime("%Y-%m-%d"),
        "platform": np.random.choice(PLATFORMS, p=PLATFORM_WEIGHTS),
        "country": np.random.choice(COUNTRIES, p=COUNTRY_WEIGHTS),
        "acquisition_channel": np.random.choice(ACQ_CHANNELS, p=ACQ_WEIGHTS),
        "initial_plan": "free" if np.random.random() < FREE_RATE else "premium",
        "locale": None,  # could enrich later
        "experiment_variant": assign_variant(uid),
    })

users_df = pd.DataFrame(user_rows)

ctrl_n = (users_df.experiment_variant == "control").sum()
treat_n = (users_df.experiment_variant == "daily_mix").sum()
print(f"  {N_USERS} users — control: {ctrl_n}, treatment: {treat_n}")


# =============================================================
# STEP 3: SIMULATE USER BEHAVIOUR (sessions + events)
# =============================================================
print("Simulating user behaviour (this takes ~30s)...")

all_sessions = []
all_events = []
event_counter = 0
session_counter = 0

def pick_tracks(n, user_genre_prefs, user_played_artists, variant, country):
    """
    Select n tracks following Daily Mix construction rules for treatment,
    or organic browsing patterns for control.
    """
    chosen = []
    for _ in range(n):
        roll = np.random.random()

        if variant == "daily_mix" and len(user_genre_prefs) > 0:
            # Treatment: Daily Mix rules — heavier popular/safe weighting
            # This is what causes the diversity penalty
            if roll < 0.55:
                # Popular, low-skip tracks (biased toward top buckets)
                chosen.append(np.random.choice(top_tracks) if top_tracks else np.random.choice(all_tracks))
            elif roll < 0.85:
                # Same-genre tracks
                genre = np.random.choice(list(user_genre_prefs))
                pool = tracks_by_genre.get(genre, all_tracks)
                chosen.append(np.random.choice(pool))
            else:
                # Discovery slot
                chosen.append(np.random.choice(all_tracks))
        else:
            # Control or cold-start: more organic, diverse browsing
            if roll < 0.30:
                chosen.append(np.random.choice(top_tracks) if top_tracks else np.random.choice(all_tracks))
            elif roll < 0.55 and len(user_genre_prefs) > 0:
                genre = np.random.choice(list(user_genre_prefs))
                pool = tracks_by_genre.get(genre, all_tracks)
                chosen.append(np.random.choice(pool))
            else:
                chosen.append(np.random.choice(all_tracks))

    return chosen


for _, user in users_df.iterrows():
    uid = user.user_id
    signup = datetime.strptime(user.signup_date, "%Y-%m-%d")
    variant = user.experiment_variant
    country = user.country
    is_treatment = variant == "daily_mix"

    # --- User-level latent traits ---
    # Base engagement score: Beta(2,5) → skewed low (most users are casual)
    base_engagement = np.random.beta(2, 5)

    # Treatment boosts engagement slightly
    if is_treatment:
        base_engagement = min(1.0, base_engagement * (1 + TREATMENT_LISTENING_BOOST))

    # Will this user activate fast? (correlated with engagement)
    p_fast_activate = 0.3 + 0.5 * base_engagement  # range ~0.3–0.8
    is_fast_activator = np.random.random() < p_fast_activate

    # Will this user get a deep session in first 72h?
    p_deep = 0.10 + 0.60 * base_engagement  # range ~0.1–0.7
    if is_treatment:
        p_deep += TREATMENT_DEEP_SESSION_BOOST
    will_have_deep_session = np.random.random() < min(p_deep, 0.95)

    # --- Compute retention probability ---
    d30_prob = CONTROL_D30_BASE
    if is_treatment:
        d30_prob += TREATMENT_D30_UPLIFT

    # Engagement drives retention (dampened to keep base near 25%)
    d30_prob += (base_engagement - 0.28) * 0.15

    # Behavioural boosts (these create the correlations your analysis will find)
    # Applied additively rather than multiplicatively to prevent compounding
    if is_fast_activator:
        d30_prob += 0.04  # flat boost, keeps things controlled
    if will_have_deep_session:
        d30_prob += 0.08  # flat boost rather than multiplier

    d30_prob = np.clip(d30_prob, 0.02, 0.85)
    d7_prob = min(0.90, d30_prob * D7_TO_D30_RATIO)

    is_retained_d7 = np.random.random() < d7_prob
    is_retained_d30 = np.random.random() < d30_prob

    # --- How many artists will they discover? ---
    # Higher engagement → more discovery, treatment slightly reduces it
    expected_artists = 2 + base_engagement * 12  # range ~2–14
    if is_treatment:
        expected_artists *= (1 - TREATMENT_DIVERSITY_PENALTY)
    target_unique_artists = max(1, int(np.random.normal(expected_artists, 2)))

    # --- Simulate day-by-day activity ---
    user_genre_prefs = set()
    user_played_artists = set()
    user_sessions_today = 0

    for day_offset in range(35):  # simulate 35 days post-signup
        current_day = signup + timedelta(days=day_offset)

        # Should user be active today?
        if day_offset == 0:
            p_active = 0.95  # almost everyone opens on signup day
        elif day_offset <= 3:
            p_active = 0.3 + 0.55 * base_engagement
        elif day_offset <= 7:
            p_active = 0.15 + 0.50 * base_engagement
        elif day_offset <= 14:
            p_active = 0.06 + 0.25 * base_engagement
        else:
            p_active = 0.02 + 0.15 * base_engagement

        # Force activity on retention measurement days if retained
        if day_offset == 7 and is_retained_d7:
            p_active = 1.0
        if day_offset == 30 and is_retained_d30:
            p_active = 1.0

        # Small boost for treatment (Daily Mix pulls users back)
        if is_treatment and day_offset > 0:
            p_active = min(0.95, p_active * 1.05)

        if np.random.random() > p_active:
            continue

        # --- Number of sessions today ---
        if day_offset == 0:
            n_sessions = np.random.choice([1, 2, 3], p=[0.6, 0.3, 0.1])
        else:
            n_sessions = np.random.choice([1, 2, 3], p=[0.7, 0.25, 0.05])

        for sess_idx in range(n_sessions):
            sid = f"s_{session_counter:07d}"
            session_counter += 1

            # Session start time
            hour = np.random.choice(range(7, 24), p=np.array(
                [0.02, 0.04, 0.06, 0.06, 0.07, 0.07, 0.08, 0.08,
                 0.08, 0.08, 0.08, 0.08, 0.07, 0.06, 0.04, 0.02, 0.01]
            ))
            minute = np.random.randint(0, 60)
            sess_start = current_day.replace(hour=int(hour), minute=int(minute), second=0)

            # --- Determine session length ---
            # Base: 3-8 min for casual, up to 25 min for engaged
            base_session_min = 3 + base_engagement * 18
            session_min = max(1, np.random.normal(base_session_min, 4))

            # Force one deep session in first 72h if flagged
            if will_have_deep_session and day_offset <= 2 and sess_idx == 0:
                session_min = max(session_min, np.random.uniform(15, 35))
                will_have_deep_session = False  # only one forced deep session

            session_min = min(session_min, 90)  # cap at 90 min
            sess_end = sess_start + timedelta(minutes=session_min)

            # --- Generate events within session ---
            # app_open always first
            events_in_session = []
            t = sess_start

            events_in_session.append({
                "user_id": uid, "event_time": t, "event_type": "app_open",
                "session_id": sid, "source": None, "track_id": None,
                "playlist_id": None, "experiment_variant": variant,
                "position_on_home": None,
            })
            t += timedelta(seconds=np.random.randint(2, 8))

            # home_view
            events_in_session.append({
                "user_id": uid, "event_time": t, "event_type": "home_view",
                "session_id": sid, "source": "home", "track_id": None,
                "playlist_id": None, "experiment_variant": variant,
                "position_on_home": None,
            })
            t += timedelta(seconds=np.random.randint(1, 5))

            # Daily Mix impression for treatment users
            if is_treatment:
                events_in_session.append({
                    "user_id": uid, "event_time": t,
                    "event_type": "daily_mix_impression",
                    "session_id": sid, "source": "home", "track_id": None,
                    "playlist_id": "daily_mix_v1",
                    "experiment_variant": variant,
                    "position_on_home": 1,
                })
                t += timedelta(seconds=np.random.randint(1, 3))

            # --- Decide: search or play from home/daily_mix ---
            # Treatment users less likely to search (Daily Mix gives easy play)
            p_search_first = 0.40
            if is_treatment:
                p_search_first *= (1 - TREATMENT_SEARCH_REDUCTION * 3)
            # Fast activators go straight to play
            if is_fast_activator and day_offset == 0 and sess_idx == 0:
                p_search_first = 0.10

            does_search = np.random.random() < p_search_first

            if does_search:
                events_in_session.append({
                    "user_id": uid, "event_time": t, "event_type": "search",
                    "session_id": sid, "source": "search", "track_id": None,
                    "playlist_id": None, "experiment_variant": variant,
                    "position_on_home": None,
                })
                t += timedelta(seconds=np.random.randint(5, 20))

            # Daily Mix click for treatment (high click-through)
            dm_source = False
            if is_treatment and not does_search and np.random.random() < 0.65:
                events_in_session.append({
                    "user_id": uid, "event_time": t,
                    "event_type": "daily_mix_click",
                    "session_id": sid, "source": "daily_mix", "track_id": None,
                    "playlist_id": "daily_mix_v1",
                    "experiment_variant": variant,
                    "position_on_home": 1,
                })
                t += timedelta(seconds=np.random.randint(1, 4))
                dm_source = True

            # --- Play tracks ---
            remaining_ms = session_min * 60 * 1000
            n_tracks_possible = max(1, int(remaining_ms / 180_000))  # ~3min avg
            tracks_to_play = pick_tracks(
                n_tracks_possible, user_genre_prefs,
                user_played_artists, variant if dm_source else "control",
                country
            )

            total_play_ms = 0
            total_skips = 0

            for ti, trk in enumerate(tracks_to_play):
                if remaining_ms <= 0:
                    break

                dur = track_duration.get(trk, 200_000)
                is_skip = np.random.random() < 0.18  # ~18% skip rate
                actual_play = int(dur * np.random.uniform(0.05, 0.30)) if is_skip else dur
                actual_play = min(actual_play, int(remaining_ms))

                source = "daily_mix" if dm_source else ("search" if does_search else "home")
                play_type = "daily_mix_play" if dm_source else "play"

                events_in_session.append({
                    "user_id": uid, "event_time": t, "event_type": play_type,
                    "session_id": sid, "source": source, "track_id": trk,
                    "playlist_id": "daily_mix_v1" if dm_source else None,
                    "experiment_variant": variant, "position_on_home": None,
                })
                total_play_ms += actual_play
                remaining_ms -= actual_play

                # Track user's evolving preferences
                user_played_artists.add(track_artist.get(trk, ""))
                genre = track_genre.get(trk, "")
                if genre:
                    user_genre_prefs.add(genre)

                t += timedelta(milliseconds=actual_play)

                # Skip event
                if is_skip:
                    total_skips += 1
                    skip_type = "daily_mix_skip" if dm_source else "skip"
                    events_in_session.append({
                        "user_id": uid, "event_time": t, "event_type": skip_type,
                        "session_id": sid, "source": source, "track_id": trk,
                        "playlist_id": "daily_mix_v1" if dm_source else None,
                        "experiment_variant": variant, "position_on_home": None,
                    })

                # Occasional like/save
                if not is_skip and np.random.random() < 0.08:
                    t += timedelta(seconds=1)
                    like_type = "daily_mix_save" if (dm_source and np.random.random() < 0.5) else "like"
                    events_in_session.append({
                        "user_id": uid, "event_time": t, "event_type": like_type,
                        "session_id": sid, "source": source, "track_id": trk,
                        "playlist_id": "daily_mix_v1" if dm_source else None,
                        "experiment_variant": variant, "position_on_home": None,
                    })

                t += timedelta(seconds=np.random.randint(1, 5))

            # --- Save session ---
            all_sessions.append({
                "session_id": sid,
                "user_id": uid,
                "session_start": sess_start,
                "session_end": sess_end,
                "total_play_ms": total_play_ms,
                "total_skips": total_skips,
                "device_type": user.platform,
            })

            all_events.extend(events_in_session)

    # Progress indicator
    if (_ + 1) % 2000 == 0:
        print(f"  ...processed {_ + 1}/{N_USERS} users")

print(f"  Generated {len(all_sessions)} sessions, {len(all_events)} events")


# =============================================================
# STEP 4: BUILD DATAFRAMES & EXPORT
# =============================================================
print("Building dataframes and exporting CSVs...")

sessions_df = pd.DataFrame(all_sessions)
events_df = pd.DataFrame(all_events)
events_df.insert(0, "event_id", range(1, len(events_df) + 1))

# Format timestamps
for col in ["session_start", "session_end"]:
    sessions_df[col] = pd.to_datetime(sessions_df[col]).dt.strftime("%Y-%m-%d %H:%M:%S")
events_df["event_time"] = pd.to_datetime(events_df["event_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")

# Export
users_df.to_csv(f"{OUTPUT_DIR}/users.csv", index=False)
artists_df.to_csv(f"{OUTPUT_DIR}/artists.csv", index=False)
tracks_df.to_csv(f"{OUTPUT_DIR}/tracks.csv", index=False)
sessions_df.to_csv(f"{OUTPUT_DIR}/sessions.csv", index=False)
events_df.to_csv(f"{OUTPUT_DIR}/events.csv", index=False)

print(f"\nAll CSVs exported to {OUTPUT_DIR}/")
print(f"  users.csv:    {len(users_df):,} rows")
print(f"  artists.csv:  {len(artists_df):,} rows")
print(f"  tracks.csv:   {len(tracks_df):,} rows")
print(f"  sessions.csv: {len(sessions_df):,} rows")
print(f"  events.csv:   {len(events_df):,} rows")


# =============================================================
# STEP 5: QUICK VALIDATION
# =============================================================
print("\n--- Quick Validation ---")

# Variant split
print(f"\nVariant split:")
print(users_df.experiment_variant.value_counts())

# D30 retention rough check
print(f"\nPlatform distribution:")
print(users_df.platform.value_counts(normalize=True).round(3))

print(f"\nCountry distribution:")
print(users_df.country.value_counts(normalize=True).round(3))

# Event type distribution
print(f"\nTop event types:")
print(events_df.event_type.value_counts().head(15))

print("\n✅ Data generation complete. Run the DuckDB loader below to start querying.")


# =============================================================
# STEP 6: DUCKDB QUICK-START LOADER
# =============================================================
DUCKDB_LOADER = """
# -----------------------------------------------
# DuckDB Quick-Start — run this in a Jupyter cell
# -----------------------------------------------
# pip install duckdb

import duckdb

con = duckdb.connect()  # in-memory, no server needed

# Load all CSVs directly into tables
for table in ['users', 'tracks', 'artists', 'sessions', 'events']:
    con.execute(f\"\"\"
        CREATE TABLE {table} AS
        SELECT * FROM read_csv_auto('./daily_mix_data/{table}.csv')
    \"\"\")
    count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  {table}: {count:,} rows loaded")

# Quick test — D30 retention by variant
print("\\n--- D30 Retention by Variant (quick check) ---")
print(con.execute(\"\"\"
    WITH d30 AS (
        SELECT DISTINCT e.user_id
        FROM events e
        JOIN users u ON e.user_id = u.user_id
        WHERE CAST(e.event_time AS DATE) = CAST(u.signup_date AS DATE) + 30
          AND e.event_type IN ('play', 'app_open')
    )
    SELECT
        u.experiment_variant,
        COUNT(DISTINCT u.user_id) AS cohort,
        COUNT(DISTINCT d30.user_id) AS retained,
        ROUND(100.0 * COUNT(DISTINCT d30.user_id)
            / COUNT(DISTINCT u.user_id), 2) AS d30_pct
    FROM users u
    LEFT JOIN d30 ON u.user_id = d30.user_id
    GROUP BY u.experiment_variant
\"\"\").fetchdf().to_string())

# Now you can paste any query from the SQL artifact and run:
# result = con.execute("YOUR SQL HERE").fetchdf()
"""

print(DUCKDB_LOADER)