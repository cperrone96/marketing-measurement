# API v1 money and error contracts

The public educational API returns routing and validation failures as the same safe
shape: `{"code": "...", "message": "...", "details": {...}}`. It does not
return framework detail text, stack traces, or submitted values.

All budget-scenario monetary outputs use fixed two-decimal strings, including
`allocations`, `total_budget`, `estimated_incremental_value`, and each sensitivity
scenario's `estimated_incremental_value`. For example, an allocation is returned as
`"0.70"`, never `0.7`. Inputs continue to accept JSON numbers or decimal strings
and are validated by the Task 6 whole-cent optimizer.

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
