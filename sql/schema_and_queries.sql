-- ============================================================
-- DAILY MIX PROJECT — SQL SCHEMA & CORE ANALYTICAL QUERIES
-- Target: PostgreSQL (minor tweaks for BigQuery noted inline)
-- ============================================================


-- ============================================================
-- PART 1: TABLE DEFINITIONS (DDL)
-- ============================================================

CREATE TABLE users (
    user_id          TEXT PRIMARY KEY,
    signup_date      DATE NOT NULL,
    platform         TEXT NOT NULL CHECK (platform IN ('iOS', 'Android', 'Web')),
    country          TEXT NOT NULL,
    acquisition_channel TEXT NOT NULL,  -- 'paid_ads', 'organic', 'referral', 'social'
    initial_plan     TEXT NOT NULL CHECK (initial_plan IN ('free', 'premium')),
    experiment_variant TEXT CHECK (experiment_variant IN ('control', 'daily_mix'))
);

CREATE TABLE tracks (
    track_id         TEXT PRIMARY KEY,
    artist_id        TEXT NOT NULL,
    genre            TEXT NOT NULL,
    duration_ms      INT NOT NULL,
    popularity_bucket TEXT NOT NULL  -- 'top_1%', 'top_10%', 'long_tail'
);

CREATE TABLE artists (
    artist_id        TEXT PRIMARY KEY,
    artist_name      TEXT,
    primary_region   TEXT,
    popularity_bucket TEXT NOT NULL
);

CREATE TABLE events (
    event_id         BIGSERIAL PRIMARY KEY,  -- BigQuery: use INT64 + generate
    user_id          TEXT NOT NULL,
    event_time       TIMESTAMP NOT NULL,
    event_type       TEXT NOT NULL,
    session_id       TEXT,
    source           TEXT,  -- 'home', 'search', 'playlist', 'library', 'notification', 'daily_mix'
    track_id         TEXT,
    playlist_id      TEXT,
    experiment_variant TEXT,
    position_on_home INT   -- for daily_mix_impression events
);

CREATE TABLE sessions (
    session_id       TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    session_start    TIMESTAMP NOT NULL,
    session_end      TIMESTAMP NOT NULL,
    total_play_ms    BIGINT DEFAULT 0,
    total_skips      INT DEFAULT 0,
    device_type      TEXT
);

-- Indexes for common query patterns
CREATE INDEX idx_events_user_time ON events (user_id, event_time);
CREATE INDEX idx_events_type ON events (event_type);
CREATE INDEX idx_events_session ON events (session_id);
CREATE INDEX idx_sessions_user ON sessions (user_id);
CREATE INDEX idx_users_signup ON users (signup_date);


-- ============================================================
-- PART 2: BASELINE ANALYSIS QUERIES
-- ============================================================

-- -------------------------------------------------
-- 2A. ACTIVATION: % of new users who play a track
--     within 2 minutes of first app_open
-- -------------------------------------------------
WITH first_open AS (
    SELECT
        u.user_id,
        u.signup_date,
        u.platform,
        u.country,
        u.experiment_variant,
        MIN(e.event_time) AS first_open_time
    FROM users u
    JOIN events e
        ON u.user_id = e.user_id
        AND e.event_type = 'app_open'
    GROUP BY u.user_id, u.signup_date, u.platform, u.country, u.experiment_variant
),
first_play AS (
    SELECT
        e.user_id,
        MIN(e.event_time) AS first_play_time
    FROM events e
    WHERE e.event_type IN ('play', 'daily_mix_play')
    GROUP BY e.user_id
)
SELECT
    fo.experiment_variant,
    fo.platform,
    COUNT(DISTINCT fo.user_id) AS total_users,
    COUNT(DISTINCT CASE
        WHEN fp.first_play_time IS NOT NULL
             AND fp.first_play_time <= fo.first_open_time + INTERVAL '2 minutes'
        THEN fo.user_id
    END) AS activated_within_2min,
    ROUND(
        100.0 * COUNT(DISTINCT CASE
            WHEN fp.first_play_time IS NOT NULL
                 AND fp.first_play_time <= fo.first_open_time + INTERVAL '2 minutes'
            THEN fo.user_id
        END) / NULLIF(COUNT(DISTINCT fo.user_id), 0),
        2
    ) AS activation_rate_pct
