# Data lineage

Public observed and synthetic evidence have separate source, transformation, storage,
and presentation paths. The API combines them only at the navigation level; it does
not combine their records or support a mixed-evidence performance claim.

## Public observed lane

| Stage | Artifact | Grain / contract | Output / consumer |
| --- | --- | --- | --- |
| Source | `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*` | Obfuscated GA4 events, 2020-11-01 through 2021-01-31 | Read only by bounded queries in `sql/bigquery/` |
| Retrieval | `scripts/retrieve_public_aggregates.py`, `scripts/retrieve_public_conversion_model.py` | Dry run first; explicit billing project; 4 GB cap per query | Query/result hashes and job metadata in `data/observed/ga4_public_sample/retrieval_metadata.json` |
| Compact evidence | `data/observed/ga4_public_sample/*.json` | Aggregate funnel days/channels, true-first-touch cohorts, conversion paths, parameter availability | Public findings notebook and artifact repository |
| Decision aggregates | `sql/bigquery/portfolio_decision_aggregates.sql` | Aggregate-only landing page, device, product/revenue, and stage-pattern rows | Typed KPI analysis sections and acquisition/journey dashboard records |
| Model evidence | `conversion_model_sessions.json.gz` | One row per measured session; 10% deterministic user-level sample; no raw identifier | Conversion notebook, reviewed evaluation JSON, and model card |
| Analysis | `src/marketing_measurement/analysis/`, `src/marketing_measurement/modeling/` | Tested descriptive rates, conserved attribution credit, group-disjoint model evaluation | `findings_summary.json`, model card, API service |
| Interface | `api/` → `dashboard/` | Typed v1 responses; bounded dates/pagination; artifact hash and limitations | Five decision views and accessible table alternatives |

The public-observed funnel session key is `user_pseudo_id + ga_session_id` inside the
source query; those identifiers are not present in the committed aggregate outputs.
Session channel is the first paired event-scoped source/medium. Cohorts use
`user_first_touch_timestamp`; eligible attribution conversions have a complete 30-day
source-window lookback.

## Synthetic lane

| Stage | Artifact | Grain / contract | Output / consumer |
| --- | --- | --- | --- |
| Fixture | `data/fixtures/ga4_schema_fixture.ndjson` | Small synthetic schema rows | Ingestion, quarantine, and SQL reconciliation tests only |
| Generator | `src/marketing_measurement/simulation/integration.py` | 200 deterministic pseudonymous demonstration rows by default; seed 20260910 | Audience/integration measures and synthetic A/B analysis |
| Experiment | `src/marketing_measurement/analysis/experiments.py` + `src/marketing_measurement/simulation/integration.py` | Marginal intent-to-treat scenario over the deterministic integration population | Scenario response with a canonical two-source manifest hash |
| Scenario | `src/marketing_measurement/analysis/budget.py` | User-provided whole-cent assumptions constrained by minima/capacities | Synthetic budget API response with sensitivity |
| Interface | `/api/v1/audiences/quality`, `/integrations/health`, `/scenarios/budget` | `evidence_type=synthetic`, generator hash, limitations | Hatched synthetic dashboard lane |

Synthetic subjects use reserved `.example` domains and cannot be joined to the public
observed lane. Scenario outputs are demonstrations, not forecasts or actual spend.
The scenario page renders experiment provenance beside experiment content and budget
provenance beside budget content; neither digest is used as a substitute for the
other.

## Controls

- The manifest and `docs/release-checksums.sha256` pin source-query and evidence bytes.
- Data-quality contracts quarantine invalid time, identifiers, quantity, and revenue.
- SQL tests reconcile event/session/product grains in DuckDB and optionally PostgreSQL.
- Model inputs use an exact pre-outcome allowlist; split and threshold selection exclude
  the final holdout.
- CI is offline after dependency installation and cannot retrieve public cloud data.
