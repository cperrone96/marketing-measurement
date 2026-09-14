# Release notes

## v0.1.0 — 2026-09-11

First portfolio-ready release of the Marketing Measurement Decision Studio.

### Included

- Validated public observed GA4 aggregates for 2020-11-01 through 2021-01-31,
  bounded retrieval provenance, analytical SQL, and three traceable descriptive findings.
- One identifier-free public-sample conversion model with leakage controls, group-aware
  evaluation, baseline/calibration evidence, and a capacity-linked threshold.
- Deterministic synthetic integration health, underpowered A/B demonstration, and
  whole-cent constrained budget sensitivity. These are not observed performance claims.
- Ten typed FastAPI v1 routes with bounded inputs, safe structured errors, evidence
  metadata, and fixed-format monetary outputs.
- Five-view Plotly Dash decision interface with explicit evidence lanes, chart table
  alternatives, responsive behavior, visible keyboard focus, and reduced motion.
- Offline CI, complete UAT/lineage/metric/risk documentation, executable notebooks,
  and SHA-256 release verification.

### Verified public findings

- 250,206 of 333,683 viewed sessions were engaged; the measured engaged-to-cart rate
  was 14,919 / 250,206 (5.96%). Decision: investigate and test that transition first.
- 1,611 of 238,644 users across 85 complete true-first-touch cohorts returned on day
  seven (0.68%). Decision: validate lifecycle hypotheses on current governed data.
- Four descriptive attribution methods each reconciled to 3,230 eligible converted
  sessions with a complete 30-day lookback. This is descriptive attribution; not causal.
- On 7,245 untouched held-out sessions, logistic regression achieved 0.041429 PR-AUC
  versus a 0.013941 no-skill baseline. This supports an educational review-queue
  workflow, not deployment or a claim of campaign lift.

### Résumé-ready project bullet (pending evidence-ledger acceptance)

> Built an end-to-end marketing measurement decision product from Google's public,
> obfuscated GA4 ecommerce sample (Nov 2020–Jan 2021), using BigQuery SQL, tested
> Python analytics, leakage-safe grouped machine learning, FastAPI, and Plotly Dash;
> quantified 250,206 / 333,683 viewed sessions as engaged (74.98%) and translated
> funnel, cohort, and descriptive-attribution evidence into testable journey priorities,
> while keeping synthetic integration and budget scenarios separate from observed results.

### Reproduction evidence

The documented clean setup exports the current committed local `HEAD`, creates a Python
3.12 virtual environment, installs the `dev` extra, then runs `make release-gate`.
That gate verifies checksums before execution, runs public observed and synthetic
fixture tests without cloud access, executes both notebooks in a temporary source copy,
byte-compares generated evidence, and verifies checksums again afterward.

### Known limitations

The source is historic, obfuscated, sampled, and ecommerce-specific. Attribution and
prediction are non-causal. The synthetic experiment is underpowered and declares no
winner. Dependency ranges are bounded but not locked. No external deployment, live
integration, or customer-data evaluation is included.
