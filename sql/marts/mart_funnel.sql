-- Grain (mart_funnel_total): one row for the full validated, deduplicated input.
-- Grain (mart_funnel_landing_pages): one row per landing_page, including null for
-- unmeasured values.  Grain (mart_funnel_channels): one row per source + medium.
-- Grain (mart_funnel_campaigns): one row per source + medium + campaign.  Every
-- conversion rate retains its numerator and denominator; source nulls are never
-- changed to zero.
CREATE OR REPLACE VIEW analytics.mart_funnel_total AS
SELECT
    SUM(has_page_view) AS views,
    SUM(is_engaged) AS engaged_sessions,
    SUM(has_add_to_cart) AS add_to_carts,
    SUM(has_purchase) AS purchases,
    SUM(is_engaged) AS engaged_sessions_numerator,
    SUM(has_page_view) AS engaged_sessions_denominator,
    SUM(has_add_to_cart) AS add_to_carts_numerator,
    SUM(is_engaged) AS add_to_carts_denominator,
    SUM(has_purchase) AS purchases_numerator,
    SUM(has_add_to_cart) AS purchases_denominator,
    CAST(SUM(is_engaged) AS DOUBLE PRECISION) / NULLIF(SUM(has_page_view), 0)
        AS engagement_rate,
    CAST(SUM(has_add_to_cart) AS DOUBLE PRECISION) / NULLIF(SUM(is_engaged), 0)
        AS add_to_cart_rate,
    CAST(SUM(has_purchase) AS DOUBLE PRECISION) / NULLIF(SUM(has_add_to_cart), 0)
        AS purchase_rate,
    SUM(revenue) AS revenue
FROM analytics.mart_sessions;

-- Grain: one row for the full validated, deduplicated input; compatibility alias
-- for consumers expecting a generic funnel mart name.
CREATE OR REPLACE VIEW analytics.mart_funnel AS
SELECT *
FROM analytics.mart_funnel_total;

CREATE OR REPLACE VIEW analytics.mart_funnel_landing_pages AS
SELECT
    landing_page,
    SUM(has_page_view) AS views,
    SUM(is_engaged) AS engaged_sessions,
    SUM(has_add_to_cart) AS add_to_carts,
    SUM(has_purchase) AS purchases,
    SUM(is_engaged) AS engaged_sessions_numerator,
    SUM(has_page_view) AS engaged_sessions_denominator,
    SUM(has_add_to_cart) AS add_to_carts_numerator,
    SUM(is_engaged) AS add_to_carts_denominator,
    SUM(has_purchase) AS purchases_numerator,
    SUM(has_add_to_cart) AS purchases_denominator,
    CAST(SUM(is_engaged) AS DOUBLE PRECISION) / NULLIF(SUM(has_page_view), 0)
        AS engagement_rate,
    CAST(SUM(has_add_to_cart) AS DOUBLE PRECISION) / NULLIF(SUM(is_engaged), 0)
        AS add_to_cart_rate,
    CAST(SUM(has_purchase) AS DOUBLE PRECISION) / NULLIF(SUM(has_add_to_cart), 0)
        AS purchase_rate,
    SUM(revenue) AS revenue
FROM analytics.mart_sessions
GROUP BY landing_page;

CREATE OR REPLACE VIEW analytics.mart_funnel_channels AS
SELECT
    traffic_source_source,
    traffic_source_medium,
    SUM(has_page_view) AS views,
    SUM(is_engaged) AS engaged_sessions,
    SUM(has_add_to_cart) AS add_to_carts,
    SUM(has_purchase) AS purchases,
    SUM(is_engaged) AS engaged_sessions_numerator,
    SUM(has_page_view) AS engaged_sessions_denominator,
    SUM(has_add_to_cart) AS add_to_carts_numerator,
    SUM(is_engaged) AS add_to_carts_denominator,
    SUM(has_purchase) AS purchases_numerator,
    SUM(has_add_to_cart) AS purchases_denominator,
    CAST(SUM(is_engaged) AS DOUBLE PRECISION) / NULLIF(SUM(has_page_view), 0)
        AS engagement_rate,
    CAST(SUM(has_add_to_cart) AS DOUBLE PRECISION) / NULLIF(SUM(is_engaged), 0)
        AS add_to_cart_rate,
    CAST(SUM(has_purchase) AS DOUBLE PRECISION) / NULLIF(SUM(has_add_to_cart), 0)
        AS purchase_rate,
    SUM(revenue) AS revenue
FROM analytics.mart_sessions
GROUP BY traffic_source_source, traffic_source_medium;

CREATE OR REPLACE VIEW analytics.mart_funnel_campaigns AS
SELECT
    traffic_source_source,
    traffic_source_medium,
    traffic_source_campaign,
    SUM(has_page_view) AS views,
    SUM(is_engaged) AS engaged_sessions,
    SUM(has_add_to_cart) AS add_to_carts,
    SUM(has_purchase) AS purchases,
    SUM(is_engaged) AS engaged_sessions_numerator,
    SUM(has_page_view) AS engaged_sessions_denominator,
    SUM(has_add_to_cart) AS add_to_carts_numerator,
    SUM(is_engaged) AS add_to_carts_denominator,
    SUM(has_purchase) AS purchases_numerator,
    SUM(has_add_to_cart) AS purchases_denominator,
    CAST(SUM(is_engaged) AS DOUBLE PRECISION) / NULLIF(SUM(has_page_view), 0)
        AS engagement_rate,
    CAST(SUM(has_add_to_cart) AS DOUBLE PRECISION) / NULLIF(SUM(is_engaged), 0)
        AS add_to_cart_rate,
    CAST(SUM(has_purchase) AS DOUBLE PRECISION) / NULLIF(SUM(has_add_to_cart), 0)
        AS purchase_rate,
    SUM(revenue) AS revenue
FROM analytics.mart_sessions
GROUP BY traffic_source_source, traffic_source_medium, traffic_source_campaign;
