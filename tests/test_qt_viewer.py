"""Qt interaction regression tests; core decoder tests remain framework independent."""

import os, sys, time, json, csv, struct, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QListWidget
    from PySide6.QtCore import QTimer, QCoreApplication, QEvent
    from PySide6.QtTest import QTest
    from ui.viewer import Viewer
    from app import wait_idle
    from ui.qt_capture import load_capture

    QT_AVAILABLE = True
except ModuleNotFoundError:
    QT_AVAILABLE = False
from decoder.fnirsi_decode import decode, channel_samples
from decoder.calibration import volts
from decoder.measurements import analyze


@unittest.skipUnless(QT_AVAILABLE, "Install requirements.txt for Qt interaction tests")
class QtViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.root = Path(__file__).parent
        self.config = tempfile.TemporaryDirectory(dir=self.root)
        self.viewer = Viewer(Path(self.config.name) / "settings.ini")
        self.viewer.show()
        self.app.processEvents()
        self.viewer.load_sync(self.root / "fixtures/reference/7.wav")
        wait_idle(self.viewer)

    def tearDown(self):
        self.viewer.close()
        self.viewer.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.config.cleanup()

    def test_identical_decode_calibration_and_measurements(self):
        v = self.viewer
        meta, raw = decode(v.data)
        expected = volts(meta, channel_samples(meta, raw))
        self.assertEqual(v.channels, expected)
        for name, values in expected.items():
            self.assertEqual(v.measurements[name], analyze(values, v.dt()))

    def test_scale_positions_math_and_raw_preserve_samples(self):
        v = self.viewer
        original = {k: list(a) for k, a in v.channels.items()}
        v.scale_boxes["CH1"].setValue(2)
        v.position_changed("CH1", 4)
        self.assertEqual(v.channels, original)
        self.assertAlmostEqual(
            v.from_display_y("CH1", v.to_display_y("CH1", 0.35)), 0.35
        )
        v.toggle_math()
        wait_idle(v)
        self.assertEqual(
            v.channels["MATH"],
            [a - b for a, b in zip(original["CH1"], original["CH2"])],
        )
        v.toggle_units()
        wait_idle(v)
        self.assertEqual(v.units, "raw")
        self.assertEqual(v.channels, v.raw_channels)
        v.toggle_units()
        wait_idle(v)
        self.assertEqual(v.channels, original)

    def test_movable_x_and_y_cursors_and_single(self):
        v = self.viewer
        v.set_cursor_mode("x")
        v.x_cursor_moved(0, v.sample_to_x(100))
        v.x_cursor_moved(1, v.sample_to_x(1100))
        wait_idle(v)
        self.assertIn("one cycle", v.cursor_readout)
        self.assertEqual([int(x) for x in v.delta_cursors], [100, 1100])
        v.set_cursor_mode("y")
        v.y_cursor_moved(0, v.to_display_y(v.y_channel, -2.1))
        v.y_cursor_moved(1, v.to_display_y(v.y_channel, -1.8))
        wait_idle(v)
        self.assertIn("Y CH1", v.cursor_readout)
        self.assertIn("AVG", v.cursor_readout)
        v.set_cursor_mode("single")
        v.single_line.setValue(v.sample_to_x(123))
        v.single_cursor_moved(v.single_line)
        v.schedule_analysis()
        wait_idle(v)
        self.assertIn("Sample 123", v.cursor_readout)
        self.assertIsNone(v.delta_cursors)

    def test_scope_selection_reorder_dialog(self):
        v = self.viewer
        v.configure_measurement_bar()
        dialog = next(
            d
            for d in v.findChildren(QDialog)
            if d.windowTitle() == "Customize measurement bar"
        )

        def button(text):
            return next(b for b in dialog.findChildren(QPushButton) if b.text() == text)

        button("Use scope selection").click()
        wait_idle(v)
        self.assertEqual(
            v.measurement_order,
            [("CH2", "max"), ("CH2", "min"), ("CH2", "avg"), ("CH2", "freq")],
        )
        listing = dialog.findChild(QListWidget)
        listing.setCurrentRow(0)
        button("Down").click()
        self.assertEqual(v.measurement_order[1], ("CH2", "max"))
        button("Remove").click()
        self.assertEqual(len(v.measurement_order), 3)
        button("Defaults").click()
        button("Close").click()
        wait_idle(v)

    def test_zoom_origin_and_saved_view(self):
        v = self.viewer
        original = list(v.channels["CH1"])
        span = v.end - v.start
        v.zoom(0.5)
        wait_idle(v)
        self.assertLess(v.end - v.start, span * 0.6)
        v.toggle_origin()
        wait_idle(v)
        self.assertAlmostEqual(v.x_to_sample(v.sample_to_x(555)), 555)
        v.scale_boxes["CH1"].setValue(3)
        v.restore_scope_view()
        wait_idle(v)
        self.assertEqual(v.scales["CH1"], 1)
        self.assertEqual(v.channels["CH1"], original)
        self.assertIsNone(v.delta_cursors)

    def test_exports_match_view_and_values(self):
        v = self.viewer
        v.toggle_math()
        v.set_cursor_mode("x")
        wait_idle(v)
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            root = Path(directory)
            v.save_csv(root / "data.csv")
            v.save_report(root / "report.json")
            v.save_image(root / "view.svg")
            v.save_image(root / "view.png")
            wait_idle(v)
            report = json.loads((root / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["view"]["x_cursor_samples"], v.delta_cursors)
            self.assertIn("MATH", report["visible_sample_measurements"])
            with (root / "data.csv").open(encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
            self.assertEqual(len(rows), v.n + 1)
            self.assertIn("MATH_volts_inferred", rows[0])
            self.assertAlmostEqual(float(rows[1][-1]), v.channels["MATH"][0])
            self.assertIn("<svg", (root / "view.svg").read_text(encoding="utf-8"))
            self.assertGreater((root / "view.png").stat().st_size, 1000)

    def test_invalid_async_load_keeps_current_capture(self):
        v = self.viewer
        previous = v.filename
        with tempfile.TemporaryDirectory(dir=self.root) as directory, patch(
            "ui.viewer.QMessageBox.warning"
        ) as warning:
            path = Path(directory) / "bad.wav"
            path.write_bytes(b"bad")
            v.load(path)
            wait_idle(v)
            self.assertEqual(v.filename, previous)
            self.assertTrue(v.last_error)
            warning.assert_called_once()

    def test_unknown_geometry_remains_raw_and_shows_no_trigger_level(self):
        v = self.viewer
        data = bytearray(v.data)
        data[0x4A:0x4C] = (96).to_bytes(2, "big")
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            p = Path(directory) / "unknown.wav"
            p.write_bytes(data)
            v.load_sync(p)
            wait_idle(v)
            self.assertEqual(v.units, "raw")
            self.assertFalse(v.trigger_line.isVisible())
            self.assertFalse(v.scale_boxes["CH1"].isEnabled())

    def test_latest_async_open_wins(self):
        v = self.viewer
        v.load(self.root / "fixtures/reference/6.wav")
        v.load(self.root / "fixtures/reference/7.wav")
        wait_idle(v)
        self.assertEqual(v.filename.name, "7.wav")
        self.assertEqual(set(v.channels), {"CH1", "CH2"})

    def test_resize_and_disabled_persistence(self):
        v = self.viewer
        v.resize(1100, 700)
        self.app.processEvents()
        self.assertGreater(v.plot.width(), 500)
        self.assertGreater(v.plot.height(), 200)
        self.assertEqual(set(v.scale_boxes), {"CH1", "CH2", "MATH"})

    def test_large_load_keeps_event_loop_alive(self):
        v = self.viewer
        data = bytearray(v.data)
        header = list(struct.unpack_from(">7I", data))
        offset = header[4]
        payload = data[offset:]
        half = len(payload) // 2
        factor = 16
        data[offset:] = payload[:half] * factor + payload[half:] * factor
        header[5] = len(data) - offset
        header[6] = len(data)
        struct.pack_into(">7I", data, 0, *header)
        struct.pack_into(">I", data, 0x120, v.n * factor)
        ticks = []
        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(1))
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            path = Path(directory) / "large.wav"
            path.write_bytes(data)
            timer.start()
            v.load(path)
            wait_idle(v, 60)
            timer.stop()
            self.assertGreater(len(ticks), 5)
            self.assertEqual(v.n, 23752 * factor)
            self.assertGreater(v.curves["CH1"].opts["autoDownsample"], 0)


if __name__ == "__main__":
    unittest.main()