FROM first_open fo
LEFT JOIN first_play fp ON fo.user_id = fp.user_id
GROUP BY fo.experiment_variant, fo.platform
ORDER BY fo.experiment_variant, fo.platform;


-- -------------------------------------------------
-- 2B. D7 AND D30 RETENTION BY SIGNUP COHORT
-- -------------------------------------------------
WITH d7 AS (
    SELECT DISTINCT e.user_id
    FROM events e
    JOIN users u ON e.user_id = u.user_id
    WHERE e.event_time::DATE = u.signup_date + 7
      AND e.event_type IN ('play', 'app_open', 'daily_mix_play')
),
d30 AS (
    SELECT DISTINCT e.user_id
    FROM events e
    JOIN users u ON e.user_id = u.user_id
    WHERE e.event_time::DATE = u.signup_date + 30
      AND e.event_type IN ('play', 'app_open', 'daily_mix_play')
)
SELECT
    u.signup_date,
    u.experiment_variant,
    COUNT(DISTINCT u.user_id) AS cohort_size,
    COUNT(DISTINCT d7.user_id) AS active_d7,
    COUNT(DISTINCT d30.user_id) AS active_d30,
    ROUND(100.0 * COUNT(DISTINCT d7.user_id)
        / NULLIF(COUNT(DISTINCT u.user_id), 0), 2) AS d7_retention_pct,
    ROUND(100.0 * COUNT(DISTINCT d30.user_id)
        / NULLIF(COUNT(DISTINCT u.user_id), 0), 2) AS d30_retention_pct
FROM users u
LEFT JOIN d7 ON u.user_id = d7.user_id
LEFT JOIN d30 ON u.user_id = d30.user_id
GROUP BY u.signup_date, u.experiment_variant
ORDER BY u.signup_date, u.experiment_variant;


-- -------------------------------------------------
-- 2C. FIRST-WEEK ENGAGEMENT: listening minutes,
--     sessions, avg session length (D0-D7)
-- -------------------------------------------------
WITH first_week_sessions AS (
    SELECT
        s.user_id,
        u.experiment_variant,
        u.platform,
        s.session_id,
        s.total_play_ms,
        s.total_skips,
        EXTRACT(EPOCH FROM (s.session_end - s.session_start)) / 60.0 AS session_length_min
    FROM sessions s
    JOIN users u ON s.user_id = u.user_id
    WHERE s.session_start < u.signup_date + INTERVAL '8 days'
      AND s.session_start >= u.signup_date::TIMESTAMP
)
SELECT
    experiment_variant,
    platform,
    COUNT(DISTINCT user_id) AS users,
    ROUND(AVG(user_total_min), 1) AS avg_listening_min,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY user_total_min), 1) AS median_listening_min,
    ROUND(AVG(user_sessions), 1) AS avg_sessions,
    ROUND(AVG(avg_session_len), 1) AS avg_session_length_min
FROM (
    SELECT
        user_id,
        experiment_variant,
        platform,
        SUM(total_play_ms) / 60000.0 AS user_total_min,
        COUNT(session_id) AS user_sessions,
        AVG(session_length_min) AS avg_session_len
    FROM first_week_sessions
    GROUP BY user_id, experiment_variant, platform
) per_user
GROUP BY experiment_variant, platform
ORDER BY experiment_variant, platform;


-- -------------------------------------------------
-- 2D. BEHAVIOURAL INSIGHT: speed-to-first-play
--     vs D7 retention
-- -------------------------------------------------
WITH first_open AS (
    SELECT user_id, MIN(event_time) AS first_open_time
    FROM events WHERE event_type = 'app_open'
    GROUP BY user_id
),
first_play AS (
    SELECT user_id, MIN(event_time) AS first_play_time
    FROM events WHERE event_type IN ('play', 'daily_mix_play')
    GROUP BY user_id
),
time_to_play AS (
    SELECT
        fo.user_id,
        EXTRACT(EPOCH FROM (fp.first_play_time - fo.first_open_time)) / 60.0 AS minutes_to_first_play,
        CASE
            WHEN fp.first_play_time <= fo.first_open_time + INTERVAL '2 minutes' THEN 'fast (≤2min)'
            WHEN fp.first_play_time <= fo.first_open_time + INTERVAL '5 minutes' THEN 'medium (2-5min)'
            ELSE 'slow (>5min)'
        END AS speed_bucket
    FROM first_open fo
    LEFT JOIN first_play fp ON fo.user_id = fp.user_id
),
d7_activity AS (
    SELECT DISTINCT e.user_id
    FROM events e
    JOIN users u ON e.user_id = u.user_id
    WHERE e.event_time::DATE = u.signup_date + 7
      AND e.event_type IN ('play', 'app_open', 'daily_mix_play')
)
SELECT
    ttp.speed_bucket,
    COUNT(DISTINCT ttp.user_id) AS users,
    COUNT(DISTINCT d7.user_id) AS retained_d7,
    ROUND(100.0 * COUNT(DISTINCT d7.user_id)
        / NULLIF(COUNT(DISTINCT ttp.user_id), 0), 2) AS d7_retention_pct
