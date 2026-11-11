"""Portable reader report. This JSON schema is not a device export format."""

from pathlib import Path
import copy, json
from measurements import analyze


def _value(value):
    return value.get() if callable(getattr(value, "get", None)) else value


def build_report(viewer):
    start = max(0, int(viewer.start))
    end = min(viewer.n, int(viewer.end) + 1)
    active = {
        name: values
        for name, values in viewer.channels.items()
        if _value(viewer.visible[name])
    }
    dt = viewer.meta.get("calibration", {}).get("sample_interval_s_candidate")
    computed = getattr(viewer, "_report_measurements", None)
    from scope_controls import trigger_info

    return {
        "trigger_panel": trigger_info(viewer.meta),
        "format": "dpos350p-reader-report",
        "schema_version": 1,
        "source_filename": viewer.filename.name,
        "metadata": copy.deepcopy(viewer.meta),
        "view": {
            "sample_start_inclusive": start,
            "sample_end_exclusive": end,
            "units": viewer.units,
            "time_origin": viewer.time_origin,
            "scope_layout": viewer.scope_layout,
            "channel_display_positions": dict(viewer.display_positions),
            "channel_display_scales": dict(getattr(viewer, "scales", {})),
            "visible_channels": list(active),
            "measurement_bar": list(getattr(viewer, "measurement_order", [])),
            "trigger_level_visible": (
                _value(viewer.show_trigger_level)
                if hasattr(viewer, "show_trigger_level")
                else False
            ),
            "x_cursor_samples": (
                list(viewer.delta_cursors) if viewer.delta_cursors is not None else None
            ),
            "y_cursor_channel": _value(viewer.y_channel),
            "y_cursor_levels": (
                list(viewer.y_cursors) if viewer.y_cursors is not None else None
            ),
        },
        "visible_sample_measurements": (
            computed
            if computed is not None
            else {
                name: analyze(values[start:end], dt) for name, values in active.items()
            }
        ),
        "cursor_readout": _value(viewer.cursor_readout),
        "limitations": [
            "Reader-generated report, not a firmware-compatible file",
            "Raw waveform samples are exported separately with Save CSV",
            "Stored scope readouts and recomputed visible-sample measurements have different provenance",
        ],
    }


def export_report(viewer, path):
    Path(path).write_text(
        json.dumps(build_report(viewer), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
