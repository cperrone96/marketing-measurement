# API v1 money and error contracts

The public educational API returns routing and validation failures as the same safe
shape: `{"code": "...", "message": "...", "details": {...}}`. It does not
return framework detail text, stack traces, or submitted values.

All budget-scenario monetary outputs use fixed two-decimal strings, including
`allocations`, `total_budget`, `estimated_incremental_value`, and each sensitivity
scenario's `estimated_incremental_value`. For example, an allocation is returned as
`"0.70"`, never `0.7`. Inputs continue to accept JSON numbers or decimal strings
and are validated by the Task 6 whole-cent optimizer.
Money inputs are limited to 99,999,999,999,999.99 with at most two decimal places;
expected-value multipliers are finite, non-negative, capped at 10, and limited to six
decimal places. Decimal/integer-cent representation is preserved end to end. Values
outside those bounds, non-finite values, overflow, and precision failures return the
same structured 422 contract.

`GET /api/v1/kpis` also publishes typed, public-observed analysis sections for landing
pages, devices, product/revenue performance, and high-value journey patterns. The
existing `POST /api/v1/scenarios/budget` response includes the separately labelled
synthetic randomized-experiment scenario; the API surface remains exactly ten routes.

## Paginated detail and decision summaries

`GET /api/v1/funnel` and `GET /api/v1/cohorts` retain their paginated `items`
collections. Each response also includes a `decision_summary` computed by the API
from the complete filtered collection before detail pagination:

- Funnel `coverage` is `full_filtered_window`; `stages` contains full-window stage
  totals and `channels` contains the eight channels ranked by engaged sessions.
- Cohort `coverage` is `complete_day_7_cohorts`; `items` contains every complete
  day-7 cohort and its API-computed retention rate.

Dashboard charts consume these decision summaries. They never infer full-sample
totals from a single page of detail rows.