FROM time_to_play ttp
LEFT JOIN d7_activity d7 ON ttp.user_id = d7.user_id
GROUP BY ttp.speed_bucket
ORDER BY d7_retention_pct DESC;


-- -------------------------------------------------
-- 2E. BEHAVIOURAL INSIGHT: deep session in first
--     72h vs D30 retention
-- -------------------------------------------------
WITH deep_session_flag AS (
    SELECT
        s.user_id,
        MAX(CASE
            WHEN EXTRACT(EPOCH FROM (s.session_end - s.session_start)) / 60.0 >= 15
                 AND s.session_start::DATE - u.signup_date BETWEEN 0 AND 2
            THEN 1 ELSE 0
        END) AS had_deep_session
    FROM sessions s
    JOIN users u ON s.user_id = u.user_id
    GROUP BY s.user_id
),
d30_activity AS (
    SELECT DISTINCT e.user_id
    FROM events e
    JOIN users u ON e.user_id = u.user_id
    WHERE e.event_time::DATE = u.signup_date + 30
      AND e.event_type IN ('play', 'app_open', 'daily_mix_play')
)
SELECT
    CASE WHEN dsf.had_deep_session = 1
         THEN 'Had 15+ min session in 72h'
         ELSE 'No deep session in 72h'
    END AS segment,
    COUNT(DISTINCT dsf.user_id) AS users,
    COUNT(DISTINCT d30.user_id) AS retained_d30,
    ROUND(100.0 * COUNT(DISTINCT d30.user_id)
        / NULLIF(COUNT(DISTINCT dsf.user_id), 0), 2) AS d30_retention_pct
FROM deep_session_flag dsf
LEFT JOIN d30_activity d30 ON dsf.user_id = d30.user_id
GROUP BY dsf.had_deep_session
ORDER BY d30_retention_pct DESC;


-- -------------------------------------------------
-- 2F. BEHAVIOURAL INSIGHT: new artist discovery
--     in first 7 days vs D30 retention
--     (controlling for total listening time)
-- -------------------------------------------------
WITH first_week_plays AS (
    SELECT
        e.user_id,
        e.track_id,
        t.artist_id
    FROM events e
    JOIN users u ON e.user_id = u.user_id
    JOIN tracks t ON e.track_id = t.track_id
    WHERE e.event_type IN ('play', 'daily_mix_play')
      AND e.event_time < u.signup_date::TIMESTAMP + INTERVAL '8 days'
),
user_discovery AS (
    SELECT
        user_id,
        COUNT(DISTINCT artist_id) AS unique_artists
    FROM first_week_plays
    GROUP BY user_id
),
user_listening AS (
    SELECT
        s.user_id,
        SUM(s.total_play_ms) / 60000.0 AS total_listening_min
    FROM sessions s
    JOIN users u ON s.user_id = u.user_id
    WHERE s.session_start < u.signup_date::TIMESTAMP + INTERVAL '8 days'
    GROUP BY s.user_id
),
user_segments AS (
    SELECT
        ud.user_id,
        ud.unique_artists,
        CASE WHEN ud.unique_artists >= 3 THEN '3+ new artists' ELSE '<3 new artists' END AS discovery_segment,
        NTILE(3) OVER (ORDER BY ul.total_listening_min) AS listening_tercile
    FROM user_discovery ud
    JOIN user_listening ul ON ud.user_id = ul.user_id
),
d30_activity AS (
    SELECT DISTINCT e.user_id
    FROM events e
    JOIN users u ON e.user_id = u.user_id
    WHERE e.event_time::DATE = u.signup_date + 30
      AND e.event_type IN ('play', 'app_open', 'daily_mix_play')
)
SELECT
    us.listening_tercile,
    us.discovery_segment,
    COUNT(DISTINCT us.user_id) AS users,
    COUNT(DISTINCT d30.user_id) AS retained_d30,
    ROUND(100.0 * COUNT(DISTINCT d30.user_id)
        / NULLIF(COUNT(DISTINCT us.user_id), 0), 2) AS d30_retention_pct
