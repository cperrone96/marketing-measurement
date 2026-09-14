/* Public Google Analytics sample only. Grain: one measured session.
   The output deliberately excludes raw user_pseudo_id, ga_session_id, event IDs,
   and transaction IDs. `user_group_bucket` is a non-unique deterministic bucket
   used only to keep a user's sessions on one split; collisions are expected. */
WITH sampled_events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id')
      AS ga_session_id,
    event_timestamp,
    event_name,
    device.category AS device_category,
    geo.country AS country,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_number')
      AS ga_session_number,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source')
      AS event_source,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium')
      AS event_medium,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'campaign')
      AS event_campaign
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
    /* Deterministic 10% user-level sample, without exporting a user identifier. */
    AND MOD(ABS(FARM_FINGERPRINT(user_pseudo_id)), 100) < 10
), sessions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    MIN(event_timestamp) AS session_start_timestamp,
    ARRAY_AGG(
      STRUCT(
        device_category,
        country,
        ga_session_number,
        event_source,
        event_medium,
        event_campaign
      )
      ORDER BY event_timestamp
      LIMIT 1
    )[SAFE_OFFSET(0)] AS start_context,
    LOGICAL_OR(event_name = 'purchase') AS converted
  FROM sampled_events
  WHERE ga_session_id IS NOT NULL
  GROUP BY user_pseudo_id, ga_session_id
)
SELECT
  DATE(TIMESTAMP_MICROS(session_start_timestamp), 'UTC') AS session_start_date,
  EXTRACT(HOUR FROM TIMESTAMP_MICROS(session_start_timestamp) AT TIME ZONE 'UTC')
    AS session_start_hour,
  EXTRACT(DAYOFWEEK FROM TIMESTAMP_MICROS(session_start_timestamp) AT TIME ZONE 'UTC') - 1
    AS session_start_day_of_week,
  COALESCE(start_context.device_category, '(unknown)') AS device_category,
  CASE
    WHEN start_context.country = 'United States' THEN 'United States'
    WHEN start_context.country IS NULL THEN '(unknown)'
    ELSE 'Other'
  END AS country_group,
  CASE
    WHEN start_context.ga_session_number = 1 THEN 'new'
    WHEN start_context.ga_session_number IS NULL THEN '(unknown)'
    ELSE 'returning'
  END AS new_returning_status,
  COALESCE(NULLIF(start_context.event_source, ''), '(unattributed)') AS session_source,
  COALESCE(NULLIF(start_context.event_medium, ''), '(unattributed)') AS session_medium,
  COALESCE(NULLIF(start_context.event_campaign, ''), '(none)') AS session_campaign,
  /* This is intentionally non-unique and is not a user identifier. */
  MOD(ABS(FARM_FINGERPRINT(user_pseudo_id)), 10000) AS user_group_bucket,
  converted
FROM sessions
ORDER BY session_start_date, user_group_bucket;
