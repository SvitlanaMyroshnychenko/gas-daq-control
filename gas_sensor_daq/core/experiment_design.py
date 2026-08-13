"""Flow profile and validation rules shared by the experiment schedule."""

import math
import re


FLOW_UNIT = "mln/min"
DEFAULT_TARGET_TOTAL_FLOW = 150.0
FLOW_TOTAL_TOLERANCE = 0.01
_DURATION_PATTERN = re.compile(
    r"((?:0|[1-9]\d*)(?:\.\d+)?)\s*(s|min)",
    re.IGNORECASE,
)


def rack_capacity(nodes):
    """Return the installed rack's theoretical capacity in normalized mL/min."""
    return sum(float(node.capacity_mln_min) for node in nodes)


def flow_matches_target(total_flow, target_flow):
    """Compare summed MFC setpoints to the configured continuous mixture flow."""
    return math.isclose(
        float(total_flow),
        float(target_flow),
        rel_tol=0,
        abs_tol=FLOW_TOTAL_TOLERANCE,
    )


def calculate_mixture_setpoints(target_total, rh_percent, mfc1, mfc2, mfc3, mfc5):
    """Build a six-MFC mixture from the calculator inputs.

    MFC4 supplies the humid-air share. MFC6 receives the remaining dry-air
    flow after humid air, analyte MFCs, and the user-selected MFC5 split.
    """
    target_total = float(target_total)
    rh_percent = float(rh_percent)
    inputs = {1: float(mfc1), 2: float(mfc2), 3: float(mfc3), 5: float(mfc5)}
    if not math.isfinite(target_total) or target_total <= 0:
        raise ValueError("Target total must be greater than zero.")
    if not math.isfinite(rh_percent) or not 0 <= rh_percent <= 100:
        raise ValueError("RH must be between 0 and 100%.")
    if any(not math.isfinite(value) or value < 0 for value in inputs.values()):
        raise ValueError("MFC flow values must be finite and non-negative.")

    humid_air = target_total * rh_percent / 100
    mfc6 = target_total - humid_air - sum(inputs.values())
    return {1: inputs[1], 2: inputs[2], 3: inputs[3], 4: humid_air, 5: inputs[5], 6: mfc6}


def parse_duration_seconds(raw_value):
    """Return a duration in seconds, requiring an explicit ``s`` or ``min`` unit."""
    if not raw_value:
        return None

    match = _DURATION_PATTERN.fullmatch(str(raw_value).strip().replace(",", "."))
    if match is None:
        return None

    value = float(match.group(1))
    return value if match.group(2).lower() == "s" else value * 60
