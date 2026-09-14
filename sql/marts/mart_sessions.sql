-- Grain: one measured user_pseudo_id + non-null ga_session_id pair.  Events with
-- a null ga_session_id remain available in staging as unmeasured and are excluded
-- here, so a user + null group can never masquerade as a measured session.
CREATE OR REPLACE VIEW analytics.mart_sessions AS
WITH event_level_records AS (
    -- Collapse an event-item spine back to one event before session metrics so a
    -- multi-item purchase cannot overstate event counts or purchase revenue.
    SELECT
        staged_events.*,
        ROW_NUMBER() OVER (
            PARTITION BY
                user_pseudo_id,
                event_timestamp,
                event_name,
                ga_session_id,
                transaction_id
            ORDER BY source_row_id DESC, item_index
        ) AS event_item_rank
    FROM staging.stg_ga4_events AS staged_events
), ordered_events AS (
    SELECT
        event_level_records.*,
        ROW_NUMBER() OVER (
            PARTITION BY user_pseudo_id, ga_session_id
            ORDER BY event_timestamp, source_row_id
        ) AS event_rank
    FROM event_level_records
    WHERE event_item_rank = 1
        AND ga_session_id IS NOT NULL
), raw_session_rollup AS (
    SELECT
        user_pseudo_id,
        ga_session_id,
        MIN(event_timestamp) AS session_started_event_timestamp,
        MIN(event_date) AS session_date,
        MAX(CASE WHEN event_rank = 1 THEN page_location END) AS landing_page,
        MAX(CASE WHEN event_rank = 1 THEN traffic_source_source END) AS traffic_source_source,
        MAX(CASE WHEN event_rank = 1 THEN traffic_source_medium END) AS traffic_source_medium,
        MAX(CASE WHEN event_rank = 1 THEN traffic_source_campaign END) AS traffic_source_campaign,
        MAX(CASE WHEN event_rank = 1 THEN device_category END) AS device_category,
        MAX(CASE WHEN event_rank = 1 THEN geo_country END) AS geo_country,
        MAX(CASE WHEN event_rank = 1 THEN privacy_info_analytics_storage END)
            AS privacy_info_analytics_storage,
        COUNT(*) AS event_count,
        SUM(CASE WHEN event_name = 'page_view' THEN 1 ELSE 0 END) AS page_views,
        MAX(CASE WHEN event_name = 'page_view' THEN 1 ELSE 0 END) AS raw_has_page_view,
        MAX(
            CASE
                WHEN event_name = 'user_engagement' OR engagement_time_msec > 0 THEN 1
                ELSE 0
            END
        ) AS raw_is_engaged,
        SUM(CASE WHEN event_name = 'add_to_cart' THEN 1 ELSE 0 END) AS add_to_cart_events,
        MAX(CASE WHEN event_name = 'add_to_cart' THEN 1 ELSE 0 END)
            AS raw_has_add_to_cart,
        SUM(CASE WHEN event_name = 'begin_checkout' THEN 1 ELSE 0 END) AS checkout_events,
        MAX(CASE WHEN event_name = 'begin_checkout' THEN 1 ELSE 0 END)
            AS raw_has_begin_checkout,
        SUM(CASE WHEN event_name = 'purchase' THEN 1 ELSE 0 END) AS purchase_events,
        MAX(CASE WHEN event_name = 'purchase' THEN 1 ELSE 0 END) AS raw_has_purchase,
        SUM(purchase_revenue) AS revenue
    FROM ordered_events
    GROUP BY user_pseudo_id, ga_session_id
)
SELECT
    raw_session_rollup.*,
    raw_has_page_view AS has_page_view,
    CASE
        WHEN raw_has_page_view = 1 AND raw_is_engaged = 1 THEN 1
        ELSE 0
    END AS is_engaged,
    CASE
        WHEN raw_has_page_view = 1
            AND raw_is_engaged = 1
            AND raw_has_add_to_cart = 1 THEN 1
        ELSE 0
    END AS has_add_to_cart,
    CASE
        WHEN raw_has_page_view = 1
            AND raw_is_engaged = 1
            AND raw_has_add_to_cart = 1
            AND raw_has_begin_checkout = 1 THEN 1
        ELSE 0
    END AS has_begin_checkout,
    CASE
        WHEN raw_has_page_view = 1
            AND raw_is_engaged = 1
            AND raw_has_add_to_cart = 1
            AND raw_has_begin_checkout = 1
            AND raw_has_purchase = 1 THEN 1
        ELSE 0
    END AS has_purchase
FROM raw_session_rollup;
