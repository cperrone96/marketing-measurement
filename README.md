# Marketing Measurement Decision Studio

Where does an ecommerce store lose buyers, which channels really earn credit for its
sales, and can landing-time context pick out next month's likely buyers for a limited
review queue? The answers are for a store's marketing and analytics leads: what to fix
in GA4 before trusting channel reports, and whether a propensity queue is worth
testing. The project uses Google's public GA4 export for the Google Merchandise Store
and serves results through typed FastAPI contracts and a Plotly Dash dashboard, so
every number traces back to a query and a test.

## Key results

Public GA4 sample, 2020-11-01 through 2021-01-31. Funnel, retention and attribution
numbers come from
[`findings_summary.json`](data/derived/ga4_public_sample/findings_summary.json); model
numbers come from
[`conversion_model_evaluation.json`](data/derived/ga4_public_sample/conversion_model_evaluation.json).

| Question | Result | Context |
| --- | --- | --- |
| Where does the funnel narrow? | 6.29% of engaged sessions add to cart (15,127 of 240,406) | Other steps: view to engaged 72.05% (GA4 `session_engaged`), cart to checkout 39.41%, checkout to purchase 47.78%; 0.85% of 333,683 viewed sessions complete every stage |
| How complete is a same-session funnel? | It keeps 2,848 of at least 4,845 purchase sessions (58.78%) | 1,997 purchase sessions have no add-to-cart in the same session |
| Do new users come back? | 0.68% return on day 7 (1,611 of 238,644) | 85 first-touch cohorts with a fully observed day 7 |
| How much do self-referrals distort attribution? | 1,381 of 3,230 converted sessions (42.76%) include a store self-referral, which takes 980 last-touch credits | Organic Search first vs last touch: 1,324 vs 1,054 as observed, 1,380 vs 1,312 with self-referrals removed |
| Can landing-time context rank next month's buyers? | Held-out PR-AUC 0.0511 (95% CI 0.0365 to 0.0770); ROC-AUC 0.811 | No-skill 0.0104; returning-visitor rule 0.0250 (ROC-AUC 0.720); gain over the rule 0.0260 (95% CI 0.0161 to 0.0472) |
| What does a 5% review queue yield? | Precision 6.85% (95% CI 4.57% to 9.24%), 6.61x the base rate | Flags 409 of 11,194 January sessions (3.65%) and finds 24.14% of the 116 held-out conversions |

![First-touch and last-touch credit by GA4 channel group, as observed and with store self-referrals removed](docs/figures/attribution_by_channel_group.png)

As observed, last-touch gives the store's own domain 30% of the credit and the four
attribution rules disagree sharply. Treat those touches the way GA4's unwanted-referral
setting would and the rules largely converge: most of the first-versus-last
disagreement was a tracking artifact, not a difference in how channels behave.

## Recommendations

