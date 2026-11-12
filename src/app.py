"""Qt entry point and packaged-build self-check."""

import json, sys, time
from pathlib import Path

VERSION = "1.0.1"


def wait_idle(viewer, timeout=30):
    from PySide6.QtCore import QCoreApplication

    deadline = time.monotonic() + timeout
    while viewer._jobs or viewer.analysis_timer.isActive():
        QCoreApplication.processEvents()
        time.sleep(0.01)
        if time.monotonic() > deadline:
            raise TimeoutError("Background task did not complete")
    QCoreApplication.processEvents()


def smoke(source, report):
    from PySide6.QtWidgets import QApplication
    from ui.viewer import Viewer

    app = QApplication.instance() or QApplication(sys.argv)
    from PySide6.QtGui import QIcon

    app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "app.ico")))
    app.setStyle("Fusion")
    window = Viewer()
    window.show()
    app.processEvents()
    rows = []
    for path in sorted(Path(source).glob("*.wav")):
        window.load_sync(path)
        wait_idle(window)
        window.zoom(0.5)
        window.fit()
        window.toggle_delta()
        wait_idle(window)
        if window.units == "V inferred":
            window.toggle_origin()
            window.toggle_origin()
            if "CH1" in window.channels and "CH2" in window.channels:
                window.toggle_math()
                window.toggle_math()
        wait_idle(window)
        rows.append(
            dict(
                file=path.name,
                channels=list(window.channels),
                units=window.units,
                samples_per_channel=window.n,
            )
        )
    if not rows:
        raise ValueError("No WAV files found")
    from exports.image_export import export_image

    export_image(window, Path(report).with_suffix(".svg"))
    window.grab().save(str(Path(report).with_suffix(".png")))
    Path(report).write_text(
        json.dumps(
            dict(
                version=VERSION,
                framework="PySide6 + PyQtGraph",
                frozen=bool(getattr(sys, "frozen", False)),
                passed=True,
                captures=rows,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    window.close()
    app.processEvents()


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--self-test":
        try:
            smoke(sys.argv[2], sys.argv[3])
        except Exception as exc:
            import traceback

            Path(sys.argv[3]).write_text(
                json.dumps(
                    {
                        "passed": False,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            sys.exit(1)
    else:
        from PySide6.QtWidgets import QApplication
        from ui.viewer import Viewer

        app = QApplication(sys.argv)
        from PySide6.QtGui import QIcon

        app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "app.ico")))
        app.setStyle("Fusion")
        window = Viewer()
        window.show()
        if len(sys.argv) > 1:
            window.load(sys.argv[1])
        sys.exit(app.exec())
