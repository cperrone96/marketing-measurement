/* Public Google Analytics sample only. Grain: UTC session-start date + first observed
event-scoped source/medium in the session. `traffic_source` is deliberately not used:
it is first-user acquisition, not a session touchpoint. No identifiers are returned. */
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id')
      AS ga_session_id,
    event_timestamp,
    MAX(event_name = 'page_view') AS has_page_view,
    MAX(event_name = 'user_engagement') AS has_engagement,
    MAX(event_name = 'add_to_cart') AS has_add_to_cart,
    MAX(event_name = 'begin_checkout') AS has_begin_checkout,
    MAX(event_name = 'purchase') AS has_purchase,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source')
      AS event_source,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium')
      AS event_medium
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
  GROUP BY user_pseudo_id, ga_session_id, event_timestamp, event_source, event_medium
), sessions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
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
    MAX(has_page_view) AS has_page_view,
    MAX(has_engagement) AS has_engagement,
    MAX(has_add_to_cart) AS has_add_to_cart,
    MAX(has_begin_checkout) AS has_begin_checkout,
    MAX(has_purchase) AS has_purchase
  FROM events
  WHERE ga_session_id IS NOT NULL
  GROUP BY user_pseudo_id, ga_session_id
), hierarchical_sessions AS (
  SELECT
    session_start_date,
    COALESCE(first_event_channel.source, '(unattributed)') AS first_event_source,
    COALESCE(first_event_channel.medium, '(unattributed)') AS first_event_medium,
    has_page_view,
    has_page_view AND has_engagement AS is_engaged,
    has_page_view AND has_engagement AND has_add_to_cart AS has_add_to_cart,
    has_page_view AND has_engagement AND has_add_to_cart AND has_begin_checkout
      AS has_begin_checkout,
    has_page_view AND has_engagement AND has_add_to_cart AND has_begin_checkout
      AND has_purchase AS has_purchase
  FROM sessions
)
SELECT
  session_start_date,
  first_event_source,
  first_event_medium,
  COUNT(*) AS measured_sessions,
  COUNTIF(has_page_view) AS views,
  COUNTIF(is_engaged) AS engaged_sessions,
  COUNTIF(has_add_to_cart) AS add_to_carts,
  COUNTIF(has_begin_checkout) AS checkouts,
  COUNTIF(has_purchase) AS purchases
FROM hierarchical_sessions
GROUP BY session_start_date, first_event_source, first_event_medium
ORDER BY session_start_date, measured_sessions DESC;
