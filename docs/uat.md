# User acceptance testing

Acceptance focuses on recruiter/stakeholder comprehension, traceability, accessibility,
and safe evidence boundaries. Public observed and synthetic content must remain
distinguishable without relying on color alone.

## Automated acceptance

| ID | Acceptance criterion | Verification | Expected result |
| --- | --- | --- | --- |
| UAT-01 | Every public observed headline number, label, decision, limitation, and trace link matches reviewed evidence | `pytest -q tests/release/test_release_documentation.py` | Funnel, retention, attribution, and model contracts pass |
| UAT-02 | Public and synthetic evidence do not mix | `pytest -q tests/api tests/dashboard tests/simulation` | Evidence labels, provenance, and limitations pass |
| UAT-03 | API schemas, errors, pagination, and money fields remain stable | `pytest -q tests/api` | Exactly ten typed v1 routes; contract tests pass |
| UAT-04 | Dashboard reads only API contracts | `pytest -q tests/dashboard` | No repository/storage imports and all routes render |
| UAT-05 | Core logic and SQL reconcile | `pytest -q` | All tests pass on redistributable local fixtures/artifacts |
| UAT-06 | Notebooks execute without cloud credentials or source mutation | `make notebook-smoke` | Both execute in a temporary copy; generated evidence byte-matches reviewed evidence |
| UAT-07 | Release evidence has not drifted | `make verify-checksums` | Every SHA-256 entry reports `OK` |
| UAT-08 | Static quality gates pass | `make lint && make typecheck` | Ruff and strict mypy are clean |

## Manual reviewer scripts

### Two-minute evidence review

1. Open the summary route at 1280 px or wider.
2. Confirm the decision statement appears before supporting charts.
3. Confirm the public observed lane says the exact 2020-11-01–2021-01-31 window.
4. Confirm the synthetic lane uses both a written label and hatch pattern.
5. Expand a chart's “View evidence table” control and follow its provenance link.

Expected: the reviewer can identify the decision, denominator, evidence type, source,
and limitation without reading source code.

### Accessibility and responsive review

1. Traverse every route, disclosure, input, and button by keyboard only.
2. Confirm a visible orange focus indicator and logical focus order.
3. Enable reduced motion and confirm nonessential animation is suppressed.
4. Review at 390 × 844 and 1440 × 900; ensure no hidden content or unusable overflow.
5. Confirm every chart has a readable table alternative and semantic heading order.

Expected: interaction remains operable and evidence meaning never depends on color.
Reviewed reference captures are under `.impeccable/review/`.

### Error and empty states

1. Stop the API and load the dashboard.
2. Confirm a safe, actionable error is shown without a stack trace or submitted value.
3. Restart the API and request an out-of-window date range or invalid page size.

Expected: structured `{code, message, details}` errors and explicit empty-state language.

## Release sign-off

- [x] Public observed claims trace to queries/notebooks/artifacts.
- [x] Synthetic demonstrations are visibly non-observed and non-causal.
- [x] Automated tests cover data, analytics, model, API, dashboard, and release docs.
- [x] Desktop, mobile, keyboard focus, and reduced-motion behavior reviewed.
- [ ] External deployment and repository publishing are intentionally out of scope.
