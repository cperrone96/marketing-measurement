# GA4 public sample source boundary

The intended public source is `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`.
Its documented coverage for this project is **2020-11-01 through 2021-01-31**.

Observed public outputs were retrieved with the documented billing project and a
4 GB cap per query. The aggregate outputs are compact JSON files. The conversion
model uses a separate 10% deterministic, identifier-free session sample compressed as
`data/observed/ga4_public_sample/conversion_model_sessions.json.gz`; it contains one
row per session but no raw user, session, transaction, or event identifier.

## Export-query provenance

Every retrieval query constrains table suffixes to the documented coverage and uses a
fully qualified public table. The model query is
`sql/bigquery/conversion_model_sessions.sql`; its retrieval script dry-runs before it
executes and records separate query and result hashes. A generic bounded example is:

```sql
SELECT *
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
```

The manifest records observed retrieval status separately from fixture metadata. Its
fixture checksum covers only `data/fixtures/ga4_schema_fixture.ndjson`, a small
deterministic synthetic schema test fixture. The fixture is never used to train,
evaluate, or infer distributions for the conversion model.

## Validation policy

The contract normalizes event parameters, items, traffic source, device, geography,
ecommerce, and privacy fields. It preserves missing values rather than defaulting them
to zero, and quarantines invalid timestamps, events outside coverage, malformed primary
identifiers, impossible item quantities, and negative ecommerce revenue. Each
quarantined row retains `source_row_id`, one deterministic primary `reason`, and all
detected `reasons`.
