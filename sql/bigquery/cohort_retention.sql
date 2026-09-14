/* Public Google Analytics sample only. Grain: acquisition date + activity date.
No user, session, or transaction identifier is returned. */
WITH measured_sessions AS (
  SELECT DISTINCT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id')
      AS ga_session_id,
    PARSE_DATE('%Y%m%d', event_date) AS session_date
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
), valid_sessions AS (
  SELECT user_pseudo_id, ga_session_id, session_date
  FROM measured_sessions
  WHERE ga_session_id IS NOT NULL
), user_cohorts AS (
  SELECT user_pseudo_id, MIN(session_date) AS cohort_date
  FROM valid_sessions
  GROUP BY user_pseudo_id
), cohort_sizes AS (
  SELECT cohort_date, COUNT(*) AS cohort_users
  FROM user_cohorts
  GROUP BY cohort_date
)
SELECT
  user_cohorts.cohort_date,
  valid_sessions.session_date AS activity_date,
  DATE_DIFF(valid_sessions.session_date, user_cohorts.cohort_date, DAY)
    AS days_since_acquisition,
  cohort_sizes.cohort_users,
  COUNT(DISTINCT valid_sessions.user_pseudo_id) AS retained_users,
  COUNT(DISTINCT CONCAT(
    valid_sessions.user_pseudo_id, ':', CAST(valid_sessions.ga_session_id AS STRING)
  )) AS measured_sessions
FROM valid_sessions
JOIN user_cohorts USING (user_pseudo_id)
JOIN cohort_sizes USING (cohort_date)
WHERE DATE_DIFF(valid_sessions.session_date, user_cohorts.cohort_date, DAY) BETWEEN 0 AND 30
GROUP BY cohort_date, activity_date, days_since_acquisition, cohort_users
ORDER BY cohort_date, activity_date;
