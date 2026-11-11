# Trigger-marker timing and viewer update

The trigger origin is derived from the scope's saved marker coordinates. It is explicitly approximate, not a claim about the physical threshold-crossing instant.

Observed fields (signed 64-bit big-endian):
- Display marker displacement: 0x17E; divide by display timebase at 0x190 to obtain horizontal pixel displacement.
- Retained capture marker displacement: 0x1C8; divide by capture timebase at 0x1AF to obtain retained pixel displacement.

    display_marker_pixel = 475 + display_displacement / display_timebase
    capture_marker_pixel = 475 + capture_displacement / capture_timebase
    marker_sample = capture_marker_pixel * samples_per_pixel
    marker_relative_time = (sample_index - marker_sample) * sample_interval

Display positions were compared against green marker pixels in all 24 embedded previews. Maximum discrepancy was 0.635 preview pixels (203-pixel-wide images). This supports the marker-coordinate interpretation; it does not independently establish subpixel trigger accuracy. Square-wave threshold crossings differ slightly from the marker-based sample index. The implementation does not guess away that difference or automatically snap to a signal edge.

The retained marker must be used for original samples. Original file 9, for example, has a shifted display marker but a centered retained marker. An out-of-range or unknown retained marker disables marker-origin selection rather than clamping it into view.

Viewer changes:
- Time origin toggles first sample / trigger marker.
- Green marker line shows its location in the current viewport.
- Voltage-mode axis and CSV exports use the selected origin.
- Cursor readout includes time relative to the selected origin.
- Save image exports the current visible plot as a standalone SVG, with filename, units and time-origin annotations. SVG can be opened in a browser or vector editor.
- Toolbar wraps into two rows at the default window width.

CLI example:

    python fnirsi_decode.py examples/reference/7.wav --calibrated --time-origin "trigger marker" --out decoded

Validation: 17 unit tests pass; all seven reference-signal checks pass; all 24 preview-marker comparisons pass. Tk smoke checks cover marker selection, calibrated/raw switching, zoom, cursor, and well-formed SVG output. Existing single/dual-channel viewer load checks still pass.

A sample SVG is in reference-validation/viewer-example.svg. Detailed marker comparisons are in reference-validation/trigger-marker-checks.json. Deferred items are recorded in TODO.md.