FROM user_segments us
LEFT JOIN d30_activity d30 ON us.user_id = d30.user_id
GROUP BY us.listening_tercile, us.discovery_segment
ORDER BY us.listening_tercile, us.discovery_segment;


-- ============================================================
-- PART 3: EXPERIMENT ANALYSIS QUERIES
-- ============================================================

-- -------------------------------------------------
-- 3A. DAILY MIX FUNNEL
--     impression → click → play → repeat → save
-- -------------------------------------------------
WITH dm_users AS (
    SELECT user_id
    FROM users
    WHERE experiment_variant = 'daily_mix'
),
funnel AS (
    SELECT
        COUNT(DISTINCT CASE WHEN e.event_type = 'daily_mix_impression' THEN e.user_id END) AS impressions,
        COUNT(DISTINCT CASE WHEN e.event_type = 'daily_mix_click'      THEN e.user_id END) AS clicks,
        COUNT(DISTINCT CASE WHEN e.event_type = 'daily_mix_play'       THEN e.user_id END) AS players,
        COUNT(DISTINCT CASE WHEN e.event_type = 'daily_mix_save'       THEN e.user_id END) AS savers,
        -- Repeat players: played Daily Mix on 2+ distinct days
        COUNT(DISTINCT CASE WHEN repeat_days >= 2 THEN e2.user_id END) AS repeat_players
    FROM events e
    JOIN dm_users d ON e.user_id = d.user_id
    LEFT JOIN (
        SELECT user_id, COUNT(DISTINCT event_time::DATE) AS repeat_days
        FROM events
        WHERE event_type = 'daily_mix_play'
        GROUP BY user_id
    ) e2 ON e.user_id = e2.user_id
)
SELECT
    impressions,
    clicks,
    ROUND(100.0 * clicks / NULLIF(impressions, 0), 2) AS click_rate_pct,
    players,
    ROUND(100.0 * players / NULLIF(clicks, 0), 2) AS play_rate_pct,
    repeat_players,
    ROUND(100.0 * repeat_players / NULLIF(players, 0), 2) AS repeat_rate_pct,
    savers,
    ROUND(100.0 * savers / NULLIF(players, 0), 2) AS save_rate_pct
FROM funnel;


-- -------------------------------------------------
-- 3B. WEEKLY LISTENING MINUTES: treatment vs control
--     with median, mean, and Winsorized mean
-- -------------------------------------------------
WITH weekly_minutes AS (
    SELECT
        u.user_id,
        u.experiment_variant,
        FLOOR((s.session_start::DATE - u.signup_date) / 7) + 1 AS week_num,
        SUM(s.total_play_ms) / 60000.0 AS listening_min
    FROM sessions s
    JOIN users u ON s.user_id = u.user_id
    WHERE s.session_start >= u.signup_date::TIMESTAMP
      AND s.session_start < u.signup_date::TIMESTAMP + INTERVAL '31 days'
    GROUP BY u.user_id, u.experiment_variant, week_num
),
p95 AS (
    SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY listening_min) AS cap
    FROM weekly_minutes
)
SELECT
    wm.experiment_variant,
    wm.week_num,
    COUNT(DISTINCT wm.user_id) AS users,
    ROUND(AVG(wm.listening_min), 2) AS mean_min,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wm.listening_min), 2) AS median_min,
    ROUND(AVG(LEAST(wm.listening_min, p95.cap)), 2) AS winsorized_mean_min
FROM weekly_minutes wm
CROSS JOIN p95
GROUP BY wm.experiment_variant, wm.week_num
ORDER BY wm.week_num, wm.experiment_variant;


