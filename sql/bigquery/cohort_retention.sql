/* Public Google Analytics sample only. Grain: true user-first-touch cohort date +
UTC session-start activity date. Only users whose user_first_touch_timestamp falls
inside the source window and has a fully observable day seven are eligible. */
WITH events AS (
  SELECT
    user_pseudo_id,
    user_first_touch_timestamp,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id')
      AS ga_session_id,
    event_timestamp
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
), valid_sessions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    DATE(TIMESTAMP_MICROS(MIN(event_timestamp)), 'UTC') AS session_start_date
  FROM events
  WHERE ga_session_id IS NOT NULL
  GROUP BY user_pseudo_id, ga_session_id
), eligible_acquired_users AS (
  SELECT DISTINCT
    user_pseudo_id,
    DATE(TIMESTAMP_MICROS(user_first_touch_timestamp), 'UTC') AS cohort_date
  FROM events
  WHERE user_first_touch_timestamp >= UNIX_MICROS(TIMESTAMP('2020-11-01'))
    AND user_first_touch_timestamp < UNIX_MICROS(TIMESTAMP('2021-01-25'))
), cohort_sizes AS (
  SELECT cohort_date, COUNT(*) AS cohort_users
  FROM eligible_acquired_users
  GROUP BY cohort_date
)
SELECT
  eligible_acquired_users.cohort_date,
  valid_sessions.session_start_date AS activity_date,
  DATE_DIFF(valid_sessions.session_start_date, eligible_acquired_users.cohort_date, DAY)
    AS days_since_acquisition,
  cohort_sizes.cohort_users,
  COUNT(DISTINCT valid_sessions.user_pseudo_id) AS retained_users,
  COUNT(*) AS measured_sessions,
  'user_first_touch_timestamp within source window; day-7 complete' AS cohort_definition
FROM valid_sessions
JOIN eligible_acquired_users USING (user_pseudo_id)
JOIN cohort_sizes USING (cohort_date)
WHERE DATE_DIFF(valid_sessions.session_start_date, eligible_acquired_users.cohort_date, DAY)
  BETWEEN 0 AND 30
GROUP BY cohort_date, activity_date, days_since_acquisition, cohort_users, cohort_definition
ORDER BY cohort_date, activity_date;
