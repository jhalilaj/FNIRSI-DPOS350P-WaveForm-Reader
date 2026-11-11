# FNIRSI DPOS350P Offline Reader

A native Windows waveform viewer built with **PySide6 (Qt Widgets) and PyQtGraph**. It reads FNIRSI waveform WAV files and their numeric settings directly; screenshots are optional previews, never a source of samples or measurements.

## Screenshots

Real included waveform capture, decoded directly from its WAV file.

![Dual-channel waveform viewer](images/waveform-viewer.png)

X/Y cursors with channel-specific Y-band average and interval statistics:

![Cursor analysis](images/cursor-analysis.png)

## Run

- **Windows build:** open `DPOS350P-Reader.exe` inside the complete Qt build folder. Keep `_internal` beside it. The Qt build is separate from the earlier legacy executable.
- **Source:** Python **3.11+**. Run `Install-Dependencies.bat` once, then `Open-Viewer.bat`. Or create a virtual environment, install `requirements.txt`, and run `python app.py`.
- `Open-Example.bat` opens the included dual-channel reference capture.

Dependencies are limited to PySide6 Essentials, PyQtGraph and NumPy. The decoder and measurement algorithms still use the Python standard library. Qt WebEngine, QML and web servers are not used. Optional legacy CLI plotting requires Matplotlib and Pillow separately.

## Interface

- **File:** Open, persistent Recent files, Ctrl+O, and file drag-and-drop.
- **View:** zoom, wheel zoom, drag to pan, Fit (Ctrl+0), Reset view, reset channel positions, and restore saved scope view.
- **Channels:** visibility, Y-channel selection, raw/inferred volts, per-channel display scales and draggable zero lines/numbered channel markers. Scale and position changes do not alter sample values.
- **Analysis:** visible-sample measurements, compact channel-selectable F/period/Vpp/RMS panel, configurable measurement bar and saved scope measurement order.
- **Cursors:** movable X pairs (Δt, one-cycle 1/|Δt|, interval extrema/mean), Y pairs (ΔV and visible-sample band statistics), and a single-sample cursor. Click the cursor overlay's statistics link for full readouts. X/Y pairs may coexist. Drag their lines or labeled rectangles to adjust; waveform clicks do not place X/Y cursors. The card shows the selected Y channel and its visible-sample band average.
- **Math:** CH1 − CH2 in physical units when both channels and conversion are available. Display offsets do not affect subtraction.
- **Trigger:** saved source, edge and inferred level; optional level line; approximate marker time origin.
- **Preview:** the original embedded thumbnail, accessible from the sidebar.
- **Exports:** complete current channels to CSV (including enabled math); current plot/readouts to PNG or SVG; reader JSON with metadata, view/cursors and measurements. JSON reports are not device-loadable files.

The left amplitude axis belongs to the selected Y channel in **Scope layout**, where each channel has independent scale/zero settings. **Physical overlay** uses one shared physical axis. The compact measurement panel has its own channel selector.

Loading, analysis, CSV writing and JSON generation run in background jobs. Plot items remain in place while panning; PyQtGraph clips to the visible range and uses peak downsampling. Stale load/analysis results cannot replace newer state. Persistence stays disabled because static WAV files do not contain live acquisition history.

## Support and limits

Firmware inspection supports the directory, scalar serialization, channel packing and numeric settings. The current observed-layout profile matches 24 supplied captures, including CH2-only and dual-channel files. Seven reference captures cover zero, DC and nominal 1 kHz square waves. Inconsistent or unrecognized settings remain raw-only.

This is an unofficial **1X** reader. Physical accuracy, exact hardware trigger timing, additional acquisition modes and multi-firmware compatibility are not claimed. Original captures 4/10/11 and 10X/100X validation remain deferred. Frequency, pulse widths and rise/fall values computed by the reader are offline estimates; stored instrument readouts may include grouped processing and multiple measurement updates. Rise/fall estimates require at least two sample intervals.

BMP files are screenshots. The firmware's reduced CAP profiles are inventoried but not supported without real-file validation. The illustrative waveform and numbers in the UI design reference are never used as decoded data.

## Development

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
.venv\Scripts\python -m unittest discover -s . -p "test*.py"
```

The suite includes 71 decoder/measurement/export-contract tests and 11 Qt interaction tests: **82 passing** on the development machine. Qt tests cover value preservation, cursors, math, saved view, recent asynchronous loads, invalid input, raw fallback, resize, all exports and event-loop activity during a larger capture load. No clean-machine or physical-calibration claim is made.

Build Windows with PyInstaller:

```powershell
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\python -m PyInstaller --noconfirm DPOS350P-Reader.spec
```

The one-folder build excludes unused browser/QML modules and the old Tk GUI. The existing local executable predates the latest cursor UI edits; rebuild it before attaching a Windows binary to a release. Check it with `DPOS350P-Reader.exe --self-test examples\reference check.json`; this explicit developer command creates its check artifacts. No additional versioned ZIP is generated by normal editing or testing.

Core files: `fnirsi_decode.py`, `calibration.py`, `timing.py` and `measurements.py`. Qt UI: `viewer.py`, `qt_theme.py`; background capture/analysis adapter: `qt_capture.py`. Exports: `image_export.py`, `report_export.py`. Launch/build: `app.py`, `requirements.txt`, `DPOS350P-Reader.spec`.

The interface follows the supplied ribbon/sidebar/card design with native window controls. It is not claimed pixel-perfect: native fonts/window chrome vary, and real captures differ from the illustration. The detailed cursor statistics are available through the overlay link rather than permanently covering the graph.

Licensed under the [MIT License](LICENSE). This unofficial reader is not affiliated with FNIRSI; the license covers this project's code, not vendor firmware, documentation or trademarks.
