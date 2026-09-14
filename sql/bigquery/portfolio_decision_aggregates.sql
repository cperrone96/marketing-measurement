/* Public Google Analytics sample only. Aggregate decision-support rows with no
   user, session, event, or transaction identifiers in the output. */
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id')
      AS ga_session_id,
    event_timestamp,
    event_name,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location')
      AS page_location,
    device.category AS device_category,
    ecommerce.purchase_revenue AS purchase_revenue
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
), sessions AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    ARRAY_AGG(page_location IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)]
      AS landing_page,
    ARRAY_AGG(device_category IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)]
      AS device_category,
    LOGICAL_OR(event_name = 'page_view') AS viewed,
    LOGICAL_OR(event_name = 'user_engagement') AS engaged,
    LOGICAL_OR(event_name = 'add_to_cart') AS carted,
    LOGICAL_OR(event_name = 'begin_checkout') AS checked_out,
    LOGICAL_OR(event_name = 'purchase') AS purchased,
    SUM(COALESCE(purchase_revenue, 0)) AS revenue
  FROM events
  WHERE ga_session_id IS NOT NULL
  GROUP BY user_pseudo_id, ga_session_id
), session_dimensions AS (
  SELECT
    'landing_page' AS analysis,
    COALESCE(REGEXP_EXTRACT(landing_page, r'https?://[^/]+(/[^?#]*)'), '(unknown)')
      AS dimension,
    COUNTIF(viewed) AS sessions,
    COUNTIF(viewed AND engaged) AS engaged_sessions,
    COUNTIF(viewed AND engaged AND carted AND checked_out AND purchased) AS purchases,
    ROUND(SUM(revenue), 2) AS revenue
  FROM sessions
  GROUP BY 2
  UNION ALL
  SELECT
    'device',
    COALESCE(device_category, '(unknown)'),
    COUNTIF(viewed),
    COUNTIF(viewed AND engaged),
    COUNTIF(viewed AND engaged AND carted AND checked_out AND purchased),
    ROUND(SUM(revenue), 2)
  FROM sessions
  GROUP BY 2
  UNION ALL
  SELECT
    'high_value_journey',
    CONCAT(
      IF(viewed, 'view', 'no_view'), ' > ',
      IF(engaged, 'engaged', 'not_engaged'), ' > ',
      IF(carted, 'cart', 'no_cart'), ' > ',
      IF(checked_out, 'checkout', 'no_checkout'), ' > ',
      IF(purchased, 'purchase', 'no_purchase')
    ),
    COUNT(*),
    COUNTIF(engaged),
    COUNTIF(purchased),
    ROUND(SUM(revenue), 2)
  FROM sessions
  GROUP BY 2
), ranked_session_dimensions AS (
  SELECT *
  FROM session_dimensions
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY analysis ORDER BY
      CASE WHEN analysis = 'high_value_journey' THEN revenue ELSE sessions END DESC,
      dimension
  ) <= 20
), product_rows AS (
  SELECT
    COALESCE(item.item_name, item.item_id, '(unknown product)') AS dimension,
    COUNTIF(event_name = 'view_item') AS product_views,
    COUNTIF(event_name = 'add_to_cart') AS add_to_carts,
    COUNTIF(event_name = 'purchase') AS purchases,
    SUM(IF(event_name = 'purchase', COALESCE(item.quantity, 0), 0)) AS units,
    ROUND(SUM(IF(event_name = 'purchase', COALESCE(item.item_revenue, 0), 0)), 2)
      AS revenue
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`,
    UNNEST(items) AS item
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
  GROUP BY dimension
  QUALIFY ROW_NUMBER() OVER (ORDER BY revenue DESC, dimension) <= 20
)
SELECT
  analysis,
  dimension,
  sessions,
  engaged_sessions,
  CAST(NULL AS INT64) AS product_views,
  CAST(NULL AS INT64) AS add_to_carts,
  purchases,
  CAST(NULL AS INT64) AS units,
  revenue,
  SAFE_DIVIDE(purchases, sessions) AS conversion_rate
FROM ranked_session_dimensions
UNION ALL
SELECT
  'product',
  dimension,
  CAST(NULL AS INT64),
  CAST(NULL AS INT64),
  product_views,
  add_to_carts,
  purchases,
  CAST(units AS INT64),
  revenue,
  SAFE_DIVIDE(purchases, product_views)
FROM product_rows
ORDER BY analysis, revenue DESC, dimension;
