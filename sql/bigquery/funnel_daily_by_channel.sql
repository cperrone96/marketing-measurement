/* Public Google Analytics sample only. Grain: event date + user acquisition source/medium.
No user, session, or transaction identifier is returned. */
WITH session_events AS (
  SELECT
    PARSE_DATE('%Y%m%d', event_date) AS event_date,
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id')
      AS ga_session_id,
    ANY_VALUE(traffic_source.source) AS source,
    ANY_VALUE(traffic_source.medium) AS medium,
    MAX(event_name = 'page_view') AS has_page_view,
    MAX(event_name = 'user_engagement') AS has_engagement,
    MAX(event_name = 'add_to_cart') AS has_add_to_cart,
    MAX(event_name = 'begin_checkout') AS has_begin_checkout,
    MAX(event_name = 'purchase') AS has_purchase
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
  GROUP BY event_date, user_pseudo_id, ga_session_id
), hierarchical_sessions AS (
  SELECT
    event_date,
    COALESCE(source, '(not set)') AS source,
    COALESCE(medium, '(not set)') AS medium,
    has_page_view,
    has_page_view AND has_engagement AS is_engaged,
    has_page_view AND has_engagement AND has_add_to_cart AS has_add_to_cart,
    has_page_view AND has_engagement AND has_add_to_cart AND has_begin_checkout
      AS has_begin_checkout,
    has_page_view AND has_engagement AND has_add_to_cart AND has_begin_checkout
      AND has_purchase AS has_purchase
  FROM session_events
  WHERE ga_session_id IS NOT NULL
)
SELECT
  event_date,
  source,
  medium,
  COUNT(*) AS measured_sessions,
  COUNTIF(has_page_view) AS views,
  COUNTIF(is_engaged) AS engaged_sessions,
  COUNTIF(has_add_to_cart) AS add_to_carts,
  COUNTIF(has_begin_checkout) AS checkouts,
  COUNTIF(has_purchase) AS purchases
FROM hierarchical_sessions
GROUP BY event_date, source, medium
ORDER BY event_date, measured_sessions DESC;
