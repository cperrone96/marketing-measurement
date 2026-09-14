-- Grain: one item_id + item_name + item_category combination from validated,
-- deduplicated event-item records.  Quantity and revenue remain null when the
-- source did not measure them; no missing source metric is converted to zero.
CREATE OR REPLACE VIEW analytics.mart_products AS
SELECT
    item_id,
    item_name,
    item_category,
    SUM(item_quantity) AS units,
    SUM(item_revenue) AS revenue,
    SUM(CASE WHEN event_name = 'page_view' THEN 1 ELSE 0 END) AS product_views,
    SUM(CASE WHEN event_name = 'add_to_cart' THEN 1 ELSE 0 END) AS add_to_carts,
    SUM(CASE WHEN event_name = 'purchase' THEN 1 ELSE 0 END) AS purchases,
    SUM(CASE WHEN event_name = 'purchase' THEN 1 ELSE 0 END) AS purchase_rate_numerator,
    SUM(CASE WHEN event_name IN ('page_view', 'add_to_cart', 'purchase') THEN 1 ELSE 0 END)
        AS purchase_rate_denominator,
    CAST(SUM(CASE WHEN event_name = 'purchase' THEN 1 ELSE 0 END) AS DOUBLE PRECISION)
        / NULLIF(
            SUM(CASE WHEN event_name IN ('page_view', 'add_to_cart', 'purchase') THEN 1 ELSE 0 END),
            0
        ) AS purchase_rate
FROM staging.stg_ga4_events
WHERE item_id IS NOT NULL
GROUP BY item_id, item_name, item_category;
