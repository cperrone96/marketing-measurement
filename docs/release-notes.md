# Release notes

## v0.2.0 (unreleased): analysis review

- Attribution: simplified GA4 default channel grouping and a self-referral
  sensitivity. 1,381 of 3,230 converted sessions include a
  `*.googlemerchandisestore.com / referral` touch, which takes 980 last-touch
  credits as observed; with those touches removed the four rules largely agree.
  `time_decay` is now documented as position decay (one-touch half-life).
- Funnel: a coverage check shows the strict same-session funnel keeps 2,847 of at
  least 4,844 purchase sessions; 1,997 purchases have no same-session add-to-cart.
- Model: a returning-visitor rule baseline and 95% cluster-bootstrap intervals.
  PR-AUC 0.041429 (0.027371 to 0.067842) against 0.024040 for the rule; the
  existing model metrics are unchanged. The model card records that 88.14% of
  sessions have an unattributed source because of the extraction query.
- Reproducibility: pinned `requirements.txt`, committed notebook outputs, `make
  notebooks` and `make figures`, and a README figure.

## v0.1.0 — 2026-09-11

First portfolio-ready release of the Marketing Measurement Decision Studio.

### Included

- Validated public observed GA4 aggregates for 2020-11-01 through 2021-01-31,
  bounded retrieval provenance, analytical SQL, and traceable funnel, landing-page,
  device, product/revenue, and high-value journey evidence.
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

### Final review hardening

- Preserved exact decimal/integer-cent budgets through API serialization, including
  values above binary floating-point's exact-integer boundary, with finite magnitude
  and precision bounds plus structured 422 failures.
- Aligned experiment power to the marginal all-randomized ITT outcome implied by
  consent, match, delivery, and exposure; the gate is now 4,209 per arm.
- Removed the undisclosed source filter so KPI and funnel views share canonical totals.
- Bound KPI and model responses to the actual findings and model-evaluation artifacts.
- Stripped tracked notebook outputs and require fresh, source-matching executed copies.
- Aligned local marts to paired event-scoped acquisition fields and corrected product
  views/rates to use `view_item`.
- Bound local PostgreSQL to `127.0.0.1` with a local-only password default.

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

### Reproduction evidence

The documented clean setup exports the current committed local `HEAD`, creates a Python
3.12 virtual environment, installs the `dev` extra, then runs `make release-gate`.
That gate verifies checksums before execution, runs public observed and synthetic
fixture tests without cloud access, removes copied generated outputs in a temporary
source copy, requires the notebooks to recreate byte-identical evidence, and verifies
source checksums again afterward.

### Known limitations

The source is historic, obfuscated, sampled, and ecommerce-specific. Attribution and
prediction are non-causal. The synthetic experiment is underpowered and declares no
winner. Dependency ranges are bounded but not locked. No external deployment, live
integration, or customer-data evaluation is included.
