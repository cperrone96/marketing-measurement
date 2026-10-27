# Release notes

## v0.3.0 (unreleased): corrected extraction and forward validation

- Model extract: acquisition source, medium and campaign now come from the landing
  `page_view` (before any purchase). The old query read the first event, which never
  carries them, leaving 88% of sessions `(unattributed)`; now 38.86%, the share of
  landing hits with no source in this export. Population: 33,553 sessions with a
  landing page view, all 466 purchase sessions kept.
- Engagement now uses GA4's `session_engaged` flag (string value; the integer 1 on
  `session_start`/`first_visit` marks every session and is ignored): 72.05% of viewed
  sessions, versus 74.98% for the old `user_engagement` proxy. Funnel and decision
  aggregates were re-queried.
- Model: forward-in-time validation (train Nov to Dec 2020, test Jan 2021), tuned L2
  logistic regression and histogram gradient boosting (replacing the random forest,
  whose class-balanced probabilities were badly calibrated), calibration
  diagnostics and permutation importance. Held-out PR-AUC 0.051064 and ROC-AUC
  0.811306, versus 0.025031 and 0.720098 for the returning-visitor rule.
- BigQuery re-runs used tight `maximum_bytes_billed` caps from each dry run.

## v0.2.0 (unreleased): analysis review

- Attribution: simplified GA4 default channel grouping and a self-referral
  sensitivity. 1,381 of 3,230 converted sessions include a
  `*.googlemerchandisestore.com / referral` touch, which takes 980 last-touch
  credits as observed; with those touches removed the four rules largely agree.
  `time_decay` is now documented as position decay (one-touch half-life).
- Funnel: a coverage check shows the strict same-session funnel keeps 2,847 of at
  least 4,844 purchase sessions; 1,997 purchases have no same-session add-to-cart.
- Model: a returning-visitor rule baseline and 95% cluster-bootstrap intervals.
  PR-AUC 0.041390 (0.027242 to 0.067993) against 0.024040 for the rule.
- Logistic regression is now solved exactly (Newton's method, standardized inputs,
  tolerance 1e-10). The early-stopped L-BFGS fit made the 5% queue flag 317
  sessions on macOS and 322 on Linux; the converged fit flags 327.
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
