---
name: Marketing Measurement Decision Studio
description: An evidence-led executive dashboard that keeps public observation and synthetic planning visibly separate.
colors:
  ink: "#152b31"
  ink-soft: "#40585d"
  paper: "#f5f0e6"
  paper-deep: "#e8dfcf"
  rule: "#9f988b"
  chart-grid: "#c9c1b1"
  observed: "#1e4d45"
  observed-mid: "#347568"
  observed-soft: "#d5e2dc"
  synthetic: "#5b4c91"
  synthetic-mid: "#8d77c2"
  synthetic-soft: "#e1dcf0"
  alert: "#8a3f33"
  alert-soft: "#f1ddd4"
  signal: "#bb6c3f"
  tally-signal: "#f0b68e"
  field-paper: "#fffaf0"
typography:
  display:
    fontFamily: "Newsreader, Georgia, serif"
    fontSize: "clamp(3.4rem, 8vw, 6rem)"
    fontWeight: 700
    lineHeight: 0.92
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Newsreader, Georgia, serif"
    fontSize: "clamp(1.65rem, 3vw, 2.7rem)"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "-0.02em"
  body:
    fontFamily: "IBM Plex Mono, Menlo, monospace"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "IBM Plex Mono, Menlo, monospace"
    fontSize: "0.78rem"
    fontWeight: 600
    lineHeight: 1.55
    letterSpacing: "0.08em"
rounded:
  square: "0"
spacing:
  compact: "0.4rem"
  control: "0.7rem 1rem"
  inset: "1.3rem 1.4rem"
  section: "clamp(2rem, 5vw, 5rem)"
  page-inline: "clamp(1rem, 4vw, 4.5rem)"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.square}"
    padding: "{spacing.control}"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.observed}"
    textColor: "{colors.paper}"
    rounded: "{rounded.square}"
    padding: "{spacing.control}"
    height: "44px"
  evidence-observed:
    backgroundColor: "{colors.observed-soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.square}"
    padding: "{spacing.inset}"
  evidence-synthetic:
    backgroundColor: "{colors.synthetic-soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.square}"
    padding: "{spacing.inset}"
  decision-tally:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.square}"
    padding: "2rem"
---

# Design System: Marketing Measurement Decision Studio

## Overview

**Creative North Star: "The Decision-Night Tally Desk"**

This is a calm executive evidence surface that makes decisions feel counted, called, held, or investigated in public view. Its warm paper ground, ruled lines, conspicuously unrounded panels, and editorial-scale decision calls avoid both a generic SaaS card grid and a blank spreadsheet. Evidence is the interface: a reader encounters the recommendation, its status, the underlying tally, and a readable record in that order.

The dashboard uses two deliberately distinct evidence lanes. Public observed evidence is mint-tinted and solid; synthetic planning evidence is violet-tinted and carries a faint diagonal hatch. Text labels repeat the distinction, so color never carries the meaning alone. Warm orange signals active investigation, while muted red is reserved for warnings and unavailable evidence.

**Key Characteristics:**

- Warm-paper dashboard with ink-navy rules and square shoulders.
- Newsreader display type for decision statements; IBM Plex Mono for all operational text, numbers, labels, and tables.
- Flat, ruled evidence records rather than rounded cards or decorative surfaces.
- Persistent disclosure of evidence type, source window, provenance, limitations, and chart-table alternatives.

## Colors

The palette is an archival desk: low-glare paper and dark drafting ink, with evidence hues serving classification rather than decoration.

### Primary

