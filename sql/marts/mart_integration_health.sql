-- Synthetic-only integration-health mart. It never reads public-observed schemas.
CREATE SCHEMA IF NOT EXISTS synthetic;

CREATE OR REPLACE VIEW synthetic.mart_integration_health AS
WITH synthetic_records AS (
    SELECT *
    FROM synthetic.integration_delivery_records
    WHERE evidence_type = 'synthetic'
), metric_inputs AS (
    SELECT
        'consent_eligibility' AS metric,
        SUM(CASE WHEN consent_eligible THEN 1 ELSE 0 END) AS numerator,
        COUNT(*) AS denominator
    FROM synthetic_records
    UNION ALL
    SELECT
        'partner_match_rate',
        SUM(CASE WHEN consent_eligible AND partner_matched THEN 1 ELSE 0 END),
        SUM(CASE WHEN consent_eligible THEN 1 ELSE 0 END)
    FROM synthetic_records
    UNION ALL
    SELECT
        'delivery_success_rate',
        SUM(CASE WHEN consent_eligible AND partner_matched AND delivery_success THEN 1 ELSE 0 END),
        SUM(CASE WHEN consent_eligible AND partner_matched THEN 1 ELSE 0 END)
    FROM synthetic_records
    UNION ALL
    SELECT
        'rejection_rate',
        SUM(CASE WHEN rejection_reason IS NOT NULL THEN 1 ELSE 0 END),
        COUNT(*)
    FROM synthetic_records
    UNION ALL
    SELECT
        'freshness_sla_rate',
        SUM(CASE WHEN source_freshness_hours <= 24 THEN 1 ELSE 0 END),
        COUNT(*)
    FROM synthetic_records
    UNION ALL
    SELECT
        'latency_sla_rate',
        SUM(CASE WHEN delivery_success AND delivery_latency_minutes <= 60 THEN 1 ELSE 0 END),
        SUM(CASE WHEN delivery_success THEN 1 ELSE 0 END)
    FROM synthetic_records
    UNION ALL
    SELECT
        'activation_rate',
        SUM(CASE WHEN delivery_success AND exposure THEN 1 ELSE 0 END),
        SUM(CASE WHEN delivery_success THEN 1 ELSE 0 END)
    FROM synthetic_records
)
SELECT
    metric,
    numerator,
    denominator,
    CAST(numerator AS DOUBLE PRECISION) / NULLIF(denominator, 0) AS rate,
    'synthetic' AS evidence_type
FROM metric_inputs;
