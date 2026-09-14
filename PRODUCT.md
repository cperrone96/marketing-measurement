# Marketing Measurement Decision Studio

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing Python application using FastAPI contracts and a delegated Plotly Dash dashboard. The dashboard consumes the published API response models only.

## Users

- Hiring managers and recruiters evaluating whether the portfolio demonstrates decision-ready data science, analytics engineering, and product communication.
- Business stakeholders reviewing acquisition, customer-journey, measurement, integration-health, and budget decisions without needing to inspect notebooks or source code first.

## Product Purpose

Turn reviewed marketing-analysis outputs into a concise decision workspace. Success means a reviewer can understand what the evidence supports, distinguish observed findings from demonstrations, trace each result to its source, and identify the next defensible action.

## Positioning

The product connects a public, obfuscated GA4 evidence base to clearly separated synthetic integration and planning demonstrations, showing the full path from governed data and analysis to an executive decision interface without exposing customer information.

## Operating Context

The workspace is used as a portfolio artifact during recruiting and as an executive-style review surface. It supports five recurring views: summary, acquisition (including landing page and device), journeys (including product/revenue and high-value patterns), integration health, and scenarios (experiment plus budget). Reviewers may use it on desktop or mobile and may need accessible table alternatives to visual charts.

## Capabilities and Constraints

- Consume only the versioned FastAPI response contracts; dashboard pages never query storage or repository modules directly.
- Show public observed evidence and synthetic demonstrations as visibly distinct evidence types.
- Treat attribution as descriptive, not causal.
- Include source windows, provenance, methodology, limitations, loading, empty, and error states.
- Use no customer, Data Design Dynamics, DDA, healthcare-patient, or personal-account data.
- Do not claim live advertising-platform integrations, causal lift, or real campaign results from synthetic records.
- Preserve the public sample window of November 1, 2020 through January 31, 2021 where it applies.

## Evidence on Hand

- Google public obfuscated GA4 ecommerce aggregates and deterministic derived findings under `data/observed/ga4_public_sample/` and `data/derived/ga4_public_sample/`.
- Deterministic synthetic audience, consent, partner-delivery, experiment, and budget-scenario outputs exposed through the existing scenario and integration API contracts.
- Reviewed aggregate landing-page, device, product/revenue, and high-value-journey analyses from the public sample, with query and result provenance.
- Reviewed model metrics and model card under `docs/models/conversion-model-card.md`.
- No real customer records, campaign performance, proprietary methods, testimonials, or commercial claims are available and none may be fabricated.

## Product Principles

1. Lead with the decision, then show evidence strength, finding, and action.
2. Make evidence boundaries impossible to miss.
3. Pair every visual summary with a readable text or table alternative.
4. Prefer honest uncertainty and methodology over false precision.
5. Let a reviewer trace claims without exposing private data.

## Accessibility & Inclusion

The web dashboard must support keyboard navigation, visible focus, reduced-motion preferences, responsive layouts, text contrast of at least 4.5:1, semantic headings and landmarks, and a text alternative for every chart.
