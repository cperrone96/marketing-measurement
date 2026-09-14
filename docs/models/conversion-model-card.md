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
  `8bf1cf9099515ce457479c69d3808702e6684f7c21b528ae314aee2124fcd128`). It is
  fully qualified, public-only, and was dry-run before execution with billing project
  `christina-data-portfolio-2026` and `maximum_bytes_billed=4,000,000,000`.
- Dry run processed 1,677,485,270 bytes; the executed job processed the same amount
  and billed 1,677,721,600 bytes. The query returned 36,211 measured sessions.
- Result: `data/observed/ga4_public_sample/conversion_model_sessions.json.gz`
  (SHA-256 `6d71b626f7734f261b217489e91d12af95a592955b3eb091542eb5c392b9a6b6`). It is
  gzip-compressed to 252 KB. Retrieval metadata records independent SQL and result
  hashes in `data/observed/ga4_public_sample/retrieval_metadata.json`.
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

The query and `LeakageError` guard exclude post-outcome or later-behavior fields:
engagement, cart, checkout, purchase/revenue, transactions, session duration, and
later page behavior. `user_group_bucket` and `session_start_date` are never model
features.

## Split, preprocessing, and comparison

`GroupShuffleSplit` makes a deterministic 80/20 group-disjoint split: 28,966
training rows and 7,245 held-out rows, with zero overlapping exported buckets. The
model selection CV is `GroupKFold(n_splits=5)` entirely within the training data.
All imputation and one-hot encoding are inside each model pipeline.

The no-skill comparator predicts the training prevalence. Two fitted comparators are
logistic regression and a random forest; logistic regression was selected by mean
training-CV PR-AUC.

| Model / evidence | ROC-AUC | PR-AUC | Brier score |
| --- | ---: | ---: | ---: |
| No-skill prevalence, held out | 0.500000 | 0.013941 | 0.013748 |
| Logistic regression, training CV | 0.712479 | 0.033056 | 0.012329 |
| Random forest, training CV | 0.685789 | 0.028183 | 0.075702 |
| Logistic regression, held out | 0.679121 | 0.035661 | 0.013621 |
| Random forest, held out | 0.667223 | 0.021713 | 0.085107 |

## Calibration

No calibration was applied. The held-out Brier score for the selected logistic model
is only slightly better than the no-skill value (0.013621 vs. 0.013748), and its
five held-out quantile bins show modest, rather than compelling, calibration error:

| Mean predicted probability | Observed conversion rate |
| ---: | ---: |
| 0.004370 | 0.006882 |
| 0.005850 | 0.008304 |
| 0.006818 | 0.007576 |
| 0.013268 | 0.016552 |
| 0.032865 | 0.030450 |

Most importantly, the untouched holdout must not be reused to fit a calibrator. A
future calibration experiment would require a nested, group-disjoint validation
step inside the training population and a new untouched test set.

## Capacity scenario and threshold trade-offs

For an illustrative outreach/review team that can inspect **50 sessions per 1,000**,
the selected threshold is 0.034407. It flags 363 of 7,245 held-out sessions (50.10
per 1,000), with precision 0.041322 and recall 0.148515. Equal scores at a threshold
can cause a slight capacity overage; a production queue would use a deterministic
secondary ordering and monitoring instead of treating this as an automated action.

| Scenario | Threshold | Flagged sessions | Precision | Recall |
| --- | ---: | ---: | ---: | ---: |
| 0.05 | 0.050000 | 68 | 0.073529 | 0.049505 |
| 0.10 | 0.100000 | 0 | 0.000000 | 0.000000 |
| 0.20 | 0.200000 | 0 | 0.000000 | 0.000000 |
| 0.30 | 0.300000 | 0 | 0.000000 | 0.000000 |
| 0.50 | 0.500000 | 0 | 0.000000 | 0.000000 |
| Capacity: 50/1,000 | 0.034407 | 363 | 0.041322 | 0.148515 |

At the capacity threshold, the held-out confusion matrix is 6,796 true negatives,
348 false positives, 86 false negatives, and 15 true positives.

## Subgroup diagnostics at the capacity threshold

These are descriptive diagnostics, not fairness certification. The tablet and other
small subgroups are particularly unstable.

| Dimension | Group | Sessions | Conversions | Flagged | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Country | Other | 4,028 | 52 | 288 | 0.041667 | 0.230769 |
| Country | United States | 3,217 | 49 | 75 | 0.040000 | 0.061224 |
| Device | desktop | 4,249 | 58 | 145 | 0.068966 | 0.172414 |
| Device | mobile | 2,847 | 42 | 201 | 0.024876 | 0.119048 |
| Device | tablet | 149 | 1 | 17 | 0.000000 | 0.000000 |
| Status | new | 5,205 | 39 | 0 | 0.000000 | 0.000000 |
| Status | returning | 2,040 | 62 | 363 | 0.041322 | 0.241935 |

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
