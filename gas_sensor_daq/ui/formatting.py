import math


def finite_values(values):
    return [
        value
        for value in values
        if isinstance(value, (int, float)) and math.isfinite(value)
    ]


def format_number(value, suffix="", precision=2):
    if isinstance(value, (int, float)) and math.isfinite(value):
        return f"{value:.{precision}f}{suffix}"

    return "OPEN" if suffix == " Ohm" else "--"
