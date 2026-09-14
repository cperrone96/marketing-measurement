# API v1 money and error contracts

The public educational API returns routing and validation failures as the same safe
shape: `{"code": "...", "message": "...", "details": {...}}`. It does not
return framework detail text, stack traces, or submitted values.

All budget-scenario monetary outputs use fixed two-decimal strings, including
`allocations`, `total_budget`, `estimated_incremental_value`, and each sensitivity
scenario's `estimated_incremental_value`. For example, an allocation is returned as
`"0.70"`, never `0.7`. Inputs continue to accept JSON numbers or decimal strings
and are validated by the Task 6 whole-cent optimizer.
