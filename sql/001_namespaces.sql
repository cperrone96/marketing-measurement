-- Namespace contract: raw_public stores validated source-shaped records, staging
-- contains canonical transformations, and analytics contains consumer-facing marts.
-- Quarantined records stay in raw_public.ga4_events_quarantine and are never read
-- by these models.
CREATE SCHEMA IF NOT EXISTS raw_public;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;
