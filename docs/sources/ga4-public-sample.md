# GA4 public sample source boundary

The intended public source is `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`.
Its documented coverage for this project is **2020-11-01 through 2021-01-31**.

No BigQuery data was downloaded for this repository task. The ingestion boundary reads
locally supplied JSON or NDJSON exports shaped as nested GA4 event rows, so it neither
requires Google credentials nor treats a local fixture as a public-data snapshot.

## Export-query provenance

When retrieval is authorized, the expected export query must constrain table suffixes
to the documented coverage:

```sql
SELECT *
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
```

The manifest records retrieval status separately from fixture metadata. Its fixture
checksum covers only `data/fixtures/ga4_schema_fixture.ndjson`, a small deterministic
synthetic schema test fixture. It is never an observed Google data extract, snapshot,
or checksum of the public dataset.

## Validation policy

The contract normalizes event parameters, items, traffic source, device, geography,
ecommerce, and privacy fields. It preserves missing values rather than defaulting them
to zero, and quarantines invalid timestamps, events outside coverage, malformed primary
identifiers, impossible item quantities, and negative ecommerce revenue. Each
quarantined row retains `source_row_id`, one deterministic primary `reason`, and all
detected `reasons`.
