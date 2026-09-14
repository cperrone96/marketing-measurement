/* Public Google Analytics sample only. Grain: eligible conversion date + compact
event-scoped session-channel path. `traffic_source` is deliberately not used because
it is first-user acquisition. Identifiers exist only inside the query and are removed
before output. Every eligible conversion has a full 30-day source-window lookback. */
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id')
      AS ga_session_id,
    event_timestamp,
    event_name,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source')
      AS event_source,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium')
      AS event_medium
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
), sessions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    MIN(event_timestamp) AS session_started_at,
    DATE(TIMESTAMP_MICROS(MIN(event_timestamp)), 'UTC') AS session_start_date,
    ARRAY_AGG(
      IF(
        event_source IS NOT NULL AND event_medium IS NOT NULL,
        STRUCT(event_source AS source, event_medium AS medium),
        NULL
      ) IGNORE NULLS
      ORDER BY event_timestamp
      LIMIT 1
    )[SAFE_OFFSET(0)] AS first_event_channel,
    MAX(event_name = 'purchase') AS has_purchase
  FROM events
  WHERE ga_session_id IS NOT NULL
  GROUP BY user_pseudo_id, ga_session_id
), eligible_conversions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    session_started_at,
    session_start_date AS conversion_date,
    DATE_SUB(session_start_date, INTERVAL 30 DAY) AS lookback_start_date
  FROM sessions
  WHERE has_purchase
    AND session_start_date >= DATE '2020-12-01'
), conversion_paths AS (
  SELECT
    conversions.user_pseudo_id,
    conversions.ga_session_id,
    conversions.conversion_date,
    conversions.lookback_start_date,
    STRING_AGG(
      CONCAT(
        COALESCE(touches.first_event_channel.source, '(unattributed)'),
        ' / ',
        COALESCE(touches.first_event_channel.medium, '(unattributed)')
      ),
      ' > ' ORDER BY touches.session_started_at, touches.ga_session_id
    ) AS channel_path
  FROM eligible_conversions AS conversions
  JOIN sessions AS touches
    ON touches.user_pseudo_id = conversions.user_pseudo_id
    AND touches.session_started_at <= conversions.session_started_at
    AND touches.session_started_at >= conversions.session_started_at - 30 * 24 * 60 * 60 * 1000000
  GROUP BY
    conversions.user_pseudo_id,
    conversions.ga_session_id,
    conversions.conversion_date,
    conversions.lookback_start_date
)
SELECT
  conversion_date,
  lookback_start_date,
  TRUE AS eligible_30_day_lookback,
  channel_path,
  COUNT(*) AS converted_sessions
FROM conversion_paths
GROUP BY conversion_date, lookback_start_date, eligible_30_day_lookback, channel_path
ORDER BY conversion_date, converted_sessions DESC, channel_path;
