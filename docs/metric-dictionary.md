# Metric dictionary

Every metric is labeled **public observed** or **synthetic**. Null means unmeasured or
undefined; it is never silently converted to zero.

## Public observed metrics

| Metric | Numerator | Denominator / grain | Window | Decision use | Source |
| --- | --- | --- | --- | --- | --- |
| Viewed sessions | Distinct sessions containing `page_view` | Unique `user_pseudo_id + ga_session_id` sessions | 2020-11-01–2021-01-31 | Funnel entry coverage | `funnel_daily_by_channel.sql` |
| Engagement rate | Sessions containing engagement | Viewed sessions | Same | Diagnose early journey quality | `funnel.py`, `findings_summary.json` |
| Add-to-cart rate | Sessions containing `add_to_cart` | Engaged sessions | Same | Identify the largest measured transition opportunity | Same |
| Checkout rate | Sessions containing `begin_checkout` | Add-to-cart sessions | Same | Diagnose cart-to-checkout transition | Same |
| Purchase rate | Sessions containing `purchase` | Checkout sessions | Same | Diagnose checkout completion | Same |
| Day-7 retention | Users active exactly seven days after cohort date | Users in true first-touch cohorts with a fully observable day seven | Eligible cohorts through 2021-01-24 | Lifecycle measurement | `cohort_retention.sql`, `cohorts.py` |
| Attribution credit | Weighted model credit assigned to a channel | 3,230 eligible converted sessions | Conversions 2020-12-01–2021-01-31, complete 30-day lookback | Compare descriptive accounting rules | `conversion_channel_paths.sql`, `attribution.py` |
| ROC-AUC | Pairwise ranking performance | 7,245 held-out sampled sessions | Source window | Ranking diagnostic | Model notebook/card |
| PR-AUC | Precision-recall curve area | 7,245 held-out sessions; 101 conversions | Source window | Low-prevalence ranking diagnostic | Model notebook/card |
| Brier score | Mean squared probability error | 7,245 held-out sessions | Source window | Calibration diagnostic | Model notebook/card |
| Capacity precision | 22 true positives | 317 flagged held-out sessions | Training-frozen threshold | Review-queue yield | Model notebook/card |
| Capacity recall | 22 true positives | 101 held-out conversions | Training-frozen threshold | Review-queue coverage | Model notebook/card |

Funnel stages are session-presence measures, not proof that every event occurred in
sequence. Attribution is always labeled **descriptive attribution; not causal**.

## Synthetic metrics and scenarios

| Metric | Numerator | Denominator / grain | Decision use | Source |
| --- | --- | --- | --- | --- |
| Consent eligibility | Synthetic candidates marked eligible | All generated candidates | Demonstrate consent gating | `simulation/integration.py` |
| Partner match rate | Eligible synthetic candidates matched | Consent-eligible candidates | Demonstrate identity-quality monitoring | Same |
| Delivery success rate | Successful deliveries | Eligible and matched candidates | Demonstrate delivery monitoring | Same |
| Rejection rate | Rows with a rejection reason | All synthetic candidates | Diagnose simulated pipeline exclusions | Same |
| Freshness SLA rate | Records ≤24 hours old | All synthetic candidates | Demonstrate source freshness monitoring | Same |
| Latency SLA rate | Successful deliveries ≤60 minutes | Successful deliveries | Demonstrate delivery latency monitoring | Same |
| Activation rate | Exposed candidates | Successful deliveries | Demonstrate downstream adoption monitoring | Same |
| Experiment ITT effect | Treatment conversion rate minus control rate | All 200 randomized synthetic candidates | Demonstrate predeclared A/B analysis | `analysis/experiments.py` |
| Planned sample gate | Actual candidates per arm | 2,033 required per arm at configured assumptions | Prevent winner claims when underpowered | Same |
| Budget allocation | Whole-cent spend per channel | Total equals submitted budget; each channel respects bounds | Demonstrate constrained planning | `analysis/budget.py` |
| Estimated incremental value | Allocation × user-supplied value assumption | Synthetic scenario only | Compare assumptions, not forecast outcomes | Same |

Default generated values are deterministic for regression testing, but their rates are
not business benchmarks. The experiment's 100 candidates per arm do not meet the
2,033-per-arm gate; its result is inconclusive and no arm is declared a winner.