- **Tally Ink** (#152b31): Primary text, masthead rules, the dark decision-status panel, controls, and structural borders.
- **Public Evidence Green** (#1e4d45): Links, observed evidence identity, and the deepest observed chart bar.
- **Synthetic Evidence Violet** (#5b4c91): Synthetic evidence identity, selection color, loading color, and synthetic chart marks.
- **Investigation Signal** (#bb6c3f): Focus outline, chart emphasis, and the warm status accent in the decision tally.

### Secondary

- **Observed Mid Green** (#347568): Supporting observed chart mark between the dark observed green and the orange purchase mark.
- **Synthetic Mid Violet** (#8d77c2): Secondary synthetic scenario chart mark.
- **Tally Signal** (#f0b68e): High-contrast `INVESTIGATE` value and primary link hover within the ink panel.

### Tertiary

- **Alert Red** (#8a3f33): Warnings, error headings, and alert outlines only.
- **Alert Wash** (#f1ddd4): The warning panel fill behind Alert Red.

### Neutral

- **Warm Paper** (#f5f0e6): Page and chart background; the base surface across every route.
- **Deep Paper** (#e8dfcf): Available as the darker paper register.
- **Observed Mint** (#d5e2dc): Solid public-observed evidence lane.
- **Synthetic Lilac** (#e1dcf0): Synthetic lane base under its diagonal hatch.
- **Soft Ink** (#40585d): Supporting copy, captions, and footer text.
- **Rule Gray** (#9f988b): Structural rules, table dividers, and dashed disclosure separators.
- **Chart Grid** (#c9c1b1): Low-emphasis Plotly gridlines.
- **Field Paper** (#fffaf0): Number-input fill.

**The Evidence Lane Rule.** Never collapse public and synthetic evidence into the same unmarked surface. Public evidence is solid mint; synthetic evidence is lilac with a diagonal hatch, and both must retain their explicit text label.

**The Signal Rule.** Orange marks attention and focus; red marks a warning. Neither is a general accent or a decorative background.

## Typography

**Display Font:** Newsreader (with Georgia, serif fallback)

**Body and Label Font:** IBM Plex Mono (with Menlo, monospace fallback)

**Character:** Large, compact Newsreader statements make the decision feel editorial and consequential. IBM Plex Mono then turns every supporting statement into legible evidence: metadata, tables, navigation, controls, and numeric labels all read as a precise record rather than marketing copy.

### Hierarchy

- **Display** (700, `clamp(3.4rem, 8vw, 6rem)`, 0.92, -0.035em): Main route decision title; capped at 9ch on desktop and 11ch on mobile to force a tall, declarative call.
- **Headline** (700, `clamp(1.65rem, 3vw, 2.7rem)`, 1.05, -0.02em): Chart records, evidence-lane heading, state titles, and scenario labels.
- **Decision call** (700, `clamp(1.45rem, 2.6vw, 2.2rem)`, 1.15): The recommendation beside the h1.
- **Body** (400, 1rem, 1.55): Explanations and supporting operational context; paragraphs are capped at 72ch.
- **Label** (600, 0.78rem, 1.55, 0.08em, uppercase where used): Tally status and other compressed operational labels. Navigation uses the same mono face at 0.78rem.

**The Record Type Rule.** Keep explanatory, navigational, and numerical UI in IBM Plex Mono. Newsreader belongs to decisions and section-level evidence calls, not to controls or metadata.

## Layout

The desktop page is centered at `min(100%, 92rem)` with `clamp(1rem, 4vw, 4.5rem)` inline page padding and `clamp(2rem, 5vw, 5rem)` top spacing. A two-column masthead places the wordmark against a wrapping route rail. The decision header is an asymmetric two-column composition (`0.82fr / 1.18fr`): the constrained display title faces a ruled decision statement.

The summary’s signature lead is a second two-column evidence record, `0.55fr / 1.45fr`, with a 26rem minimum height. The ink decision tally occupies the narrow first column; the observed chart record occupies the wide second column. Evidence lanes sit side by side at equal width, separated by a one-pixel ink seam. Chart records run full width beneath a simple title-description grid and always end in a collapsed table alternative.

At 760px and below, masthead, decision header, summary lead, record headings, scenario controls, and evidence lanes become one column. The mobile tally keeps an 18rem minimum height; the navigation wraps rather than becoming a hidden menu. Footer content stacks vertically.

## Elevation & Depth

This is a flat system. It uses no box shadows, gradients, or rounded floating cards. Depth comes from ink rules, a dark-to-paper column split, bordered evidence fields, and the synthetic lane’s quiet repeating diagonal hatch (`10px` transparent intervals with a one-pixel violet mark). Tables and methodology disclosures gain hierarchy through rule weight and dashed separators, not surface lift.

The only motion is the `tally-arrive` clipping reveal on loading content and a 140ms ease-out route-focus note. Under reduced motion, smooth scrolling, animations, and transitions collapse to 0.01ms.

**The Flat Record Rule.** Add hierarchy with rules, contrast, and space—not shadows, glass effects, or elevated cards.

## Shapes

All controls and panels have square corners (`border-radius: 0`). One-pixel ink or rule-gray lines define edges; state panels use paired `2px double` ink rules. The synthetic evidence panel is the only patterned silhouette, and its hatch is a semantic support for the explicitly labeled synthetic state. Focus is a conspicuous `3px` orange outline offset by `4px`.

## Components

### Buttons

Precise, square operational controls.

- **Shape:** Square (0 radius), 1px ink border, and at least 44px height.
- **Primary:** Ink background with warm-paper text; `0.7rem 1rem` padding.
- **Hover / Focus:** Hover changes the fill to Public Evidence Green. Keyboard focus uses the 3px Investigation Signal outline with 4px offset.
- **Disabled:** Preserves the square form and drops to 0.62 opacity with a not-allowed cursor.

### Evidence Lanes

Evidence classification is a first-class component, never an afterthought.

- **Public observed:** Observed Mint fill, solid treatment, and a Public GA4 evidence label.
- **Synthetic:** Synthetic Lilac fill plus a low-contrast diagonal hatch and a Synthetic integration demonstration label.
- **Structure:** Square panel, ink border, `1.3rem 1.4rem` inset, a compact window line, and a native disclosure for source, provenance, and limitations.

### Decision Tally / Callout

- **Shape:** Square ink column with no shadow; minimum 18rem on mobile and vertically centered content.
- **Content:** Small spaced status label, an oversized Tally Signal value, and an underlined warm-paper evidence link.
- **Usage:** The summary’s decision state only; it pairs with, rather than replaces, the chart record.

### Charts and Tables

- **Chart field:** Warm Paper plot background with transparent outer paper, ink text, and Chart Grid lines. Observed charts use green plus the orange purchase emphasis; synthetic charts use violet.
- **Alternative:** Every chart is followed by a dashed-top native disclosure labelled “View evidence table.”
- **Table:** Full-width, tabular numerals, uppercase 0.76rem headers, and single rule-gray row dividers; horizontal overflow remains available on narrow screens.

### Inputs / Fields

- **Style:** Field Paper fill, 1px ink border, square corners, 44px minimum height, and `0.7rem` inner padding.
- **Focus:** Same 3px orange, 4px-offset focus outline as buttons.
- **Scenario control:** A ruled three-column field/control strip that becomes a vertical sequence on mobile.

### Navigation

- **Style:** Border-bottomed paper masthead with mono 0.78rem links and a wrapping horizontal route rail.
- **Default / active:** Ink link text; active route receives a 1px ink underline and weight 600. Hover changes the underline to Alert Red.
- **Focus note:** Focusing a route reveals a fixed ink note near the rail with warm-paper text; it appears over 140ms and is fully reduced-motion safe.

## Do's and Don'ts

- Do lead each route with a decision call, its next action, and a visible evidence boundary.
- Do use Newsreader only for decisions, section headings, and prominent labels; keep operational text and data in IBM Plex Mono.
- Do preserve square edges, one-pixel rules, and open paper space.
- Do give every chart its native table alternative and every evidence strip its provenance disclosure.
- Do pair the observed mint lane with explicit public-observed language, and the hatched lilac lane with explicit synthetic language.
- Do retain the orange 3px visible focus outline and reduced-motion overrides.
- Don't use pill controls, rounded SaaS cards, shadows, gradients, or decorative glass treatments.
- Don't use evidence color without the corresponding written evidence label and, for synthetic evidence, the patterned distinction.
- Don't treat attribution visualization as causal proof; retain the alert-language treatment where attribution appears.
- Don't make old public evidence appear current or make synthetic planning records appear observed.
