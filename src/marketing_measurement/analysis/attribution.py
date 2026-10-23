"""Deterministic descriptive attribution for compact, non-identifying paths.

Four rule-based models allocate one unit of credit per conversion:

* ``first_touch`` and ``last_touch``: all credit to one end of the path;
* ``linear``: equal credit to every touch;
* ``time_decay``: position decay with a half-life of one touch, so each earlier
  touch receives half the weight of the touch after it. The committed path extract
  has ordered touches but no timestamps, so this is a position-based stand-in for
  GA's 7-day time-decay rule.

Credits describe how a path is accounted for, not what caused the conversion.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import pandas as pd

AttributionModel = Literal["first_touch", "last_touch", "linear", "time_decay"]
ATTRIBUTION_MODELS: tuple[AttributionModel, ...] = (
    "first_touch",
    "last_touch",
    "linear",
    "time_decay",
)
_MODELS = frozenset(ATTRIBUTION_MODELS)
_INTERPRETATION = "descriptive attribution; not causal"

PATH_SEPARATOR = " > "
DIRECT_TOUCH = "(direct) / (none)"
#: The Google Merchandise Store's own domains. A session whose first source is one
#: of these is a self-referral (for example a session restarted on a subdomain), so
#: GA4 would normally list it as an unwanted referral.
INTERNAL_REFERRAL_DOMAIN = "googlemerchandisestore.com"
_SEARCH_ENGINES = frozenset({"google", "bing", "yahoo", "duckduckgo", "baidu"})
_SOCIAL_SOURCES = frozenset(
    {"facebook.com", "l.facebook.com", "m.facebook.com", "l.messenger.com"}
)
_VIDEO_SOURCES = frozenset({"youtube.com", "m.youtube.com", "creatoracademy.youtube.com"})


def attribution_credits(paths: pd.DataFrame, model: AttributionModel) -> pd.DataFrame:
    """Allocate one unit of descriptive credit per conversion across touches.

    ``paths`` must contain a non-identifying conversion label, channel, and either
    ``touch_number`` or ``touch_timestamp``.
    """
    if model not in _MODELS:
        raise ValueError(f"Unsupported attribution model: {model}")
    required = {"conversion_id", "channel"}
    missing = required.difference(paths.columns)
    if missing:
        raise ValueError(f"paths is missing required columns: {sorted(missing)}")
    if "touch_number" not in paths.columns and "touch_timestamp" not in paths.columns:
        raise ValueError("paths must include touch_number or touch_timestamp")

    order_columns = ["conversion_id"]
    order_columns.append(
        "touch_timestamp" if "touch_timestamp" in paths.columns else "touch_number"
    )
    ordered = paths.copy().sort_values(order_columns, kind="stable").reset_index(drop=True)
    if ordered["conversion_id"].isna().any() or ordered["channel"].isna().any():
        raise ValueError("conversion_id and channel cannot be missing")

    ordered["touch_position"] = ordered.groupby("conversion_id", sort=False).cumcount()
    ordered["touches_in_conversion"] = ordered.groupby("conversion_id", sort=False)[
        "conversion_id"
    ].transform("size")
    ordered["credit"] = _credits_for_model(ordered, model)
    ordered["interpretation"] = _INTERPRETATION

    if not _credit_sums_to_one(ordered):
        raise RuntimeError("Attribution credits must sum to one per conversion")
    return ordered


def is_internal_referral(touch: str) -> bool:
    """Return whether a ``source / medium`` touch is a store self-referral."""
    source, _, medium = touch.partition(" / ")
    return medium == "referral" and (
        source == INTERNAL_REFERRAL_DOMAIN
        or source.endswith("." + INTERNAL_REFERRAL_DOMAIN)
    )


def default_channel_group(touch: str) -> str:
    """Map a ``source / medium`` touch to a simplified GA4 default channel group.

    The rules follow GA4's published channel definitions for the values present in
    the public sample. Obfuscated (``<Other>``, ``(data deleted)``) and unattributed
    values fall to ``Unassigned`` unless the medium alone identifies the channel.
    """
    source, _, medium = touch.partition(" / ")
    if is_internal_referral(touch):
        return "Internal self-referral"
    if source == "(direct)" and medium in {"(none)", "(not set)"}:
        return "Direct"
    if medium in {"cpc", "ppc", "paidsearch"} and source in _SEARCH_ENGINES:
        return "Paid Search"
    if medium == "organic" or (source in _SEARCH_ENGINES and medium == "referral"):
        return "Organic Search"
    if medium == "email":
        return "Email"
    if medium == "affiliate":
        return "Affiliates"
    if source in _SOCIAL_SOURCES:
        return "Organic Social"
    if source in _VIDEO_SOURCES:
        return "Organic Video"
    if medium == "referral":
        return "Referral"
    return "Unassigned"


def expand_paths(
    paths: pd.DataFrame, *, exclude_internal_referrals: bool = False
) -> pd.DataFrame:
    """Turn aggregated ``channel_path`` rows into one row per weighted touch.

    ``paths`` holds ``channel_path`` (touches joined by ``" > "``) and
    ``converted_sessions``. With ``exclude_internal_referrals`` the store's own
    referral touches are removed, the usual GA4 unwanted-referral treatment; a path
    left empty becomes a single direct touch.
    """
    missing = {"channel_path", "converted_sessions"}.difference(paths.columns)
    if missing:
        raise ValueError(f"paths is missing required columns: {sorted(missing)}")
    rows: list[dict[str, object]] = []
    for path_index, (channel_path, weight) in enumerate(
        zip(paths["channel_path"], paths["converted_sessions"], strict=True)
    ):
        touches: Sequence[str] = str(channel_path).split(PATH_SEPARATOR)
        if exclude_internal_referrals:
            touches = [touch for touch in touches if not is_internal_referral(touch)]
            touches = touches or [DIRECT_TOUCH]
        rows.extend(
            {
                "conversion_id": f"observed_path_{path_index}",
                "channel": touch,
                "touch_number": touch_number,
                "conversion_weight": int(weight),
            }
            for touch_number, touch in enumerate(touches, start=1)
        )
    return pd.DataFrame(rows)


def weighted_credits(
    touches: pd.DataFrame, model: AttributionModel, *, by_channel_group: bool = False
) -> pd.Series:
    """Sum conversion-weighted credit per channel (or channel group), descending."""
    credits = attribution_credits(touches, model)
    weighted = credits["credit"] * credits["conversion_weight"]
    keys = credits["channel"]
    if by_channel_group:
        keys = keys.map(default_channel_group)
    totals = weighted.groupby(keys).sum().sort_values(ascending=False, kind="stable")
    totals.index.name = "channel_group" if by_channel_group else "channel"
    return totals


def _credits_for_model(frame: pd.DataFrame, model: AttributionModel) -> pd.Series:
    if model == "first_touch":
        return (frame["touch_position"] == 0).astype(float)
    if model == "last_touch":
        return (
            frame["touch_position"] == frame["touches_in_conversion"] - 1
        ).astype(float)
    if model == "linear":
        return 1.0 / frame["touches_in_conversion"]

    raw_weight = 0.5 ** (frame["touches_in_conversion"] - 1 - frame["touch_position"])
    return raw_weight / raw_weight.groupby(frame["conversion_id"], sort=False).transform("sum")


def _credit_sums_to_one(frame: pd.DataFrame) -> bool:
    totals = frame.groupby("conversion_id", sort=False)["credit"].sum()
    return bool(totals.sub(1.0).abs().le(1e-12).all())
