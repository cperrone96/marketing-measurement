-- Grain: one validated, deduplicated GA4 event-item record.  The deduplication
-- key is user_pseudo_id, event_timestamp, event_name, ga_session_id,
-- transaction_id, and zero-based item_index; source_row_id descending selects
-- the latest received copy of an otherwise identical event.  item_index preserves
-- distinct items belonging to the same ecommerce event.  Event-level purchase
-- revenue is emitted only on item_index 0 (or a non-item event) to prevent an
-- exploded item spine from duplicating event-level revenue.  Input is only validated
-- raw_public.ga4_events; quarantined rows have no path into this model.
CREATE OR REPLACE VIEW staging.stg_ga4_events AS
WITH ranked_events AS (
    SELECT
        raw_events.*,
        ROW_NUMBER() OVER (
            PARTITION BY
                user_pseudo_id,
                event_timestamp,
                event_name,
                ga_session_id,
                transaction_id,
                item_index
            ORDER BY source_row_id DESC
        ) AS duplicate_rank
    FROM raw_public.ga4_events AS raw_events
)
SELECT
    source_row_id,
    event_timestamp,
    DATE '1970-01-01'
        + CAST(FLOOR(event_timestamp / 86400000000.0) AS INTEGER) AS event_date,
    event_name,
    user_pseudo_id,
    ga_session_id,
    page_location,
    page_title,
    traffic_source_source,
    traffic_source_medium,
    traffic_source_name AS traffic_source_campaign,
    device_category,
    geo_country,
    privacy_info_analytics_storage,
    engagement_time_msec,
    CASE
        WHEN item_index IS NULL OR item_index = 0 THEN purchase_revenue
        ELSE NULL
    END AS purchase_revenue,
    transaction_id,
    item_index,
    item_id,
    item_name,
    item_category,
    item_quantity,
    item_revenue
FROM ranked_events
WHERE duplicate_rank = 1;
