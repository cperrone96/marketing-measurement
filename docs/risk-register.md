# Risk register

This register applies to both public observed evidence and synthetic demonstrations.

| Risk | Likelihood / impact | Control | Residual risk / owner action |
| --- | --- | --- | --- |
| Historic obfuscated ecommerce data is generalized to a current employer or industry | Medium / High | Scope window appears beside every public finding; README and API limitations prohibit generalization | Validate decisions on current, governed domain data before use |
| Descriptive attribution is read as causal | Medium / High | Every output says “descriptive attribution; not causal”; four methods expose sensitivity | Require a randomized experiment before claiming lift |
| Synthetic metrics are mistaken for real campaign performance | Medium / High | Separate namespace, evidence type, hatch pattern, reserved domains, deterministic seed, explicit non-claims | Do not remove evidence labels in derivative presentations |
| Outcome leakage inflates model evidence | Low / High | Exact pre-outcome allowlist; group-disjoint split; training-only CV and threshold; leakage tests | Re-audit features for any new source schema |
| Low prevalence and subgroup sparsity produce unstable model decisions | High / Medium | PR-AUC, baseline, calibration, threshold table, and subgroup counts reported | Collect current data and reserve a new untouched validation set |
| Public retrieval creates unexpected cost or accesses the wrong project | Low / Medium | Explicit billing project, dry run, fully qualified public dataset, 4 GB cap per query; excluded from CI | Operator must inspect the dry-run plan before retrieval |
| Source or result bytes drift silently | Low / High | Manifest records query/result hashes; release checksum gate runs locally and in CI | Review and version any intentional data refresh |
| API leaks paths, identifiers, submitted values, or traces | Low / High | Typed response models, structured safe errors, aggregate-only artifact repository, contract tests | Add security review before any public production deployment |
| Dependency ranges resolve differently over time | Medium / Medium | Python 3.12 boundary, CI gates, audited dependency set | Add a reviewed lock file before production deployment |
| Notebook execution changes tracked evidence | Low / Medium | Checksums run first; copied outputs are deleted in a temporary source copy; notebooks must freshly create byte-matching evidence; checksums run again | Investigate any missing/mismatched output; never repair or overwrite reviewed evidence silently |
| Fixture-only CI misses cloud/source regressions | Medium / Medium | Query text, caps, hashes, and source contracts are tested offline | Run bounded manual retrieval only for an approved source refresh |

No live customer data, advertising accounts, Google Analytics properties, proprietary
systems, or personal accounts are required or authorized by this project.
