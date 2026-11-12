"""Qt Widgets / PyQtGraph offline instrument viewer."""

import csv, sys
from html import escape
from pathlib import Path
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QToolButton,
    QPushButton,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QMenu,
    QFileDialog,
    QMessageBox,
    QDialog,
    QPlainTextEdit,
    QListWidget,
    QScrollArea,
    QSplitter,
)
import pyqtgraph as pg
from ui.qt_theme import STYLE, COLORS, icon, initialize_fonts
from ui.qt_capture import load_capture, analyze_view
from decoder.scope_controls import METRICS, trigger_info, measurement_text
from decoder.timing import origin_sample
from decoder.fnirsi_decode import extract_preview

pg.setConfigOptions(antialias=False, background="#070e13", foreground="#b5c4cf")


class JobSignals(QtCore.QObject):
    done = Signal(str, int, object)
    failed = Signal(str, int, str)


class Job(QtCore.QRunnable):
    def __init__(self, kind, token, fn):
        super().__init__()
        self.kind, self.token, self.fn = kind, token, fn
        self.signals = JobSignals()

    def run(self):
        try:
            self.signals.done.emit(self.kind, self.token, self.fn())
        except Exception as exc:
            self.signals.failed.emit(self.kind, self.token, str(exc))


class AmplitudeAxis(pg.AxisItem):
    def __init__(self, viewer):
        super().__init__("left")
        self.viewer = viewer

    def tickStrings(self, values, scale, spacing):
        return [
            f"{self.viewer.from_display_y(self.viewer.y_channel,v):.4g}" for v in values
        ]


class ScopePlot(pg.PlotWidget):
    pointClicked = Signal(float, float)
    resized = Signal()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.property("placeCursor"):
            p = self.plotItem.vb.mapSceneToView(
                self.mapToScene(event.position().toPoint())
            )
            hit = self.scene().items(self.mapToScene(event.position().toPoint()))
            if not any(
                isinstance(item, pg.InfiniteLine)
                or isinstance(item.parentItem(), pg.InfiniteLine)
                for item in hit
            ):
                self.pointClicked.emit(p.x(), p.y())
        super().mousePressEvent(event)


