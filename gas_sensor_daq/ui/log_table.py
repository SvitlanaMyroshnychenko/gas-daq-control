from gas_sensor_daq.ui.formatting import format_number


def log_preview_values(data, event):
    return [
        data["timestamp"],
        f"{data['elapsed_s']:.1f}",
        format_number(data["resistance_ohm"], precision=2),
        f"{data.get('mfc1_actual_mln_min', 0.0):.2f}",
        f"{data.get('mfc2_actual_mln_min', 0.0):.2f}",
        f"{data.get('mfc3_actual_mln_min', 0.0):.2f}",
        f"{data.get('mfc4_actual_mln_min', 0.0):.2f}",
        f"{data.get('mfc5_actual_mln_min', 0.0):.2f}",
        f"{data.get('mfc6_actual_mln_min', 0.0):.2f}",
        event,
    ]