-- -------------------------------------------------
-- 3C. GUARDRAIL: search/discover usage by variant
-- -------------------------------------------------
SELECT
    u.experiment_variant,
    e.source,
    COUNT(*) AS total_events,
    COUNT(DISTINCT e.user_id) AS unique_users,
    ROUND(AVG(
        CASE WHEN e.event_type IN ('play', 'daily_mix_play')
             THEN t.duration_ms / 60000.0 END
    ), 2) AS avg_play_min_per_event
FROM events e
JOIN users u ON e.user_id = u.user_id
LEFT JOIN tracks t ON e.track_id = t.track_id
WHERE e.source IN ('search', 'home', 'playlist', 'library', 'daily_mix')
  AND e.event_time < u.signup_date::TIMESTAMP + INTERVAL '31 days'
GROUP BY u.experiment_variant, e.source
ORDER BY u.experiment_variant, e.source;


-- -------------------------------------------------
-- 3D. GUARDRAIL: artist diversity index by variant
--     (avg unique artists per user per week)
-- -------------------------------------------------
WITH weekly_artists AS (
    SELECT
        u.user_id,
        u.experiment_variant,
        FLOOR((e.event_time::DATE - u.signup_date) / 7) + 1 AS week_num,
        COUNT(DISTINCT t.artist_id) AS unique_artists
    FROM events e
    JOIN users u ON e.user_id = u.user_id
    JOIN tracks t ON e.track_id = t.track_id
    WHERE e.event_type IN ('play', 'daily_mix_play')
      AND e.event_time < u.signup_date::TIMESTAMP + INTERVAL '31 days'
    GROUP BY u.user_id, u.experiment_variant, week_num
)
SELECT
    experiment_variant,
    week_num,
    ROUND(AVG(unique_artists), 2) AS avg_unique_artists,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY unique_artists), 2) AS median_unique_artists
FROM weekly_artists
GROUP BY experiment_variant, week_num
ORDER BY week_num, experiment_variant;


-- -------------------------------------------------
-- 3E. CANNIBALIZATION CHECK: minutes by source
--     (Daily Mix vs all other surfaces)
--     Uses track duration (not session play time) because
--     source attribution is only available on events.
-- -------------------------------------------------
WITH source_minutes AS (
    SELECT
        u.user_id,
        u.experiment_variant,
        CASE
            WHEN e.source = 'daily_mix' THEN 'daily_mix'
            WHEN e.source = 'search'    THEN 'search'
            WHEN e.source = 'playlist'  THEN 'editorial_playlist'
            WHEN e.source = 'home'      THEN 'home_other'
            ELSE 'other'
        END AS surface,
        SUM(t.duration_ms) / 60000.0 AS listening_min
    FROM events e
    JOIN users u ON e.user_id = u.user_id
    JOIN tracks t ON e.track_id = t.track_id
    WHERE e.event_type IN ('play', 'daily_mix_play')
      AND e.event_time < u.signup_date::TIMESTAMP + INTERVAL '31 days'
    GROUP BY u.user_id, u.experiment_variant, surface
)
SELECT
    experiment_variant,
    surface,
    COUNT(DISTINCT user_id) AS users,
    ROUND(AVG(listening_min), 2) AS avg_min_per_user,
    ROUND(SUM(listening_min), 2) AS total_min
FROM source_minutes
GROUP BY experiment_variant, surface
ORDER BY experiment_variant, surface;


-- -------------------------------------------------
-- 3F. D30 RETENTION BY VARIANT, SEGMENTED
--     by platform & country
-- -------------------------------------------------
WITH d30_activity AS (
    SELECT DISTINCT e.user_id
    FROM events e
    JOIN users u ON e.user_id = u.user_id
    WHERE e.event_time::DATE = u.signup_date + 30
      AND e.event_type IN ('play', 'app_open', 'daily_mix_play')
)
SELECT
    u.experiment_variant,
    u.platform,
    u.country,
    COUNT(DISTINCT u.user_id) AS cohort_size,
    COUNT(DISTINCT d30.user_id) AS retained,
    ROUND(100.0 * COUNT(DISTINCT d30.user_id)
        / NULLIF(COUNT(DISTINCT u.user_id), 0), 2) AS d30_retention_pct
FROM users u
LEFT JOIN d30_activity d30 ON u.user_id = d30.user_id
GROUP BY u.experiment_variant, u.platform, u.country
ORDER BY u.experiment_variant, u.platform, u.country;