1. **Fix tracking before reading channel reports.** List `googlemerchandisestore.com`
   as an [unwanted referral](https://support.google.com/analytics/answer/10327750),
   Google's standard fix for self-referrals, and check cross-domain setup. As observed, the store's own
   domain takes 980 of 3,230 last-touch credits; with it removed, Organic Search earns
   1,380 first-touch and 1,312 last-touch credits, the largest channel under every rule.
2. **Diagnose the cart step, measured across sessions.** The engaged-to-cart step is
   the narrowest, but 1,997 purchases have no same-session add-to-cart, so measure cart
   behavior at the user level before redesigning it.
3. **Test the propensity queue; don't deploy it.** In a later month, sessions above
   the frozen top-5% threshold convert at 6.85% against a 1.04% base rate, so it
   takes about 15 reviews to reach one buyer, and almost none of the flagged
   sessions (7 of 409) are first visits. Run it as a
   randomized test (flag the top 5%, contact half) and keep it only if a review costs
   less than the incremental margin it produces.

## Approach

- **Session-scoped channels from event parameters.** Each session's channel is the
  first event-scoped `source / medium` pair, not `traffic_source` (which is the user's
  first acquisition). Channels are mapped to a simplified GA4 default channel grouping.
- **Strict funnel with a coverage check.** Stages are counted only when every earlier
  stage occurred in the same session, and stage-pattern aggregates measure how many
  purchases that rule drops.
- **True first-touch cohorts.** Retention cohorts use `user_first_touch_timestamp`
  and include only cohorts whose day 7 falls inside the data window.
- **Rule-based multi-touch attribution.** First touch, last touch, linear and
  position decay (each earlier touch gets half the weight) over a complete 30-day
  lookback, with credit conserved per conversion and a self-referral sensitivity
  analysis.
- **Leakage-safe propensity model validated forward in time.** Train on November and
  December, score January once. An L2 logistic regression (solved exactly with
  Newton's method) and histogram gradient boosting are tuned with `GroupKFold` over
  user buckets inside the training months, on an exact allowlist of landing-time
  features; the capacity threshold is frozen from out-of-fold training scores.
- **Baselines, uncertainty, calibration and interpretation.** No-skill and
  returning-visitor baselines, 95% cluster-bootstrap intervals, calibration
  (observed/expected and slope), permutation importance and subgroup error analysis;
  see the [model card](docs/models/conversion-model-card.md).
- **Governed delivery.** Ten typed FastAPI v1 routes serve reviewed artifacts with
  SHA-256 provenance; the Dash dashboard reads only the API. A deterministic synthetic
  generator demonstrates audience-integration health, an intent-to-treat A/B analysis
  with a power gate, and a constrained budget allocation with sensitivity checks.

## Data

- **Source:** [Google Analytics 4 obfuscated sample ecommerce dataset](https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset)
  (`bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`), available
  through the BigQuery Public Datasets program under Google's terms. It is the GA4
  export for the Google Merchandise Store, with some values obfuscated (`<Other>`,
  `(data deleted)`).
- **Coverage:** 2020-11-01 through 2021-01-31. Units are sessions
  (`user_pseudo_id` + `ga_session_id`), first-touch user cohorts, and converted
  sessions for attribution.
- **What is committed:** compact aggregates from six bounded BigQuery queries in
  [`sql/bigquery/`](sql/bigquery/) and an identifier-free 33,553-session extract (a
  deterministic 10% user sample of sessions with a landing page view) for the model.
  No raw events or identifiers are committed. Retrieval metadata records each query's
  hash, bytes billed and billing cap; see [`docs/sources/ga4-public-sample.md`](docs/sources/ga4-public-sample.md).
- **Synthetic data:** the integration, experiment and budget views use a seeded
  generator (`seed=20260910`) that models consent eligibility, partner matching,
  delivery, exposure, cost and outcomes for 200 audience candidates. It is kept apart
  from the GA4 evidence and labeled as synthetic everywhere it appears.

## Repository structure

```text
sql/bigquery/          bounded source queries that produced the committed extracts
sql/staging, marts/    cross-engine SQL marts tested on a local fixture (DuckDB)
src/marketing_measurement/
  analysis/            funnel, cohorts, attribution, experiments, budget
  modeling/            leakage-safe conversion model, baselines, bootstrap
  quality/, ingestion/ data contracts and fixture validation
  simulation/          seeded synthetic integration generator
notebooks/             01 descriptive findings, 02 conversion model (executed)
data/observed/         committed public aggregates and model extract
data/derived/          evidence JSON written by the notebooks
api/                   FastAPI v1 contracts over reviewed artifacts
dashboard/             Plotly Dash interface that reads only the API
docs/                  model card, metric dictionary, lineage, API contracts
scripts/               retrieval, notebook gate, figure rendering
tests/                 SQL, analysis, model, API, dashboard and release tests
```

## Reproduce

Requires Python 3.12. Everything below runs offline from the committed extracts;
re-querying BigQuery needs your own billing project (see the source doc).

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e . --no-deps

make test            # SQL marts, analysis, model, API, dashboard and release tests
make notebooks       # re-execute both notebooks and rewrite data/derived/*.json
make figures         # redraw docs/figures/attribution_by_channel_group.png
make release-gate    # checksums, ruff, mypy, tests, offline notebook re-run vs reviewed outputs
```

Run the interfaces in two terminals with `make api` (http://127.0.0.1:8000/docs) and
`make dashboard` (http://127.0.0.1:8050). Screenshots of the reviewed dashboard:
[desktop](.impeccable/review/desktop.png), [mobile](.impeccable/review/mobile.png).

## Limitations

- **Old, obfuscated, single-store data.** The sample covers one merchandise store in
  late 2020, and obfuscated or unattributed values leave 12% of last-touch credit
  Unassigned even after self-referrals are removed. None of these rates transfer to
  another business.
- **Attribution is descriptive.** Rule-based credit ranks where to investigate; only
  randomized experiments establish incremental effect.
- **The model is a ranking, not a forecast.** January converted less than the
  training months, so scores over-predict (observed/expected 0.70) and would
  need recalibration before use as probabilities. With 116 held-out conversions the
  intervals are wide, and 38.86% of landing hits carry no source in this export.
  Logistic regression and gradient boosting are statistically indistinguishable
  (held-out PR-AUC 0.0507 vs 0.0511).
- **Synthetic views are demonstrations.** The 200-candidate experiment is deliberately
  underpowered (100 per arm against 4,209 planned per arm) and declares no winner.
