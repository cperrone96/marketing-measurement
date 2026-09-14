-- Grain: one acquisition cohort date + activity date pair.  cohort_users is the
-- cohort-size denominator and retained_users is its activity-date numerator.
-- Dates derive directly from UTC epoch days, avoiding an execution-session time
-- zone conversion.  Revenue remains null when no measured revenue exists.
CREATE OR REPLACE VIEW analytics.mart_cohorts AS
WITH user_cohorts AS (
    SELECT
        user_pseudo_id,
        MIN(session_date) AS cohort_date
    FROM analytics.mart_sessions
    GROUP BY user_pseudo_id
), cohort_sizes AS (
    SELECT
        cohort_date,
        COUNT(*) AS cohort_users
    FROM user_cohorts
    GROUP BY cohort_date
), cohort_activity AS (
    SELECT
        user_cohorts.cohort_date,
        sessions.session_date AS activity_date,
        COUNT(DISTINCT sessions.user_pseudo_id) AS retained_users,
        COUNT(*) AS sessions,
        SUM(sessions.has_purchase) AS purchasers,
        SUM(sessions.revenue) AS revenue
    FROM analytics.mart_sessions AS sessions
    INNER JOIN user_cohorts
        ON sessions.user_pseudo_id = user_cohorts.user_pseudo_id
    GROUP BY user_cohorts.cohort_date, sessions.session_date
)
SELECT
    cohort_activity.cohort_date,
    cohort_activity.activity_date,
    cohort_activity.activity_date - cohort_activity.cohort_date AS days_since_acquisition,
    cohort_sizes.cohort_users,
    cohort_activity.retained_users,
    cohort_sizes.cohort_users AS retention_rate_denominator,
    cohort_activity.retained_users AS retention_rate_numerator,
    CAST(cohort_activity.retained_users AS DOUBLE PRECISION)
        / NULLIF(cohort_sizes.cohort_users, 0) AS retention_rate,
    cohort_activity.sessions,
    cohort_activity.purchasers,
    cohort_activity.revenue
FROM cohort_activity
INNER JOIN cohort_sizes
    ON cohort_activity.cohort_date = cohort_sizes.cohort_date;
