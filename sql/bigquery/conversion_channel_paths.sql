/* Public Google Analytics sample only. Grain: compact channel path + converted purchase count.
User, session, transaction, and hashed identifiers are used only inside the query
and are removed before this output is materialized. */
WITH event_sessions AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id')
      AS ga_session_id,
    MIN(event_timestamp) AS session_started_at,
    ARRAY_AGG(
      STRUCT(
        COALESCE(traffic_source.source, '(not set)') AS source,
        COALESCE(traffic_source.medium, '(not set)') AS medium
      )
      ORDER BY event_timestamp
      LIMIT 1
    )[OFFSET(0)] AS first_channel,
    MAX(event_name = 'purchase') AS has_purchase
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
  GROUP BY user_pseudo_id, ga_session_id
), conversion_sessions AS (
  SELECT user_pseudo_id, ga_session_id, session_started_at
  FROM event_sessions
  WHERE ga_session_id IS NOT NULL AND has_purchase
), conversion_paths AS (
  SELECT
    conversions.user_pseudo_id,
    conversions.ga_session_id,
    STRING_AGG(
      CONCAT(touches.first_channel.source, ' / ', touches.first_channel.medium),
      ' > ' ORDER BY touches.session_started_at, touches.ga_session_id
    ) AS channel_path
  FROM conversion_sessions AS conversions
  JOIN event_sessions AS touches
    ON touches.user_pseudo_id = conversions.user_pseudo_id
    AND touches.ga_session_id IS NOT NULL
    AND touches.session_started_at <= conversions.session_started_at
    AND touches.session_started_at >= conversions.session_started_at - 30 * 24 * 60 * 60 * 1000000
  GROUP BY conversions.user_pseudo_id, conversions.ga_session_id
)
SELECT
  channel_path,
  COUNT(*) AS converted_sessions
FROM conversion_paths
GROUP BY channel_path
ORDER BY converted_sessions DESC, channel_path;
