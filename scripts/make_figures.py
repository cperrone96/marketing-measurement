"""Render the README figure from the reviewed findings summary.

The figure compares first-touch and last-touch credit by GA4 channel group, as
observed and with the store's self-referrals removed. It reads only
``data/derived/ga4_public_sample/findings_summary.json``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "data/derived/ga4_public_sample/findings_summary.json"
DEFAULT_OUTPUT = ROOT / "docs/figures/attribution_by_channel_group.png"

FIRST_TOUCH = "#2a78d6"
LAST_TOUCH = "#eb6834"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"
SHOWN_GROUPS = (
    "Organic Search",
    "Internal self-referral",
    "Referral",
    "Direct",
    "Unassigned",
    "Paid Search",
)


def _collapse(credits: dict[str, float]) -> dict[str, float]:
    """Keep the large groups and fold the rest into 'All other'."""
    collapsed = {group: credits.get(group, 0.0) for group in SHOWN_GROUPS}
    collapsed["All other"] = sum(
        value for group, value in credits.items() if group not in SHOWN_GROUPS
    )
    return collapsed


def render(output: Path) -> None:
    """Draw a two-panel dumbbell chart of first- versus last-touch credit."""
    attribution = json.loads(SUMMARY.read_text(encoding="utf-8"))["attribution"]
    total = attribution["eligible_converted_sessions"]
    panels = (
        ("As observed", attribution["channel_group_credits"]),
        (
            "Store self-referrals removed",
            attribution["channel_group_credits_excluding_self_referrals"],
        ),
    )
    groups = [*SHOWN_GROUPS, "All other"]
    positions = list(range(len(groups)))[::-1]

    plt.rcParams.update({"font.size": 10, "font.family": "DejaVu Sans"})
    figure, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True, sharex=True)
    figure.patch.set_facecolor(SURFACE)
    for axis, (title, credits) in zip(axes, panels, strict=True):
        first = _collapse(credits["first_touch"])
        last = _collapse(credits["last_touch"])
        axis.set_facecolor(SURFACE)
        for group, y in zip(groups, positions, strict=True):
            share_first = first[group] / total
            share_last = last[group] / total
            axis.plot([share_first, share_last], [y, y], color=GRID, linewidth=3, zorder=1)
            axis.scatter(
                share_first, y, s=40, color=FIRST_TOUCH, edgecolor=SURFACE,
                linewidth=1, zorder=2, label="First touch" if y == positions[0] else None,
            )
            axis.scatter(
                share_last, y, s=110, facecolor="none", edgecolor=LAST_TOUCH,
                marker="D", linewidth=2, zorder=3,
                label="Last touch" if y == positions[0] else None,
            )
        axis.set_title(title, loc="left", color=INK, fontsize=11, fontweight="bold")
        axis.xaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
        axis.grid(axis="x", color=GRID, linewidth=0.8)
        axis.set_axisbelow(True)
        axis.tick_params(colors=MUTED, length=0)
        for spine in axis.spines.values():
            spine.set_visible(False)
        axis.set_xlabel("Share of converted sessions credited", color=MUTED)
    axes[0].set_yticks(positions, groups, color=INK)
    axes[0].set_xlim(-0.01, 0.45)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles, labels, loc="upper right", ncol=2, frameon=False,
        bbox_to_anchor=(0.98, 1.0), labelcolor=INK,
    )
    figure.suptitle(
        f"Attribution by GA4 channel group, {total:,} converted sessions",
        x=0.01, ha="left", color=INK, fontsize=12, fontweight="bold",
    )
    figure.text(
        0.01, 0.005,
        "Google public GA4 ecommerce sample, conversions 2020-12-01 to 2021-01-31, "
        "30-day lookback. Descriptive, not causal.",
        color=MUTED, fontsize=8,
    )
    figure.tight_layout(rect=(0, 0.03, 1, 0.95))
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=150, facecolor=SURFACE, metadata={"Software": None})
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    render(parser.parse_args().output)


if __name__ == "__main__":
    main()
