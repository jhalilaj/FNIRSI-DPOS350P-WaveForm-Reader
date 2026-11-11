"""Small Qt-independent capture adapter; decoding and measurement algorithms stay unchanged."""

from pathlib import Path
import numpy as np
from fnirsi_decode import decode, channel_samples
from calibration import volts
from measurements import analyze
from cursor_analysis import x_selection, y_selection
from scope_controls import measurement_text


def load_capture(path):
    path = Path(path)
    data = path.read_bytes()
    meta, samples = decode(data)
    raw = channel_samples(meta, samples)
    try:
        physical = volts(meta, raw)
    except ValueError:
        physical = None
    arrays = {"raw": {k: np.asarray(v, dtype=float) for k, v in raw.items()}}
    if physical is not None:
        arrays["V inferred"] = {
            k: np.asarray(v, dtype=float) for k, v in physical.items()
        }
    return dict(
        filename=path,
        data=data,
        meta=meta,
        raw_channels=raw,
        physical_channels=physical,
        arrays=arrays,
        n=max(map(len, raw.values())),
    )


def analyze_view(
    channels, start, end, dt, order, units, x_pair, y_pair, y_channel, single_index=None
):
    measurements = {
        name: analyze(values[start:end], dt) for name, values in channels.items()
    }
    unit = "V" if units == "V inferred" else "counts"
    bar = [
        f"{name} " + measurement_text(key, measurements[name], unit)
        for name, key in order
        if name in measurements
    ]
    cursor = []
    y_band = None
    if single_index is not None and channels:
        index = max(0, min(len(next(iter(channels.values()))) - 1, int(single_index)))
        cursor.append(
            f"Sample {index:,}  "
            + "  ".join(
                f"{name}: {values[index]:.6g} {unit}"
                for name, values in channels.items()
            )
        )
    if x_pair is not None and channels:
        a, b = x_pair
        m = x_selection(next(iter(channels.values())), a, b, dt)
        frequency = m["one_cycle_hz"]
        cursor.append(
            f"Δt {m['delta_s']:.6g} s  |  1/|Δt| {frequency:.6g} Hz (one cycle)"
            if frequency
            else "Δt / one-cycle frequency unavailable"
        )
        for name, values in channels.items():
            selected = x_selection(values, a, b, dt)
            ia, ib = [max(0, min(len(values) - 1, int(i))) for i in (a, b)]
            cursor.append(
                f"X {name}: MIN {selected['minimum']:.6g}  MAX {selected['maximum']:.6g}  AVG {selected['mean']:.6g} {unit}  Δ{unit} {values[ib]-values[ia]:.6g}"
            )
    if y_pair is not None and y_channel in channels:
        a, b = y_pair
        m = y_selection(channels[y_channel][start:end], a, b)
        y_band = dict(m, channel=y_channel)
        text = f'Y {y_channel}: Δ{unit} {b-a:.6g}  N={m["count"]}'
        text += (
            f'  MIN {m["minimum"]:.6g} MAX {m["maximum"]:.6g} AVG {m["mean"]:.6g} {unit}'
            if m["count"]
            else "  No visible samples in this band"
        )
        cursor.append(text)
    return dict(measurements=measurements, bar=bar, cursor=cursor, start=start, end=end, y_band=y_band)
