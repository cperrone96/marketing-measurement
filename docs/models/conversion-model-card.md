# Conversion propensity model card

## Purpose

Rank next month's sessions by purchase likelihood from what is known when a session
lands, so a team with fixed review capacity (50 sessions per 1,000) can fill its
queue. The model describes associations in Google's public, obfuscated GA4 ecommerce
sample; it does not estimate causal impact. All numbers below come from
`data/derived/ga4_public_sample/conversion_model_evaluation.json` and the executed
`notebooks/02_conversion_model.ipynb`.

## Data and provenance

- Source: `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`, covering
  2020-11-01 through 2021-01-31.
- Query: `sql/bigquery/conversion_model_sessions.sql` (SHA-256
  `557d5aa822cbf3848f8f53a31230774b639c47673888ed08e0c8fd847b598744`), public data
  only, dry-run first, then run with `maximum_bytes_billed` set 50 MiB above the
  dry-run size. It processed 1,677,485,270 bytes and billed 1,677,721,600.
- Result: `data/observed/ga4_public_sample/conversion_model_sessions.json.gz`
  (SHA-256 `f1e30fb2c0c4a9bba6652925029cbe5605ffb1755fc7a5c5f97c8664c1647ba3`),
  written as deterministic gzip. Job and hash details are in
  `data/observed/ga4_public_sample/retrieval_metadata.json`.
- Population: 33,553 sessions with a landing page view, from a deterministic 10%
  user sample, including 466 purchase sessions. No user, session, event or
  transaction identifier is exported. `user_group_bucket`
  (`FARM_FINGERPRINT(user_pseudo_id) mod 10,000`) is non-unique and used only to
  keep a user's sessions in one CV fold.

## Target and inputs

The target is whether the session contains a `purchase` event. An exact allowlist
(`LeakageError` rejects anything else) admits only fields known at landing:

- session-start hour and day of week;
- device category and coarse country group;
- new/returning status (`ga_session_number`);
- source, medium and campaign from the landing `page_view`, which must precede any
  purchase in the session.

An earlier extract read source and medium from the session's first event. That
event is usually `session_start` or `first_visit`, which never carry those fields,
so 88% of sessions were `(unattributed)`. Reading the landing page view brings that
to 38.86%; the rest are landing hits that carry no source in this obfuscated export.

## Validation design

- **Forward in time.** Training is November and December 2020 (22,359 sessions); the
  holdout is every January 2021 session (11,194 sessions, 116 conversions), scored
  once.
- **Tuning and selection inside training only.** `GroupKFold(5)` over user buckets.
  L2 logistic regression (C in 0.01, 0.1, 1, 10; solved exactly with Newton's
  method on standardized inputs) and histogram gradient boosting (learning rate 0.03
  or 0.1, 7 or 15 leaves, 200 rounds, native categorical splits). The family with
  the higher mean CV PR-AUC is selected.
- **Capacity threshold** frozen from grouped out-of-fold training scores at the top
  5%, before the holdout is scored.
- **Uncertainty:** 95% percentile intervals from 2,000 cluster-bootstrap resamples
  of holdout user buckets.

## Results

Gradient boosting was selected (CV PR-AUC 0.053273 vs 0.050028 for logistic
regression). On the holdout the two are indistinguishable:

| Model / evidence | ROC-AUC | PR-AUC | Brier score |
| --- | ---: | ---: | ---: |
| No-skill prevalence, held out | 0.500000 | 0.010363 | 0.010283 |
| Returning-visitor rule, held out | 0.720098 | 0.025031 | 0.010147 |
| Logistic regression (C=1), training CV | 0.781951 | 0.050028 | 0.015174 |
| Gradient boosting (rate 0.03, 7 leaves), training CV | 0.781279 | 0.053273 | 0.015143 |
| Logistic regression, held out | 0.817465 | 0.050711 | 0.010039 |
| Gradient boosting, held out (selected) | 0.811306 | 0.051064 | 0.010049 |

| Quantity (selected model) | Estimate | 95% interval |
| --- | ---: | ---: |
| PR-AUC | 0.051064 | 0.036526 to 0.077015 |
| ROC-AUC | 0.811306 | 0.766181 to 0.853229 |
| PR-AUC gain over the returning-visitor rule | 0.026032 | 0.016083 to 0.047182 |
| Queue precision at the capacity threshold | 0.068460 | 0.045708 to 0.092421 |
| Queue recall at the capacity threshold | 0.241379 | 0.168032 to 0.321429 |
| Queue lift over the January base rate | 6.606357 | 4.684573 to 8.713375 |

The model beats the returning-visitor rule on both ranking metrics; the earlier
version did not on ROC-AUC because its acquisition features were mostly empty.

## Capacity queue

The threshold is 0.055140 (frozen from training). In January it flags 409 of 11,194
held-out sessions (36.54 per 1,000), fewer than 50 per 1,000 because January
converted less than the training months. Confusion matrix: 10,697 true negatives,
381 false positives, 88 false negatives, 28 true positives. No held-out score lies
within 1e-6 of the threshold (the notebook asserts this), so queue membership does
not hinge on floating-point noise; refitting on row-permuted training data gives
bit-identical scores.

## Calibration

No calibrator is fit; the holdout is used once, for diagnosis. The model expected
165.08 January conversions and 116 occurred (observed/expected 0.702681), with a
calibration slope of 1.250041. Training-period scores over-predict a quieter month,
so rankings are usable but the scores are not probabilities to budget against
without recalibration on recent data.

| Mean predicted probability | Observed conversion rate |
| ---: | ---: |
| 0.0028 | 0.0025 |
| 0.0056 | 0.0019 |
| 0.0079 | 0.0040 |
| 0.0127 | 0.0072 |
| 0.0449 | 0.0362 |

## What drives the ranking

Permutation importance (drop in held-out PR-AUC, 10 shuffles per feature):
new/returning status 0.036346, session source 0.019430, session medium 0.017585;
every other feature is within noise of zero. These are associations: a source that
ranks high is not shown to cause purchases.

## Where it fails

| Dimension | Group | Sessions | Conversions | Flagged | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Country | Other | 6,190 | 69 | 253 | 0.0791 | 0.2899 |
| Country | United States | 5,004 | 47 | 156 | 0.0513 | 0.1702 |
| Device | desktop | 6,443 | 58 | 225 | 0.0711 | 0.2759 |
| Device | mobile | 4,518 | 56 | 175 | 0.0629 | 0.1964 |
| Device | tablet | 233 | 2 | 9 | 0.1111 | 0.5000 |
| Status | new | 9,026 | 43 | 7 | 0.0000 | 0.0000 |
| Status | returning | 2,168 | 73 | 402 | 0.0697 | 0.3836 |

First visits are almost never flagged, so the queue misses all 43 January
conversions that happened on a first visit. Recall is lower for United States and
mobile sessions. These are descriptive diagnostics, not a fairness certification.

## Limitations

The data are one store's obfuscated export from late 2020, so none of these numbers
transfer to another site. With 116 held-out conversions the intervals are wide.
The split key is a non-unique hash bucket. Any operational use would need current
governed data, recalibration, privacy review, drift and subgroup monitoring, and a
randomized holdout before claiming that contacting flagged sessions changes
outcomes.
