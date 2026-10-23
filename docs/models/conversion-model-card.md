# Conversion propensity model card

## Purpose

Rank sessions by purchase likelihood from session-start context, so a team with a
fixed review capacity (50 sessions per 1,000) can fill its queue. The model
describes associations in Google's public, obfuscated GA4 ecommerce sample; it does
not estimate causal impact. All numbers below come from
`data/derived/ga4_public_sample/conversion_model_evaluation.json` and the executed
`notebooks/02_conversion_model.ipynb`.

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
All imputation, scaling and one-hot encoding are inside each model pipeline. The
logistic regression is solved with Newton's method on standardized numeric inputs to
a 1e-10 tolerance, so it reaches the unique optimum of its convex loss. An earlier
version stopped L-BFGS at its default tolerance after 65 iterations, up to 0.027 away
in predicted probability from that optimum, and the operating point then differed
between macOS (317 flagged) and Linux (322 flagged). The notebook now asserts that no
held-out score lies within 1e-6 of the frozen threshold; the nearest is 2.9e-5 away. The capacity
threshold is frozen at 0.035706 from 28,966 grouped out-of-fold training predictions
only, before any final holdout score, label, threshold, or subgroup calculation.

Two baselines are scored on the same holdout: the training prevalence (no skill)
and a one-feature returning-visitor rule that gives each session its new/returning
group's training conversion rate. Two fitted candidates are logistic regression and
a random forest; logistic regression was selected by mean training-CV PR-AUC.
Encoding hour and day of week as categories instead of numbers was also tried and
lowered training-CV PR-AUC for both candidates, so it was not adopted.

| Model / evidence | ROC-AUC | PR-AUC | Brier score |
| --- | ---: | ---: | ---: |
| No-skill prevalence, held out | 0.500000 | 0.013941 | 0.013748 |
| Returning-visitor rule, held out | 0.668493 | 0.024040 | 0.013642 |
| Logistic regression, training CV | 0.706967 | 0.043855 | 0.012285 |
| Random forest, training CV | 0.676439 | 0.031707 | 0.079871 |
| Logistic regression, held out | 0.653125 | 0.041390 | 0.013585 |
| Random forest, held out | 0.629040 | 0.040626 | 0.085390 |

### Uncertainty

Intervals are 95% percentiles from 2,000 cluster-bootstrap resamples of held-out
user buckets, so sessions that share a bucket move together.

| Quantity | Estimate | 95% interval |
| --- | ---: | ---: |
| Logistic regression PR-AUC | 0.041390 | 0.027242 to 0.067993 |
| Logistic regression ROC-AUC | 0.653125 | 0.590410 to 0.712930 |
| PR-AUC gain over the returning-visitor rule | 0.017350 | 0.007276 to 0.040388 |
| Queue precision at the capacity threshold | 0.067278 | 0.039994 to 0.096027 |
| Queue recall at the capacity threshold | 0.217822 | 0.141005 to 0.297036 |
| Queue lift over the held-out base rate | 4.826051 | 3.104540 to 6.673864 |

The PR-AUC gain over the rule excludes zero, while the rule's ROC-AUC is slightly
higher than the model's. The model's advantage is at the top of the ranking, which
is the part a capacity-limited queue uses.

## Calibration

No calibration was applied. The held-out Brier score for the selected logistic model
is only slightly better than the no-skill value (0.013585 vs. 0.013748), and its
five held-out quantile bins show modest, rather than compelling, calibration error:

| Mean predicted probability | Observed conversion rate |
| ---: | ---: |
| 0.004959 | 0.008941 |
| 0.005871 | 0.011042 |
| 0.006734 | 0.006897 |
| 0.011793 | 0.009695 |
| 0.033379 | 0.033149 |

Most importantly, the untouched holdout must not be reused to fit a calibrator. A
future calibration experiment would require a nested, group-disjoint validation
step inside the training population and a new untouched test set.

## Capacity scenario and threshold trade-offs

For an illustrative outreach/review team that can inspect **50 sessions per 1,000**,
the threshold is 0.035706, frozen from training-only grouped out-of-fold predictions
before evaluating the holdout. It flags 327 of 7,245 held-out sessions (45.13 per
1,000), with precision 0.067278 and recall 0.217822. The holdout rate need not be
exactly 50/1,000 because the frozen training threshold is not tuned to test scores.

| Scenario | Threshold | Flagged sessions | Precision | Recall |
| --- | ---: | ---: | ---: | ---: |
| 0.05 | 0.050000 | 112 | 0.089286 | 0.099010 |
| 0.10 | 0.100000 | 10 | 0.100000 | 0.009901 |
| 0.20 | 0.200000 | 0 | 0.000000 | 0.000000 |
| 0.30 | 0.300000 | 0 | 0.000000 | 0.000000 |
| 0.50 | 0.500000 | 0 | 0.000000 | 0.000000 |
| Capacity: 50/1,000, frozen from training OOF | 0.035706 | 327 | 0.067278 | 0.217822 |

At the frozen capacity threshold, the held-out confusion matrix is 6,839 true
negatives, 305 false positives, 79 false negatives, and 22 true positives.

## Subgroup diagnostics at the capacity threshold

These are descriptive diagnostics, not fairness certification. The tablet and other
small subgroups are particularly unstable.

| Dimension | Group | Sessions | Conversions | Flagged | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Country | Other | 4,028 | 52 | 217 | 0.069124 | 0.288462 |
| Country | United States | 3,217 | 49 | 110 | 0.063636 | 0.142857 |
| Device | desktop | 4,249 | 58 | 154 | 0.084416 | 0.224138 |
| Device | mobile | 2,847 | 42 | 161 | 0.055901 | 0.214286 |
| Device | tablet | 149 | 1 | 12 | 0.000000 | 0.000000 |
| Status | new | 5,205 | 39 | 0 | 0.000000 | 0.000000 |
| Status | returning | 2,040 | 62 | 327 | 0.067278 | 0.354839 |

## Known extraction issue: acquisition features

In 88.14% of sessions the exported `session_source` is `(unattributed)`. The
extraction query takes source, medium and campaign from the session's very first
event, and in this dataset that event is usually `session_start` or `first_visit`,
which never carry those parameters (see
`data/observed/ga4_public_sample/event_parameter_availability.json`). The funnel and
attribution queries avoid this by taking the first event that has a source/medium
pair. Applying the same rule to `conversion_model_sessions.sql` (restricted to
events before any purchase) and re-running the bounded retrieval is the clearest
improvement available; it was not re-run here because it needs BigQuery access.

## Limitations and monitoring needs

The public data is old (late 2020), obfuscated, ecommerce-specific and sampled, so
none of these numbers transfer to another site. Only 101 held-out conversions were
observed, which is why the intervals above are wide. The split is group-disjoint but
random in time; a forward-in-time holdout would better reflect deployment. The
split key is a non-unique hash bucket, so a few unrelated users share a bucket. Any
operational use would need a governed current dataset, a fresh validation set,
privacy review, drift and subgroup monitoring, and a randomized test before
claiming lift.
