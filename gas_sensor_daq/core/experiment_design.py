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


def parse_duration_seconds(raw_value):
    """Return a duration in seconds, requiring an explicit ``s`` or ``min`` unit."""
    if not raw_value:
        return None

    match = _DURATION_PATTERN.fullmatch(str(raw_value).strip().replace(",", "."))
    if match is None:
        return None

    value = float(match.group(1))
    return value if match.group(2).lower() == "s" else value * 60