class ChannelMarker(pg.InfLineLabel):
    """Drag a channel or cursor badge across its line using existing signals."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Let the badge handle drags instead of its internal text item.
        self.textItem.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.textItem.setAcceptHoverEvents(False)
        self.setAcceptHoverEvents(True)

    def hoverEvent(self, event):
        draggable = self.line.movable and not event.isExit()
        if draggable:
            event.acceptDrags(Qt.MouseButton.LeftButton)
        self.line.setMouseHover(draggable)
        cursor = Qt.CursorShape.SizeVerCursor if self.line.angle == 0 else Qt.CursorShape.SizeHorCursor
        self.setCursor(cursor if draggable else Qt.CursorShape.ArrowCursor)

    def mouseDragEvent(self, event):
        if not self.line.movable or event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        event.accept()
        parent = self.line.parentItem()
        point = parent.mapFromScene(event.scenePos())
        if event.isStart():
            self._start_value = self.line.value()
            pressed = parent.mapFromScene(event.buttonDownScenePos())
            self._press_value = pressed.y() if self.line.angle == 0 else pressed.x()
        coordinate = point.y() if self.line.angle == 0 else point.x()
        self.line.setValue(self._start_value + coordinate - self._press_value)
        self.line.sigDragged.emit(self.line)
        if event.isFinish():
            self.line.sigPositionChangeFinished.emit(self.line)


class ScaleSpinBox(QDoubleSpinBox):
    def textFromValue(self, value):
        return f"{value:.6f}".rstrip("0").rstrip(".")


class ScopeCheckBox(QCheckBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked():
            option = QtWidgets.QStyleOptionButton()
            self.initStyleOption(option)
            rect = self.style().subElementRect(
                QtWidgets.QStyle.SubElement.SE_CheckBoxIndicator, option, self
            )
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            painter.setPen(QtGui.QPen(QtGui.QColor("#07121b"), 2))
            painter.drawPolyline(
                QtGui.QPolygonF(
                    [
                        QtCore.QPointF(rect.x() + 4, rect.y() + 8),
                        QtCore.QPointF(rect.x() + 7, rect.y() + 12),
                        QtCore.QPointF(rect.x() + 13, rect.y() + 4),
                    ]
                )
            )


class Viewer(QMainWindow):
    def __init__(self, settings_path=None):
        super().__init__()
        initialize_fonts()
        self.setWindowTitle("FNIRSI DPOS350P — Offline Replay")
        self.resize(1480, 900)
        self.setMinimumSize(1080, 680)
        self.setStyleSheet(STYLE)
        self.data = b""
        self.meta = {}
        self.filename = None
        self.channels = {}
        self.raw_channels = {}
        self.arrays = {}
        self.n = 0
        self.units = "raw"
        self.scope_layout = True
        self.display_positions = {}
        self.scales = {}
        self.time_origin = "first sample"
        self.start = 0.0
        self.end = 1.0
        self.cursor = None
        self.delta_cursors = None
        self.y_cursors = None
        self.y_channel = "CH1"
        self.cursor_axis = None
        self.cursor_next = 0
        self.math_enabled = False
        self.visible = {k: True for k in COLORS}
        self.show_trigger_level = True
        self.measurement_order = []
        self.measurement_custom = False
        self.live_readout = ""
        self.cursor_readout = ""
        self.trigger_readout = ""
        self._last_analysis_token = -1
        self._pending_image = None
        self.measurements = {}
        self.curves = {}
        self.zero_lines = {}
        self.x_lines = []
        self.y_lines = []
        self.single_line = None
        self._rendering = False
        self._load_token = 0
        self._analysis_token = 0
        self._jobs = {}
        self._export_token = 0
        self.last_error = ""
        self.pool = QtCore.QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        directory = (
            Path(sys.executable).parent
            if getattr(sys, "frozen", False)
            else Path(__file__).parents[2]
        )
        self.settings = QtCore.QSettings(
            str(settings_path or directory / "reader-settings.ini"),
            QtCore.QSettings.Format.IniFormat,
        )
        self.recent = list(self.settings.value("recent", []) or [])
        self.analysis_timer = QtCore.QTimer(self)
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(140)
        self.analysis_timer.timeout.connect(self.request_analysis)
        self._build_ui()
        self._build_menus()
        self.fit()
        try:
            import ctypes

            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(self.winId()), 20, ctypes.byref(value), 4
            )
        except (AttributeError, OSError):
            pass

    def _card(self, title, parent_layout):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(13, 12, 13, 13)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("cardTitle")
        layout.addWidget(heading)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#344550")
        layout.addWidget(line)
        parent_layout.addWidget(card)
        return layout

    def _button(self, layout, label, symbol, callback=None, menu=None, primary=False):
        b = QToolButton()
        b.setText(label)
        b.setIcon(icon(symbol))
        b.setIconSize(QtCore.QSize(23, 23))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        b.setMinimumSize(76, 59)
        b.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        if primary:
            b.setObjectName("openButton")
        if menu:
            b.setMenu(menu)
            b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        else:
            b.clicked.connect(callback)
        layout.addWidget(b)
        return b

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QWidget()
        header.setObjectName("header")
        h = QHBoxLayout(header)
        h.setContentsMargins(24, 10, 24, 10)
        logo = QLabel("FNIRSI")
        logo.setObjectName("brand")
        h.addWidget(logo)
        subtitle = QLabel("│   DPOS350P / Offline Replay")
        subtitle.setObjectName("subtitle")
        h.addWidget(subtitle)
        h.addStretch()
        badge = QLabel("OFFLINE  •  1X")
        badge.setObjectName("muted")
        h.addWidget(badge)
        outer.addWidget(header)
        ribbon = QWidget()
        ribbon.setObjectName("ribbon")
        r = QHBoxLayout(ribbon)
        r.setContentsMargins(16, 10, 16, 12)
        r.setSpacing(14)

        def group(title):
            f = QFrame()
            f.setObjectName("group")
            v = QVBoxLayout(f)
            v.setContentsMargins(5, 0, 14, 0)
            v.setSpacing(7)
            t = QLabel(title)
            t.setObjectName("groupTitle")
            v.addWidget(t)
            row = QHBoxLayout()
            row.setSpacing(7)
            v.addLayout(row)
            r.addWidget(f, 2 if "File" in title else 4 if "View" in title else 3)
            return row

        row = group("▱  File")
        self.open_button = self._button(
            row, "Open", "open", self.open_dialog, primary=True
        )
        self.recent_menu = QMenu(self)
        self._button(row, "Recent", "recent", menu=self.recent_menu)
        self.refresh_recent()
        row = group("⌕  View")
        self._button(row, "Zoom In", "zoom_in", lambda: self.zoom(0.5))
        self._button(row, "Zoom Out", "zoom_out", lambda: self.zoom(2))
        self._button(row, "Fit", "fit", self.fit)
        reset = QMenu(self)
        reset.addAction("Reset view", self.reset_view)
        reset.addAction("Reset channel positions", self.reset_positions)
        reset.addAction("Restore saved scope view", self.restore_scope_view)
        self._button(row, "Reset", "reset", menu=reset)
        row = group("⌁  Analysis")
        measure_menu = QMenu(self)
        measure_menu.addAction("All measurements…", self.measure)
        measure_menu.addAction(
            "Customize measurement bar…", self.configure_measurement_bar
        )
        self._button(row, "Measurements", "measure", menu=measure_menu)
        cursor_menu = QMenu(self)
        for label, mode in [
            ("X pair — time / frequency", "x"),
            ("Y pair — amplitude band", "y"),
            ("Single sample", "single"),
            ("Clear cursors", None),
        ]:
            cursor_menu.addAction(
                label, lambda checked=False, m=mode: self.set_cursor_mode(m)
            )
        self._button(row, "Cursor", "cursor", menu=cursor_menu)
        self.math_button = self._button(row, "Math", "math", self.toggle_math)
        self.math_button.setCheckable(True)
        self.math_button.setToolTip("CH1 − CH2 in physical units")
        row = group("⇧  Export")
        self._button(row, "Save CSV", "csv", self.save_csv)
        self._button(row, "Save Image", "image", self.save_image)
        self._button(row, "Report", "report", self.save_report)
        outer.addWidget(ribbon)
        body = QSplitter()
        body.setHandleWidth(10)
        outer.addWidget(body, 1)
        side = QScrollArea()
        side.setWidgetResizable(True)
        side.setMinimumWidth(232)
        side.setMaximumWidth(255)
        side.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        side.viewport().setStyleSheet("background:#0c1319")
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet("QWidget#sidebar{background:#0c1319}")
        sv = QVBoxLayout(sidebar)
        sv.setContentsMargins(10, 12, 0, 12)
        sv.setSpacing(9)
        side.setWidget(sidebar)
        body.addWidget(side)
        channels = self._card("⌁  Channels", sv)
        self.channel_checks = {}
        for name in ("CH1", "CH2", "MATH"):
            line = QHBoxLayout()
            check = ScopeCheckBox()
            check.setToolTip(name + " visibility")
            check.setChecked(name != "MATH")
            check.setStyleSheet(f"color:{COLORS[name]};font-weight:700;")
            check.toggled.connect(
                lambda state, n=name: self.set_channel_visible(n, state)
            )
            self.channel_checks[name] = check
            line.addWidget(check)
            chip = QLabel(name)
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip.setFixedWidth(57)
            chip.setStyleSheet(
                f"background:{COLORS[name]};color:#07121b;border-radius:5px;font-weight:800;padding:4px;"
            )
            line.addWidget(chip)
            line.addStretch()
            more = QPushButton("•••")
            more.setFixedWidth(30)
            more.setToolTip("Channel controls")
            more.clicked.connect(lambda checked=False, n=name: self.channel_menu(n))
            line.addWidget(more)
            channels.addLayout(line)
        controls = self._card("⚙  Channel Settings", sv)
        self.channel_selector = QComboBox()
        self.channel_selector.addItems(["CH1", "CH2"])
        self.channel_selector.currentTextChanged.connect(self.change_y_channel)
        self.units_selector = QComboBox()
        self.units_selector.addItems(["V (inferred)", "Raw counts"])
        self.units_selector.currentIndexChanged.connect(self.units_changed)
        for title, widget in [
            ("Y channel", self.channel_selector),
            ("Units", self.units_selector),
        ]:
            line = QHBoxLayout()
            line.addWidget(QLabel(title))
            line.addWidget(widget, 1)
            controls.addLayout(line)
        self.scale_boxes = {}
        for name in ("CH1", "CH2", "MATH"):
            row = QHBoxLayout()
            label = QLabel(name)
            label.setStyleSheet(f"color:{COLORS[name]};font-weight:700")
            row.addWidget(label)
            spin = ScaleSpinBox()
            spin.setRange(0.000001, 1000000)
            spin.setDecimals(6)
            spin.setValue(1)
            spin.setSuffix(" V/div")
            spin.setSingleStep(0.1)
            spin.setToolTip("Display scale only; sample values do not change")
            spin.valueChanged.connect(
                lambda value, n=name: self.scale_changed(n, value)
            )
            self.scale_boxes[name] = spin
            row.addWidget(spin, 1)
            controls.addLayout(row)
        display = self._card("▣  Display", sv)
        self.trigger_check = ScopeCheckBox("Show trigger level")
        self.trigger_check.setChecked(True)
        self.trigger_check.toggled.connect(self.trigger_visibility)
        display.addWidget(self.trigger_check)
        self.cursor_check = ScopeCheckBox("Show cursors")
        self.cursor_check.toggled.connect(self.cursor_visibility)
        display.addWidget(self.cursor_check)
        persistence = ScopeCheckBox("Persistence")
        persistence.setEnabled(False)
        persistence.setToolTip(
            "Unavailable: a static export contains no acquisition history"
        )
        display.addWidget(persistence)
        self.layout_selector = QComboBox()
        self.layout_selector.addItems(["Scope layout", "Physical overlay"])
        self.layout_selector.currentIndexChanged.connect(self.layout_changed)
        display.addWidget(self.layout_selector)
        self.origin_selector = QComboBox()
        self.origin_selector.addItems(["First sample", "Trigger marker (approx.)"])
        self.origin_selector.currentIndexChanged.connect(self.origin_changed)
        display.addWidget(self.origin_selector)
        preview = QPushButton("Embedded scope preview")
        preview.clicked.connect(self.preview)
        display.addWidget(preview)
        sv.addStretch()
        main = QWidget()
        mv = QVBoxLayout(main)
        mv.setContentsMargins(0, 12, 12, 12)
        mv.setSpacing(12)
        body.addWidget(main)
        body.setStretchFactor(1, 1)
        top = QHBoxLayout()
        top.setSpacing(12)
        info = QWidget()
        iv = QVBoxLayout(info)
        iv.setContentsMargins(4, 0, 0, 0)
        self.file_label = QLabel("▤  File: open a scope waveform")
        self.file_label.setWordWrap(True)
        iv.addWidget(self.file_label)
        self.trigger_label = QLabel("⚑  Trigger: —")
        self.trigger_label.setWordWrap(True)
        self.trigger_label.setStyleSheet("color:#75db9b")
        iv.addWidget(self.trigger_label)
        self.length_label = QLabel("No capture loaded")
        self.length_label.setObjectName("muted")
        iv.addWidget(self.length_label)
        top.addWidget(info, 1)
        panel = QFrame()
        panel.setObjectName("card")
        panel.setMinimumWidth(380)
        panel.setMaximumWidth(540)
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(15, 10, 15, 12)
        heading = QHBoxLayout()
        heading.addWidget(QLabel("▥  Measurements"))
        self.measure_channel = QComboBox()
        self.measure_channel.addItems(["CH1", "CH2"])
        self.measure_channel.currentTextChanged.connect(self.update_measurement_panel)
        heading.addWidget(self.measure_channel)
        heading.addStretch()
        pv.addLayout(heading)
        grid = QGridLayout()
        self.measure_values = {}
        for column, (key, title) in enumerate(
            [
                ("frequency_hz", "Freq"),
                ("period_s", "Period"),
                ("peak_to_peak", "Vpp"),
                ("rms", "RMS"),
            ]
        ):
            title_label = QLabel(title)
            title_label.setObjectName("muted")
            grid.addWidget(title_label, 0, column)
            value = QLabel("—")
            value.setObjectName("measureValue")
            grid.addWidget(value, 1, column)
            self.measure_values[key] = value
        pv.addLayout(grid)
        top.addWidget(panel)
        mv.addLayout(top)
        plot_card = QFrame()
        plot_card.setObjectName("card")
        pl = QVBoxLayout(plot_card)
        pl.setContentsMargins(16, 15, 14, 12)
        self.plot = ScopePlot(axisItems={"left": AmplitudeAxis(self)})
        self.plot.setBackground("#070e13")
        self.plot.showGrid(x=True, y=True, alpha=0.22)
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        self.plot.getPlotItem().setClipToView(True)
        self.plot.getPlotItem().setDownsampling(auto=True, mode="peak")
        self.plot.getPlotItem().setDefaultPadding(0.025)
        self.plot.getPlotItem().getAxis("left").setWidth(78)
        self.plot.getPlotItem().getAxis("bottom").setHeight(38)
        self.plot.getPlotItem().vb.setMouseMode(pg.ViewBox.PanMode)
        self.plot.getPlotItem().vb.sigXRangeChanged.connect(self.range_changed)
        self.plot.pointClicked.connect(self.plot_clicked)
        pl.addWidget(self.plot, 1)
        self.cursor_label = QFrame(self.plot.viewport())
        self.cursor_label.setObjectName("cursorCard")
        self.cursor_label.setStyleSheet("""
            QFrame#cursorCard {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #172633,stop:1 #09131c);border:1px solid #63869f;border-radius:12px;}
            QLabel {background:transparent;border:none;font-size:12px;}
            QLabel#cursorBadge {border-radius:8px;font-weight:700;padding:1px 7px;}
        """)
        shadow = QtWidgets.QGraphicsDropShadowEffect(self.cursor_label)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QtGui.QColor(0, 0, 0, 150))
        self.cursor_label.setGraphicsEffect(shadow)
        card_layout = QVBoxLayout(self.cursor_label)
        card_layout.setContentsMargins(13, 9, 13, 10)
        card_layout.setSpacing(4)
        heading = QHBoxLayout()
        cursor_icon = QLabel()
        cursor_icon.setPixmap(icon("cursor").pixmap(16, 16))
        heading.addWidget(cursor_icon)
        title = QLabel("Cursors")
        title.setStyleSheet("font-weight:700;color:#f2f6fa;")
        heading.addWidget(title)
        heading.addStretch()
        card_layout.addLayout(heading)
        self.cursor_channel_label = QLabel()
        self.cursor_channel_label.setWordWrap(True)
        card_layout.addWidget(self.cursor_channel_label)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(3)
        self.cursor_fields = {}
        for row, (name, accent, background) in enumerate((
            ("C1", "#b6ddff", "#075d99"),
            ("C2", "#a7fcff", "#008f9d"),
            ("ΔT", "#ffe638", "#655700"),
            ("1/ΔT", "#91f34b", "#246109"),
            ("Y1", "#d698f6", "#41315f"),
            ("Y2", "#f18ae6", "#632967"),
            ("AVG", "#e9b8fc", "#493356"),
            ("Sample", "#c8d6e2", "#304455"),
        )):
            badge = QLabel(name)
            badge.setObjectName("cursorBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(f"color:{accent};background:{background};")
            value = QLabel("—")
            value.setStyleSheet(f"color:{accent};font-weight:650;")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(badge, row, 0)
            grid.addWidget(value, row, 1)
            self.cursor_fields[name] = (badge, value)
        grid.setColumnStretch(1, 1)
        card_layout.addLayout(grid)
        details = QLabel('<a href="details" style="color:#78cafa;">Interval / band statistics…</a>')
        details.linkActivated.connect(self.cursor_details)
        card_layout.addWidget(details)
        self.cursor_label.setFixedWidth(216)
        self.cursor_label.hide()
        self.plot.resized.connect(self.position_cursor_overlay)
        mv.addWidget(plot_card, 1)
        self.bar_label = QLabel("Visible samples: —")
        self.bar_label.setWordWrap(True)
        self.bar_label.setStyleSheet("color:#c1cdd7;padding:3px;")
        mv.addWidget(self.bar_label)
        self.statusBar().setSizeGripEnabled(False)
        status_content = QWidget()
        status_content.installEventFilter(self)
        self.status_content = status_content
        status_layout = QHBoxLayout(status_content)
        status_layout.setContentsMargins(9, 3, 9, 3)
        status_layout.setSpacing(12)
        self.status_label = QLabel("●  Ready")
        self.status_label.setMaximumWidth(180)
        self.status_label.setStyleSheet("color:#75ed93;font-size:11px;")
        status_layout.addWidget(self.status_label)
        self.scale_status = QLabel("V/div: —")
        self.time_status = QLabel("Time/div: —")
        self.rate_status = QLabel("Sample rate: —")
        self.status_sections = []
        for name, label in (("wave", self.scale_status), ("recent", self.time_status), ("wave", self.rate_status)):
            section = QWidget()
            layout = QHBoxLayout(section)
            layout.setContentsMargins(12, 0, 0, 0)
            layout.setSpacing(7)
            section.setStyleSheet("QWidget {border:none;} QWidget#statusSection {border-left:1px solid #53616d;}")
            section.setObjectName("statusSection")
            glyph = QLabel()
            glyph.setPixmap(icon(name).pixmap(14, 14))
            layout.addWidget(glyph)
            label.setStyleSheet("font-size:11px;")
            layout.addWidget(label)
            status_layout.addWidget(section)
            self.status_sections.append(section)
        status_layout.addStretch(1)
        self.mouse_hints = QLabel("◉  Wheel: zoom   ·   Drag: pan   ·   Click: set cursor")
        self.mouse_hints.setStyleSheet("font-size:11px;color:#c6d1db;border-left:1px solid #53616d;padding-left:12px;")
        status_layout.addWidget(self.mouse_hints)
        status_content.setToolTip("Wheel: Zoom · Drag: Pan · Click: Set cursor (in cursor mode)")
        self.statusBar().addWidget(status_content, 1)
        self.statusBar().hide()
        self.trigger_line = pg.InfiniteLine(
            angle=0,
            pen=pg.mkPen("#67ba86", style=Qt.PenStyle.DashLine),
            label="Trigger {value:.3g}",
            labelOpts={"position": 0.97, "color": "#8ad6a4"},
        )
        self.plot.addItem(self.trigger_line)
        self.trigger_line.hide()
        self.marker_line = pg.InfiniteLine(
            angle=90,
            pen=pg.mkPen("#4ed978", style=Qt.PenStyle.DotLine),
            label="T marker",
            labelOpts={"position": 0.96, "color": "#65e688"},
        )
        self.plot.addItem(self.marker_line)
        self.marker_line.hide()

    def _build_menus(self):
        action = QtGui.QAction(self)
        action.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        action.triggered.connect(self.open_dialog)
        self.addAction(action)
        action = QtGui.QAction(self)
        action.setShortcut("Ctrl+0")
        action.triggered.connect(self.fit)
        self.addAction(action)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.load(urls[0].toLocalFile())

    def refresh_recent(self):
        self.recent_menu.clear()
        for path in self.recent[:8]:
            self.recent_menu.addAction(
                Path(path).name, lambda checked=False, p=path: self.load(p)
            )
        if not self.recent:
            self.recent_menu.addAction("No recent files").setEnabled(False)

    def notify(self, title, text):
        QMessageBox.information(self, title, text)

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open FNIRSI waveform", "", "FNIRSI waveform (*.wav);;All files (*)"
        )
        if path:
            self.load(path)

    def submit(self, kind, token, fn):
        job = Job(kind, token, fn)
        job.signals.done.connect(self.job_done)
        job.signals.failed.connect(self.job_failed)
        self._jobs[(kind, token)] = job
        self.pool.start(job)

    def load(self, path):
        self._load_token += 1
        self._analysis_token += 1
        self.analysis_timer.stop()
        self.set_status("●  Loading…")
        self.open_button.setEnabled(False)
        self.submit("load", self._load_token, lambda: load_capture(path))

    def load_sync(self, path):
        """Deterministic entry used only by automated tests and packaged self-checks."""
        self.apply_capture(load_capture(path))

    @Slot(str, int, object)
    def job_done(self, kind, token, result):
        self._jobs.pop((kind, token), None)
        if kind == "load":
            if token != self._load_token:
                return
            self.open_button.setEnabled(True)
            self.apply_capture(result)
        elif kind == "analysis":
            if token != self._analysis_token:
                return
            self._last_analysis_token = token
            self.apply_analysis(result)
            if self._pending_image is not None:
                path = self._pending_image
                self._pending_image = None
                self.save_image(path)
        elif kind == "export":
            self.set_status("●  Export saved")

    @Slot(str, int, str)
    def job_failed(self, kind, token, error):
        self._jobs.pop((kind, token), None)
        if kind == "load" and token != self._load_token:
            return
        if kind == "analysis" and token != self._analysis_token:
            return
        self.last_error = error
        self.open_button.setEnabled(True)
        self.set_status("●  " + error)
        if kind != "analysis":
            QMessageBox.warning(self, "Unable to " + kind, error)

    def apply_capture(self, capture):
        for key, value in capture.items():
            setattr(self, key, value)
        self.channels = (
            self.physical_channels
            if self.physical_channels is not None
            else self.raw_channels
        )
        self.units = "V inferred" if self.physical_channels is not None else "raw"
        self.math_enabled = False
        self.visible = {k: k != "MATH" for k in COLORS}
        self.display_positions = {}
        self.scales = {}
        self.measurements = {}
        self.clear_cursors()
        for curve in self.curves.values():
            self.plot.removeItem(curve)
        self.curves = {}
        for line in self.zero_lines.values():
            self.plot.removeItem(line)
        self.zero_lines = {}
        self.units_selector.blockSignals(True)
        self.units_selector.setCurrentIndex(0 if self.units == "V inferred" else 1)
        self.units_selector.blockSignals(False)
        self.y_channel = next(iter(self.channels))
        self._sync_channels()
        for name, spin in self.scale_boxes.items():
            scale = (
                self.meta.get("calibration", {})
                .get("channels", {})
                .get(name, {})
                .get("display_volts_per_div", 1)
                or 1
            )
            self.scales[name] = scale
            spin.blockSignals(True)
            spin.setValue(scale)
            spin.setEnabled(
                self.units == "V inferred"
                and (
                    name in self.channels or name == "MATH" and len(self.channels) == 2
                )
            )
            spin.blockSignals(False)
        if not self.measurement_custom:
            self.default_measurement_bar()
        self.time_origin = "first sample"
        self.origin_selector.blockSignals(True)
        self.origin_selector.setCurrentIndex(0)
        self.origin_selector.blockSignals(False)
        self.file_label.setText("▤  File: " + self.filename.name)
        dt = self.dt()
        self.length_label.setText(
            f'Length: {pg.siFormat((self.n-1)*dt,suffix="s") if dt else str(self.n)+" samples"}   ({self.n:,} pts/channel)'
        )
        self.recent = [str(self.filename)] + [
            p for p in self.recent if p != str(self.filename)
        ]
        self.recent = self.recent[:8]
        self.settings.setValue("recent", self.recent)
        self.refresh_recent()
        self.render_data()
        self.fit()
        self.set_status(
            "●  Ready · " + self.meta.get("compatibility", {}).get("status", "Raw data")
        )

    def _sync_channels(self):
        for name, check in self.channel_checks.items():
            check.blockSignals(True)
            check.setChecked(self.visible.get(name, False) and name in self.channels)
            check.setEnabled(
                name in self.channels
                or name == "MATH"
                and "CH1" in self.raw_channels
                and "CH2" in self.raw_channels
            )
            check.blockSignals(False)
        names = list(self.channels)
        for combo in (self.channel_selector, self.measure_channel):
            previous = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            combo.setCurrentText(previous if previous in names else names[0])
            combo.blockSignals(False)
        self.y_channel = self.channel_selector.currentText()
        self.math_button.setChecked(self.math_enabled)

    def dt(self):
        return self.meta.get("calibration", {}).get("sample_interval_s_candidate")

    def origin(self):
        return origin_sample(self.meta, self.time_origin)

    def time_axis(self):
        return bool(self.dt() and self.units == "V inferred")

    def sample_to_x(self, index):
        return (index - self.origin()) * self.dt() if self.time_axis() else index

    def x_to_sample(self, x):
        value = x / self.dt() + self.origin() if self.time_axis() else x
        nearest = round(value)
        return float(nearest) if abs(value - nearest) < 1e-6 else value

    def channel_scale(self, name):
        return self.scales.get(name, 1) or 1

    def position(self, name):
        return self.display_positions.get(
            name,
            self.meta.get("calibration", {})
            .get("channels", {})
            .get(name, {})
            .get("display_zero_position", 250),
        )

    def to_display_y(self, name, value):
        return (
            value / self.channel_scale(name) + self.position(name) / 63
            if self.scope_layout and self.units == "V inferred"
            else value
        )

    def from_display_y(self, name, value):
        return (
            (value - self.position(name) / 63) * self.channel_scale(name)
            if self.scope_layout and self.units == "V inferred"
            else value
        )

    def render_data(self):
        self._rendering = True
        for name, values in self.channels.items():
            if name not in self.curves:
                curve = pg.PlotDataItem(pen=pg.mkPen(COLORS[name], width=1.6))
                curve.setClipToView(True)
                curve.setDownsampling(auto=True, method="peak")
                self.plot.addItem(curve)
                self.curves[name] = curve
            array = self.arrays[self.units][name]
            x = np.arange(len(array), dtype=float)
            if self.time_axis():
                x = (x - self.origin()) * self.dt()
            self.curves[name].setData(x, self.to_display_y(name, array))
            self.curves[name].setVisible(self.visible.get(name, False))
            if name not in self.zero_lines:
                line = pg.InfiniteLine(
                    angle=0,
                    movable=True,
                    pen=pg.mkPen(COLORS[name], width=0.5, style=Qt.PenStyle.DotLine),
                    hoverPen=pg.mkPen(COLORS[name], width=2),
                )
                line.label = ChannelMarker(
                    line,
                    text=name.replace("CH", "").replace("MATH", "M"),
                    position=0.014,
                    color="#07121b",
                    fill=COLORS[name],
                )
                line.sigPositionChangeFinished.connect(
                    lambda item, n=name: self.position_changed(n, item.value())
                )
                self.plot.addItem(line)
                self.zero_lines[name] = line
            line = self.zero_lines[name]
            line.setValue(self.to_display_y(name, 0))
            line.setVisible(
                self.visible.get(name, False)
                and self.units == "V inferred"
                and self.scope_layout
            )
        for name in list(self.curves):
            if name not in self.channels:
                self.curves[name].hide()
                self.zero_lines[name].hide()
        if self.n > 1:
            span = self.sample_to_x(self.n - 1) - self.sample_to_x(0)
            self.plot.getPlotItem().vb.setLimits(
                xMin=self.sample_to_x(0),
                xMax=self.sample_to_x(self.n - 1),
                minXRange=min(span, (self.dt() if self.time_axis() else 1) * 16),
                maxXRange=span,
            )
        self.plot.setLabel(
            "bottom",
            "Time" if self.time_axis() else "Sample",
            units="s" if self.time_axis() else None,
        )
        self.plot.setLabel(
            "left",
            (
                self.y_channel + " amplitude"
                if self.scope_layout and self.units == "V inferred"
                else "Amplitude"
            ),
            units="V" if self.units == "V inferred" else "counts",
        )
        self.plot.getAxis("left").picture = None
        self.plot.getAxis("left").update()
        info = trigger_info(self.meta)
        self.trigger_readout = info["text"]
        self.trigger_label.setText("⚑  " + self.trigger_readout)
        channel = info.get("channel")
        level = info.get("level_v")
        show = (
            self.show_trigger_level
            and info.get("enabled")
            and channel in self.channels
            and self.visible.get(channel)
            and level is not None
        )
        if show:
            if self.units == "raw":
                cal = self.meta["calibration"]["channels"][channel]
                level = (
                    level / cal["candidate_volts_per_count"] + cal["candidate_zero_raw"]
                )
            self.trigger_line.setValue(self.to_display_y(channel, level))
            self.trigger_line.label.setFormat(f'T {channel} ≈ {info["level_v"]:+.4g} V')
        self.trigger_line.setVisible(bool(show))
        marker = (
            self.meta.get("calibration", {})
            .get("trigger", {})
            .get("sample_index_candidate")
        )
        self.marker_line.setVisible(marker is not None)
        if marker is not None:
            self.marker_line.setValue(self.sample_to_x(marker))
        self._rendering = False
        self.sync_cursor_lines()
        self.update_status()
        self.schedule_analysis()

    def fit(self):
        if not self.channels:
            self.plot.setXRange(0, 1)
            self.plot.setYRange(-5, 5)
            return
        self.plot.setXRange(
            self.sample_to_x(0), self.sample_to_x(self.n - 1), padding=0
        )
        self.fit_y()
        self.schedule_analysis()

    def fit_y(self):
        if self.scope_layout and self.units == "V inferred":
            self.plot.setYRange(0, 500 / 63, padding=0.02)
        else:
            arrays = [
                self.arrays[self.units][name]
                for name in self.channels
                if self.visible.get(name)
            ]
            if arrays:
                lo = min(float(a.min()) for a in arrays)
                hi = max(float(a.max()) for a in arrays)
                pad = max((hi - lo) * 0.1, 1e-6 if self.units == "V inferred" else 1)
                self.plot.setYRange(lo - pad, hi + pad, padding=0)

    def zoom(self, factor):
        if not self.channels:
            return
        lo, hi = self.plot.viewRange()[0]
        center = (lo + hi) / 2
        half = (hi - lo) * factor / 2
        self.plot.setXRange(center - half, center + half, padding=0)

    def range_changed(self, *args):
        if not self.channels:
            return
        lo, hi = self.plot.viewRange()[0]
        self.start = max(0.0, min(self.n - 1, self.x_to_sample(lo)))
        self.end = max(self.start, min(self.n - 1, self.x_to_sample(hi)))
        self.schedule_analysis()
        self.update_status()

    def set_status(self, text):
        message = text.removeprefix("●  ")
        color = "#75ed93" if message.startswith(("Ready", "Export saved")) else (
            "#ffd65a" if message.startswith("Loading") else "#f48b96"
        )
        self.status_label.setStyleSheet(f"color:{color};font-size:11px;")
        self.status_label.setToolTip(message)
        self.status_label.setText(
            self.status_label.fontMetrics().elidedText("●  " + message, Qt.TextElideMode.ElideRight, 180)
        )

    def update_status(self):
        unit = "V/div" if self.units == "V inferred" else "counts/div"
        scales = " &nbsp; ".join(
            f'<span style="color:{COLORS.get(name, "#eaf0f5")};font-weight:700;">{name}</span> '
            f'{self.channel_scale(name):g} {unit}'
            for name in self.channels
            if self.visible.get(name)
        )
        self.scale_status.setText(scales or "V/div: —")
        lo, hi = self.plot.viewRange()[0]
        self.time_status.setText(
            ("Time/div: " + pg.siFormat((hi - lo) / 10, suffix="s"))
            if self.time_axis()
            else f"Samples/div: {(hi-lo)/10:.5g}"
        )
        self.rate_status.setText(
            "Sample rate: " + pg.siFormat(1 / self.dt(), suffix="Sa/s") + " (inferred)"
            if self.dt()
            else "Sample rate: —"
        )

    def schedule_analysis(self):
        self.cursor_y_band = None
        self._analysis_token += 1
        if self.channels:
            self.measurements = {}
            self.live_readout = "Visible samples: updating…"
            self.bar_label.setText(self.live_readout)
            self.update_measurement_panel()
            self.analysis_timer.start()

    def request_analysis(self):
        if not self.channels:
            return
        token = self._analysis_token
        channels = {n: v for n, v in self.channels.items() if self.visible.get(n)}
        a = int(self.start)
        b = min(self.n, max(a + 1, int(self.end) + 1))
        args = (
            channels,
            a,
            b,
            self.dt(),
            list(self.measurement_order),
            self.units,
            list(self.delta_cursors) if self.delta_cursors is not None else None,
            list(self.y_cursors) if self.y_cursors is not None else None,
            self.y_channel,
            self.cursor,
        )
        self.submit("analysis", token, lambda: analyze_view(*args))

    def apply_analysis(self, result):
        self.measurements = result["measurements"]
        self.live_readout = "Visible samples: " + "   |   ".join(result["bar"])
        self.bar_label.setText(
            'Visible samples: ' + ' &nbsp; <span style="color:#718391;">|</span> &nbsp; '.join(
                f'<span style="color:{COLORS.get(item.split()[0], "#c1cdd7")};">{escape(item)}</span>'
                for item in result["bar"]
            )
        )
        self.cursor_readout = "\n".join(result["cursor"])
        self.cursor_y_band = result.get("y_band")
        self.update_cursor_overlay()
        self.update_measurement_panel()
        if getattr(self, "measurement_dialog_text", None) is not None:
            try:
                self.measurement_dialog_text.setPlainText(
                    self.measurement_description()
                )
            except RuntimeError:
                self.measurement_dialog_text = None

    def position_cursor_overlay(self):
        if not hasattr(self, "cursor_label"):
            return
        self.cursor_label.adjustSize()
        self.cursor_label.move(
            max(0, self.plot.viewport().width() - self.cursor_label.width() - 22),
            max(0, self.plot.viewport().height() - self.cursor_label.height() - 55),
        )

    def update_cursor_overlay(self):
        values = {}
        channel_color = COLORS.get(self.y_channel, "#c8d6e2")
        self.cursor_channel_label.setText(
            f'Y channel: <b style="color:{channel_color};">{escape(self.y_channel)}</b>'
            if self.y_cursors is not None else "Time cursors · all channels"
        )

        if self.delta_cursors is not None:
            for i, value in enumerate(self.delta_cursors):
                values[f"C{i+1}"] = (
                    pg.siFormat(self.sample_to_x(value), suffix="s")
                    if self.time_axis() else f"#{int(value):,}"
                )
            delta = (self.delta_cursors[1] - self.delta_cursors[0]) * (self.dt() or 0)
            values["ΔT"] = pg.siFormat(delta, suffix="s") if self.dt() else "—"
            values["1/ΔT"] = pg.siFormat(1 / abs(delta), suffix="Hz") if delta else "—"
        if self.y_cursors is not None:
            unit = "V" if self.units == "V inferred" else "counts"
            for i, value in enumerate(self.y_cursors):
                values[f"Y{i+1}"] = f"{value:.6g} {unit}"
            band = getattr(self, "cursor_y_band", None)
            values["AVG"] = (
                f'{band["mean"]:.6g} {unit}' if band and band["channel"] == self.y_channel and band["count"]
                else "—" if band else "Updating…"
            )
            self.cursor_fields["AVG"][1].setToolTip("Mean of visible samples between Y1 and Y2; — means no samples in the band.")
        if self.cursor is not None:
            values["Sample"] = f"{int(self.cursor):,}"
        for name, (badge, label) in self.cursor_fields.items():
            badge.setVisible(name in values)
            label.setVisible(name in values)
            label.setText(values.get(name, "—"))
        self.cursor_label.setToolTip(self.cursor_readout)
        self.cursor_label.setVisible(self.cursor_check.isChecked() and bool(values))
        self.position_cursor_overlay()
        self.cursor_label.raise_()

    def eventFilter(self, watched, event):
        if watched is getattr(self, "status_content", None) and event.type() == QtCore.QEvent.Type.Resize:
            width = watched.width()
            self.mouse_hints.setVisible(width >= 1250)
            # The full sampling readout remains available on hover on narrow windows.
            self.status_sections[2].setVisible(width >= 900)
            self.status_content.setToolTip(
                self.rate_status.text() + "\nWheel: Zoom · Drag: Pan · Click: Set cursor (in cursor mode)"
            )
        return super().eventFilter(watched, event)

    def cursor_details(self, *args):
        dialog = QDialog(self)
        dialog.setWindowTitle("Cursor statistics")
        dialog.resize(720, 300)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit(self.cursor_readout)
        text.setReadOnly(True)
        layout.addWidget(text)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    def update_measurement_panel(self, *args):
        name = self.measure_channel.currentText()
        m = self.measurements.get(name, {})
        for key, label in self.measure_values.items():
            value = m.get(key)
            suffix = (
                "Hz"
                if key == "frequency_hz"
                else (
                    "s"
                    if key == "period_s"
                    else "V" if self.units == "V inferred" else " counts"
                )
            )
            label.setText(
                pg.siFormat(value, precision=4, suffix=suffix)
                if value is not None
                else "—"
            )
            label.setStyleSheet("color:" + COLORS.get(name, "#fff126"))

    def set_channel_visible(self, name, state):
        if name == "MATH" and state and not self.math_enabled:
            self.toggle_math()
            return
        self.visible[name] = state
        self.render_data()

    def channel_menu(self, name):
        menu = QMenu(self)
        menu.addAction(
            "Reset channel position", lambda: self.reset_channel_position(name)
        )
        menu.addAction(
            "Use for Y cursors", lambda: self.channel_selector.setCurrentText(name)
        )
        menu.exec(QtGui.QCursor.pos())

    def reset_channel_position(self, name):
        self.display_positions.pop(name, None)
        self.render_data()

    def position_changed(self, name, value):
        self.display_positions[name] = max(0, min(500, value * 63))
        self.render_data()

    def scale_changed(self, name, value):
        self.scales[name] = value
        if self.channels:
            self.render_data()

    def change_y_channel(self, name):
        if name not in self.channels:
            return
        self.y_channel = name
        self.y_cursors = None
        self.render_data()

    def units_changed(self, index):
        if not self.channels:
            return
        target = "V inferred" if index == 0 else "raw"
        if target == "V inferred" and self.physical_channels is None:
            self.units_selector.blockSignals(True)
            self.units_selector.setCurrentIndex(1)
            self.units_selector.blockSignals(False)
            self.notify(
                "Physical conversion unavailable",
                "This capture remains in raw counts because calibration or compatibility checks did not pass.",
            )
            return
        self.clear_cursors()
        self.units = target
        self.math_enabled = False
        self.channels = (
            self.physical_channels if target == "V inferred" else self.raw_channels
        )
        self._sync_channels()
        if not self.measurement_custom:
            self.default_measurement_bar()
        for name, spin in self.scale_boxes.items():
            spin.setEnabled(
                target == "V inferred"
                and (
                    name in self.channels or name == "MATH" and len(self.channels) == 2
                )
            )
        self.render_data()
        self.fit()

    def toggle_units(self):
        self.units_selector.setCurrentIndex(1 if self.units == "V inferred" else 0)

    def toggle_math(self):
        if (
            not all(n in self.raw_channels for n in ("CH1", "CH2"))
            or self.physical_channels is None
        ):
            self.math_button.setChecked(False)
            self.channel_checks["MATH"].blockSignals(True)
            self.channel_checks["MATH"].setChecked(False)
            self.channel_checks["MATH"].blockSignals(False)
            self.notify(
                "Math unavailable",
                "Both channels and a usable physical conversion are required.",
            )
            return
        if self.units == "raw":
            self.units_selector.setCurrentIndex(0)
        self.math_enabled = not self.math_enabled
        if self.math_enabled:
            self.channels = dict(self.channels)
            self.channels["MATH"] = [
                a - b for a, b in zip(self.channels["CH1"], self.channels["CH2"])
            ]
            self.arrays[self.units]["MATH"] = np.asarray(self.channels["MATH"])
            self.visible["MATH"] = True
        else:
            self.channels = {k: v for k, v in self.channels.items() if k != "MATH"}
            self.visible["MATH"] = False
        self._sync_channels()
        if not self.measurement_custom:
            self.default_measurement_bar()
        self.render_data()

    def layout_changed(self, index):
        self.scope_layout = index == 0
        self.render_data()
        self.fit_y()

    def toggle_layout(self):
        self.layout_selector.setCurrentIndex(1 if self.scope_layout else 0)

    def origin_changed(self, index):
        proposed = "trigger marker" if index else "first sample"
        try:
            origin_sample(self.meta, proposed)
        except ValueError as exc:
            self.origin_selector.blockSignals(True)
            self.origin_selector.setCurrentIndex(0)
            self.origin_selector.blockSignals(False)
            self.notify("Timing unavailable", str(exc))
            return
        a, b = self.start, self.end
        self.time_origin = proposed
        self.render_data()
        self.plot.setXRange(self.sample_to_x(a), self.sample_to_x(b), padding=0)

    def toggle_origin(self):
        self.origin_selector.setCurrentIndex(
            0 if self.time_origin == "trigger marker" else 1
        )

    def trigger_visibility(self, state):
        self.show_trigger_level = state
        self.render_data()

    def reset_positions(self):
        self.display_positions = {}
        self.render_data()

    def restore_scales(self):
        for name, spin in self.scale_boxes.items():
            value = (
                self.meta.get("calibration", {})
                .get("channels", {})
                .get(name, {})
                .get("display_volts_per_div", 1)
                or 1
            )
            self.scales[name] = value
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)

    def reset_view(self):
        self.clear_cursors()
        self.display_positions = {}
        self.restore_scales()
        self.render_data()
        self.fit()

    def restore_scope_view(self):
        if not self.channels:
            return
        from decoder.display_state import clipped_view

        state = self.meta.get("saved_display", {})
        try:
            a, b = clipped_view(state, self.n)
        except ValueError as exc:
            self.notify("Saved scope view", str(exc))
            return
        self.scope_layout = True
        self.layout_selector.blockSignals(True)
        self.layout_selector.setCurrentIndex(0)
        self.layout_selector.blockSignals(False)
        self.display_positions = {}
        self.restore_scales()
        self.clear_cursors()
        self.delta_cursors = (
            list(state["x_samples"])
            if state.get("x_enabled")
            and all(0 <= p < self.n for p in state["x_samples"])
            else None
        )
        self.y_cursors = (
            list(state["y_volts_by_channel"][self.y_channel])
            if state.get("y_enabled")
            and self.units == "V inferred"
            and self.y_channel in state.get("y_volts_by_channel", {})
            else None
        )
        self.cursor_check.setChecked(
            self.delta_cursors is not None or self.y_cursors is not None
        )
        self.render_data()
        self.plot.setXRange(self.sample_to_x(a), self.sample_to_x(b), padding=0)
        self.fit_y()

    def clear_cursors(self):
        for line in self.x_lines + self.y_lines:
            self.plot.removeItem(line)
        self.x_lines = []
        self.y_lines = []
        if self.single_line is not None:
            self.plot.removeItem(self.single_line)
            self.single_line = None
        self.delta_cursors = None
        self.y_cursors = None
        self.cursor = None
        self.cursor_axis = None
        self.cursor_readout = ""
        self.cursor_label.hide()
        self.plot.setProperty("placeCursor", False)
        self.cursor_check.blockSignals(True)
        self.cursor_check.setChecked(False)
        self.cursor_check.blockSignals(False)

    def set_cursor_mode(self, mode):
        if not self.channels:
            return
        if mode is None:
            self.clear_cursors()
            self.schedule_analysis()
            return
        if mode == "single":
            self.clear_cursors()
        elif self.single_line is not None:
            self.plot.removeItem(self.single_line)
            self.single_line = None
            self.cursor = None
        self.cursor_axis = mode
        self.cursor_next = 0
        if mode == "x":
            self.delta_cursors = [
                self.start + 0.3 * (self.end - self.start),
                self.start + 0.7 * (self.end - self.start),
            ]
        elif mode == "y":
            values = self.channels[self.y_channel][int(self.start) : int(self.end) + 1]
            lo, hi = min(values), max(values)
            self.y_cursors = [lo + 0.25 * (hi - lo), lo + 0.75 * (hi - lo)]
        else:
            self.cursor = (self.start + self.end) / 2
        self.cursor_check.setChecked(True)
        self.plot.setProperty("placeCursor", mode == "single")
        self.sync_cursor_lines()
        self.schedule_analysis()

    def toggle_delta(self):
        self.set_cursor_mode("x")

    def toggle_y(self):
        self.set_cursor_mode("y")

    def toggle_cursor(self):
        self.set_cursor_mode("single")

    def cursor_visibility(self, state):
        self.plot.setProperty("placeCursor", bool(state and self.cursor_axis == "single"))
        if (
            state
            and self.delta_cursors is None
            and self.y_cursors is None
            and self.cursor is None
        ):
            self.set_cursor_mode("x")
            return
        self.sync_cursor_lines()
        self.cursor_label.setVisible(state and bool(self.cursor_readout))

    def sync_cursor_lines(self):
        shown = self.cursor_check.isChecked()
        self._rendering = True
        if self.delta_cursors is not None:
            if not self.x_lines:
                for i in range(2):
                    line = pg.InfiniteLine(
                        angle=90,
                        movable=True,
                        pen=pg.mkPen("#b7e7fc", style=Qt.PenStyle.DashLine),
                    )
                    line.label = ChannelMarker(
                        line, text=f"C{i+1}", position=0.96,
                        color="#c5efff", fill="#264759",
                    )
                    line.sigPositionChangeFinished.connect(
                        lambda item, j=i: self.x_cursor_moved(j, item.value())
                    )
                    self.plot.addItem(line)
                    self.x_lines.append(line)
            for i, line in enumerate(self.x_lines):
                line.setValue(self.sample_to_x(self.delta_cursors[i]))
                line.setVisible(shown)
        else:
            for line in self.x_lines:
                line.hide()
        if self.y_cursors is not None:
            if not self.y_lines:
                for i in range(2):
                    line = pg.InfiniteLine(
                        angle=0,
                        movable=True,
                        pen=pg.mkPen("#f1ac72", style=Qt.PenStyle.DashLine),
                    )
                    line.label = ChannelMarker(
                        line, text=f"Y{i+1}", position=0.02,
                        color=("#d698f6", "#f18ae6")[i],
                        fill=("#41315f", "#632967")[i],
                    )
                    line.sigPositionChangeFinished.connect(
                        lambda item, j=i: self.y_cursor_moved(j, item.value())
                    )
                    self.plot.addItem(line)
                    self.y_lines.append(line)
            for i, line in enumerate(self.y_lines):
                line.setValue(self.to_display_y(self.y_channel, self.y_cursors[i]))
                line.setVisible(shown)
        else:
            for line in self.y_lines:
                line.hide()
        if self.cursor is not None:
            if self.single_line is None:
                self.single_line = pg.InfiniteLine(
                    angle=90,
                    movable=True,
                    pen="w",
                    label="Sample",
                    labelOpts={"position": 0.85},
                )
                self.single_line.sigPositionChangeFinished.connect(
                    self.single_cursor_moved
                )
                self.plot.addItem(self.single_line)
            self.single_line.setValue(self.sample_to_x(self.cursor))
            self.single_line.setVisible(shown)
        self._rendering = False
        self.update_cursor_overlay()

    def x_cursor_moved(self, index, value):
        if self._rendering:
            return
        self.delta_cursors[index] = max(0, min(self.n - 1, self.x_to_sample(value)))
        self.sync_cursor_lines()
        self.schedule_analysis()

    def y_cursor_moved(self, index, value):
        if self._rendering:
            return
        self.y_cursors[index] = self.from_display_y(self.y_channel, value)
        self.schedule_analysis()

    def single_cursor_moved(self, line):
        self.cursor = max(0, min(self.n - 1, self.x_to_sample(line.value())))
        index = int(self.cursor)
        self.cursor_readout = f"Sample {index:,}   " + "   ".join(
            f"{name}: {values[index]:.6g}"
            for name, values in self.channels.items()
            if self.visible.get(name)
        )
        self.update_cursor_overlay()

    def plot_clicked(self, x, y):
        if self.cursor_axis == "single" and self.single_line is not None:
            self.single_line.setValue(x)
            self.single_cursor_moved(self.single_line)

    def default_measurement_bar(self):
        self.measurement_order = [
            (name, key)
            for name in self.channels
            for key in ("max", "min", "avg", "freq")
        ]
        self.measurement_custom = False

    def configure_measurement_bar(self):
        if not self.channels:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Customize measurement bar")
        dialog.resize(610, 440)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(
                "Visible-sample estimates. Scope selection restores choice and order only."
            )
        )
        listing = QListWidget()
        layout.addWidget(listing, 1)
        row = QHBoxLayout()
        channel = QComboBox()
        channel.addItems(list(self.channels))
        metric = QComboBox()
        metric.addItems(list(METRICS))
        row.addWidget(channel)
        row.addWidget(metric)
        layout.addLayout(row)

        def refresh(index=-1):
            listing.clear()
            listing.addItems(
                [f"{name}   {METRICS[key][0]}" for name, key in self.measurement_order]
            )
            listing.setCurrentRow(index)
            self.schedule_analysis()

        def add():
            item = (channel.currentText(), metric.currentText())
            if item not in self.measurement_order:
                self.measurement_order.append(item)
            self.measurement_custom = True
            refresh(len(self.measurement_order) - 1)

        def remove():
            index = listing.currentRow()
            if index >= 0:
                self.measurement_order.pop(index)
                self.measurement_custom = True
                refresh(min(index, len(self.measurement_order) - 1))

        def move(step):
            index = listing.currentRow()
            target = index + step
            if 0 <= index < len(self.measurement_order) and 0 <= target < len(
                self.measurement_order
            ):
                self.measurement_order[index], self.measurement_order[target] = (
                    self.measurement_order[target],
                    self.measurement_order[index],
                )
                self.measurement_custom = True
                refresh(target)

        def saved():
            entries = self.meta.get("saved_measurement_selection", {}).get(
                "entries", []
            )
            if not entries:
                self.notify("Scope selection", "No recognized saved selection.")
                return
            self.measurement_order = [tuple(e) for e in entries]
            self.measurement_custom = True
            refresh()

        def defaults():
            self.default_measurement_bar()
            refresh()

        for label, callback in [
            ("Add", add),
            ("Remove", remove),
            ("Up", lambda: move(-1)),
            ("Down", lambda: move(1)),
        ]:
            b = QPushButton(label)
            b.clicked.connect(callback)
            row.addWidget(b)
        bottom = QHBoxLayout()
        layout.addLayout(bottom)
        for label, callback in [
            ("Use scope selection", saved),
            ("Defaults", defaults),
            ("Close", dialog.accept),
        ]:
            b = QPushButton(label)
            b.clicked.connect(callback)
            bottom.addWidget(b)
        refresh()
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    def measure(self):
        if not self.channels:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(
            "Measurements — visible samples and stored scope readouts"
        )
        dialog.resize(850, 650)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(self.measurement_description())
        self.measurement_dialog_text = text
        layout.addWidget(text)
        b = QPushButton("Close")
        b.clicked.connect(dialog.accept)
        layout.addWidget(b)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    def measurement_description(self):
        lines = ["Visible exported samples (" + self.units + ")"]
        for name, m in self.measurements.items():
            lines.append("\n" + name)
            for metric in METRICS:
                lines.append(
                    "  "
                    + measurement_text(
                        metric, m, "V" if self.units == "V inferred" else "counts"
                    )
                )
        lines.append("\nScope-produced stored readouts (may include multiple updates):")
        for name, info in self.meta.get("calibration", {}).get("channels", {}).items():
            lines.append("\n" + name)
            for key, value in info["stored_readouts"].items():
                lines.append(f"  {key}: {value:.7g}")
        lines.extend(
            [
                "",
                "Time/voltage conversion is inferred. Stored readouts and offline estimates have different provenance.",
                "Rise/fall estimates need at least two sample intervals.",
            ]
        )
        return "\n".join(lines)

    def preview(self):
        if not self.channels:
            return
        try:
            w, h, rgb = extract_preview(self.data, self.meta)
        except ValueError as exc:
            self.notify("Preview unavailable", str(exc))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(self.filename.name + " — embedded scope preview")
        layout = QVBoxLayout(dialog)
        image = QtGui.QImage(rgb, w, h, w * 3, QtGui.QImage.Format.Format_RGB888).copy()
        label = QLabel()
        label.setPixmap(
            QtGui.QPixmap.fromImage(image).scaled(
                w * 3,
                h * 3,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )
        layout.addWidget(label)
        layout.addWidget(
            QLabel(
                "Optional embedded thumbnail; never used for decoding or measurements."
            )
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    def save_csv(self, path=None):
        if not self.channels:
            return
        if not isinstance(path, (str, Path)):
            path = QFileDialog.getSaveFileName(
                self,
                "Save channels",
                self.filename.stem + "-channels.csv",
                "CSV (*.csv)",
            )[0]
        if not path:
            return
        channels = dict(self.channels)
        dt = self.dt()
        origin = self.origin()
        calibrated = self.units == "V inferred"
        mode = self.time_origin

        def write():
            with Path(path).open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "sample_index",
                        *(
                            [mode.replace(" ", "_") + "_time_s_model"]
                            if calibrated
                            else []
                        ),
                        *[
                            name + ("_volts_inferred" if calibrated else "_raw_u16")
                            for name in channels
                        ],
                    ]
                )
                writer.writerows(
                    (
                        i,
                        *([(i - origin) * dt if dt else ""] if calibrated else []),
                        *row,
                    )
                    for i, row in enumerate(zip(*channels.values()))
                )

        self._export_token += 1
        self.submit("export", self._export_token, write)

    def save_report(self, path=None):
        if not self.channels:
            return
        if not isinstance(path, (str, Path)):
            path = QFileDialog.getSaveFileName(
                self,
                "Save reader report",
                self.filename.stem + "-report.json",
                "Reader report (*.json)",
            )[0]
        if not path:
            return
        from exports.report_export import export_report
        from types import SimpleNamespace

        keys = (
            "start",
            "end",
            "n",
            "filename",
            "meta",
            "units",
            "time_origin",
            "scope_layout",
            "y_channel",
            "cursor_readout",
            "cursor",
        )
        snapshot = SimpleNamespace(**{key: getattr(self, key) for key in keys})
        for key in ("channels", "visible", "display_positions", "scales"):
            setattr(snapshot, key, dict(getattr(self, key)))
        snapshot.measurement_order = list(self.measurement_order)
        snapshot.show_trigger_level = self.show_trigger_level
        snapshot.delta_cursors = (
            list(self.delta_cursors) if self.delta_cursors is not None else None
        )
        snapshot.y_cursors = (
            list(self.y_cursors) if self.y_cursors is not None else None
        )

        def write():
            selected = {
                name: values
                for name, values in snapshot.channels.items()
                if snapshot.visible.get(name)
            }
            result = analyze_view(
                selected,
                int(snapshot.start),
                min(snapshot.n, int(snapshot.end) + 1),
                snapshot.meta.get("calibration", {}).get("sample_interval_s_candidate"),
                snapshot.measurement_order,
                snapshot.units,
                snapshot.delta_cursors,
                snapshot.y_cursors,
                snapshot.y_channel,
                snapshot.cursor,
            )
            snapshot._report_measurements = result["measurements"]
            snapshot.cursor_readout = "\n".join(result["cursor"])
            export_report(snapshot, path)

        self._export_token += 1
        self.submit("export", self._export_token, write)

    def save_image(self, path=None):
        if not self.channels:
            return
        if not isinstance(path, (str, Path)):
            path = QFileDialog.getSaveFileName(
                self,
                "Save current waveform",
                self.filename.stem + "-waveform.png",
                "PNG (*.png);;SVG (*.svg)",
            )[0]
        if not path:
            return
        if self._last_analysis_token != self._analysis_token:
            self._pending_image = path
            self.analysis_timer.stop()
            self.request_analysis()
            return
        from exports.image_export import export_image

        try:
            export_image(self, path)
        except (OSError, ValueError) as exc:
            self.notify("Image export failed", str(exc))

    def closeEvent(self, event):
        self.analysis_timer.stop()
        self._load_token += 1
        self._analysis_token += 1
        self.pool.waitForDone()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = Viewer()
    window.show()
    if len(sys.argv) > 1:
        window.load(sys.argv[1])
    sys.exit(app.exec())
