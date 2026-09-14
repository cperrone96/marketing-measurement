# Conversion propensity model card

## Purpose and boundary

This is an **educational decision-support portfolio model**, not a production
targeting system. It describes associations in Google's public, obfuscated GA4
ecommerce sample and can illustrate how a team might prioritize a limited review
queue. It does not estimate causal impact, recommend real-campaign treatment, or
make a claim about real-campaign performance.

## Data and provenance

- Source: `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`, covering
  2020-11-01 through 2021-01-31.
- Query: `sql/bigquery/conversion_model_sessions.sql` (SHA-256
  `26e5aead54dee1c80bc695d78664319b328ba59cda7a64ee8a3f3ac3ad7e0270`). It is
  fully qualified, public-only, and was dry-run before execution with billing project
  `christina-data-portfolio-2026` and `maximum_bytes_billed=4,000,000,000`.
- Dry run processed 1,677,485,270 bytes; the executed job processed the same amount
  and billed 1,677,721,600 bytes. The query returned 36,211 measured sessions.
- Result: `data/observed/ga4_public_sample/conversion_model_sessions.json.gz`
  (SHA-256 `cf828e20761a596a0ca1a7f2568dd808792367137ba7bd0a6a3bfc946dfccf9c`). It is
  gzip-compressed to 252 KB with fixed `mtime=0` and empty filename metadata.
  Canonical SQL tie-breakers and output order make identical logical results produce
  identical gzip bytes. Retrieval metadata records independent SQL and result hashes
  in `data/observed/ga4_public_sample/retrieval_metadata.json`.
- The sample has 466 purchase-converting sessions (1.2869%). It contains no raw
  user, session, event, or transaction identifier.

The query deterministically samples 10% of users, retains one row per measured
session, and exports `user_group_bucket` only as `FARM_FINGERPRINT(user_pseudo_id)
mod 10,000`. This bucket is non-unique and is not an identifier. It keeps a user's
sessions in one split, but collisions also put some unrelated users together. That
is a conservative group-isolation approximation; it does not prove perfect
user-level separation.

## Target and inputs

The target is whether the measured session contains a `purchase` event. The model
uses only features available before that outcome:

- session-start hour and day of week (the date is retained only for provenance);
- device category and coarse country group (United States, Other, or unknown);
- new/returning status from the session's first observed event;
- source, medium, and campaign from that same first observed event.

The `LeakageError` guard is an exact allowlist, not a blacklist: only the eight
features listed above can reach a model pipeline. It rejects every other requested
field, including targets, identifiers, split/provenance fields, arbitrary unknown
aliases, and post-outcome behavior such as engagement, cart, checkout,
purchase/revenue, transactions, duration, or later pages. `user_group_bucket` and
`session_start_date` are never model features.

## Split, preprocessing, and comparison

`GroupShuffleSplit` makes a deterministic 80/20 group-disjoint split: 28,966
training rows and 7,245 held-out rows, with zero overlapping exported buckets. The
model selection CV is `GroupKFold(n_splits=5)` entirely within the training data.
All imputation and one-hot encoding are inside each model pipeline. The capacity
threshold is frozen at 0.035589 from 28,966 grouped out-of-fold training predictions
only, before any final holdout score, label, threshold, or subgroup calculation.

The no-skill comparator predicts the training prevalence. Two fitted comparators are
logistic regression and a random forest; logistic regression was selected by mean
training-CV PR-AUC.

| Model / evidence | ROC-AUC | PR-AUC | Brier score |
| --- | ---: | ---: | ---: |
| No-skill prevalence, held out | 0.500000 | 0.013941 | 0.013748 |
| Logistic regression, training CV | 0.707922 | 0.043843 | 0.012284 |
| Random forest, training CV | 0.676439 | 0.031707 | 0.079871 |
| Logistic regression, held out | 0.652281 | 0.041429 | 0.013582 |
| Random forest, held out | 0.629040 | 0.040626 | 0.085390 |

## Calibration

No calibration was applied. The held-out Brier score for the selected logistic model
is only slightly better than the no-skill value (0.013582 vs. 0.013748), and its
five held-out quantile bins show modest, rather than compelling, calibration error:

| Mean predicted probability | Observed conversion rate |
| ---: | ---: |
| 0.005008 | 0.008972 |
| 0.005904 | 0.011027 |
| 0.006739 | 0.006911 |
| 0.011844 | 0.010352 |
| 0.033310 | 0.032436 |

Most importantly, the untouched holdout must not be reused to fit a calibrator. A
future calibration experiment would require a nested, group-disjoint validation
step inside the training population and a new untouched test set.

## Capacity scenario and threshold trade-offs

For an illustrative outreach/review team that can inspect **50 sessions per 1,000**,
the threshold is 0.035589, frozen from training-only grouped out-of-fold predictions
before evaluating the holdout. It flags 317 of 7,245 held-out sessions (43.75 per
1,000), with precision 0.069401 and recall 0.217822. The holdout rate need not be
exactly 50/1,000 because the frozen training threshold is not tuned to test scores.

| Scenario | Threshold | Flagged sessions | Precision | Recall |
| --- | ---: | ---: | ---: | ---: |
| 0.05 | 0.050000 | 112 | 0.089286 | 0.099010 |
| 0.10 | 0.100000 | 19 | 0.052632 | 0.009901 |
| 0.20 | 0.200000 | 0 | 0.000000 | 0.000000 |
| 0.30 | 0.300000 | 0 | 0.000000 | 0.000000 |
| 0.50 | 0.500000 | 0 | 0.000000 | 0.000000 |
| Capacity: 50/1,000, frozen from training OOF | 0.035589 | 317 | 0.069401 | 0.217822 |

At the frozen capacity threshold, the held-out confusion matrix is 6,849 true
negatives, 295 false positives, 79 false negatives, and 22 true positives.

## Subgroup diagnostics at the capacity threshold

These are descriptive diagnostics, not fairness certification. The tablet and other
small subgroups are particularly unstable.

| Dimension | Group | Sessions | Conversions | Flagged | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Country | Other | 4,028 | 52 | 208 | 0.072115 | 0.288462 |
| Country | United States | 3,217 | 49 | 109 | 0.064220 | 0.142857 |
| Device | desktop | 4,249 | 58 | 152 | 0.085526 | 0.224138 |
| Device | mobile | 2,847 | 42 | 154 | 0.058442 | 0.214286 |
| Device | tablet | 149 | 1 | 11 | 0.000000 | 0.000000 |
| Status | new | 5,205 | 39 | 0 | 0.000000 | 0.000000 |
| Status | returning | 2,040 | 62 | 317 | 0.069401 | 0.354839 |

## Limitations and monitoring needs

The public data is old, obfuscated, ecommerce-specific, and sampled; it is not Data
Design Dynamics data and should not be generalized to a client's visitors. Session
acquisition context can be incomplete or unattributed, and a purchase-event label is
not necessarily the conversion definition for another business. The low prevalence,
threshold sensitivity, non-unique split bucket, temporal drift risk, and subgroup
differences mean this evidence is suitable only for teaching measurement mechanics.
Any future operational use would require consent, a separately governed dataset,
privacy review, an outcome definition, ongoing drift/subgroup monitoring, and a
causal experiment before claiming lift.
