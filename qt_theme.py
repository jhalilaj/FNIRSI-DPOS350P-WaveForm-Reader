"""Dark instrument styling and small scalable outline icons."""

from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from pathlib import Path
from PySide6.QtGui import QFontDatabase, QFont, QPalette, QColor
from PySide6.QtWidgets import QApplication


def initialize_fonts():
    # Windows supplies these fonts. Load them directly when an isolated/offscreen
    # Qt platform cannot enumerate system fonts; never redistribute font files.
    if not QFontDatabase.families():
        for filename in ("segoeui.ttf", "segoeuib.ttf", "segoeuiz.ttf", "seguisym.ttf"):
            path = Path("C:/Windows/Fonts") / filename
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))
    palette = QPalette()
    for role, color in {
        "Window": "#101820",
        "WindowText": "#edf2f7",
        "Base": "#111c25",
        "AlternateBase": "#1c2a35",
        "Text": "#edf2f7",
        "Button": "#22303c",
        "ButtonText": "#edf2f7",
        "Highlight": "#315c7c",
        "HighlightedText": "#ffffff",
        "ToolTipBase": "#223645",
        "ToolTipText": "#ffffff",
    }.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(color))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#687985")
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#687985")
    )
    QApplication.instance().setPalette(palette)


COLORS = {"CH1": "#fff126", "CH2": "#00e4ed", "MATH": "#d772fa", "RAW": "#fff126"}
STYLE = """
QWidget { color:#eaf0f5; font-family:"Segoe UI"; font-size:13px; }
QMainWindow,QDialog { background:#0c1319; }
QWidget#header { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #202a34,stop:1 #111a22); border-bottom:1px solid #35424e; }
QLabel#brand {font-size:32px;font-weight:900;font-style:italic;color:#f5f8fc;}
QLabel#subtitle {font-size:20px;color:#e9edf2;}
QWidget#ribbon {background:#10181f;border-bottom:1px solid #33434e;}
QFrame#group {border-right:1px solid #2c3944;}
QLabel#groupTitle {color:#dce4ec;font-size:14px;}
QToolButton,QPushButton {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #25313c,stop:1 #18222b);border:1px solid #3c4c59;border-radius:6px;padding:7px;}
QToolButton:hover,QPushButton:hover {background:#2b4153;border-color:#6185a2;}
QToolButton:pressed,QPushButton:pressed,QToolButton:checked {background:#244e73;border-color:#5ba6e5;}
QToolButton:disabled,QPushButton:disabled {color:#60717e;border-color:#26323b;background:#151e25;}
QToolButton#openButton {background:#265477;border-color:#5495c5;}
QFrame#card {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1e2932,stop:1 #151e26);border:1px solid #354450;border-radius:9px;}
QLabel#cardTitle {font-size:14px;font-weight:650;color:#f1f5f9;border:none;background:transparent;}
QLabel#muted {color:#9cabb7;}
QLabel#measureValue {font-size:18px;font-weight:700;color:#fff126;}
QComboBox,QDoubleSpinBox,QListWidget,QPlainTextEdit {background:#111c25;border:1px solid #3b4d5b;border-radius:5px;padding:5px;color:#eaf0f5;selection-background-color:#315c7c;}
QComboBox::drop-down {border:none;width:20px;}
QComboBox QAbstractItemView {background:#1b2833;color:white;selection-background-color:#315c7c;}
QCheckBox {spacing:9px;background:transparent;}
QCheckBox::indicator {width:16px;height:16px;}
QCheckBox::indicator:unchecked {background:#0e1820;border:1px solid #68808f;border-radius:3px;}
QCheckBox::indicator:checked {background:#37c983;border:1px solid #8aebbb;border-radius:3px;image:none;}
QMenu {background:#182630;border:1px solid #455666;padding:5px;}
QMenu::item {padding:7px 20px;border-radius:3px;}
QMenu::item:selected {background:#31516c;}
QStatusBar {background:#1a2631;border-top:1px solid #3b4c59;}
QStatusBar::item {border:none;}
QSplitter::handle {background:#0c1319;}
QScrollArea {border:none;background:transparent;}
QDoubleSpinBox {min-width:96px;}
QScrollBar:vertical {background:#15212b;width:9px;}
QScrollBar::handle:vertical {background:#475e70;min-height:25px;border-radius:4px;}
QTabWidget::pane {border:1px solid #354450;}
QTabBar::tab {background:#1a2935;padding:9px 16px;}
QTabBar::tab:selected {background:#31516c;}
QToolTip {background:#223645;color:#eff7fc;border:1px solid #66869f;padding:5px;}
"""
PATHS = {
    "open": '<path d="M3 7h7l2 3h9l-2 10H3z M3 7V4h7l2 3"/>',
    "recent": '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    "zoom_in": '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M6 10h8M10 6v8"/>',
    "zoom_out": '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M6 10h8"/>',
    "fit": '<path d="M3 9V3h6M15 3h6v6M21 15v6h-6M9 21H3v-6m0-12 6 6m12-6-6 6m6 12-6-6M3 21l6-6"/>',
    "reset": '<path d="M4 8a9 9 0 1 1-1 8M4 3v6h6"/>',
    "measure": '<path d="M3 21h18M5 19v-6h3v6m3 0V8h3v11m3 0V3h3v16"/>',
    "cursor": '<path d="M12 2v20M2 12h20M8 4h8M8 20h8M4 8v8M20 8v8"/>',
    "math": '<path d="M17 3c-6-4-7 10-9 16-1 3-3 3-5 1M5 9h11m1 7 5 6m0-6-5 6"/>',
    "csv": '<path d="M6 2h9l4 4v16H6zM15 2v5h4M8 11h9M8 15h9M8 19h9M12 10v10"/>',
    "image": '<rect x="2" y="3" width="20" height="18" rx="2"/><circle cx="8" cy="9" r="2"/><path d="m3 19 6-6 4 3 4-5 5 8"/>',
    "report": '<path d="M6 2h9l4 4v16H6zM15 2v5h4M9 11h7M9 15h7M9 19h5"/>',
    "wave": '<path d="M1 13h5l3-9 5 16 3-10h6"/>',
    "export": '<path d="M3 13v8h18v-8M12 16V2m-5 5 5-5 5 5"/>',
    "settings": '<circle cx="12" cy="12" r="4"/><path d="M12 1v4m0 14v4M1 12h4m14 0h4M4 4l3 3m10 10 3 3M4 20l3-3M17 7l3-3"/>',
}


def icon(name):
    content = PATHS.get(name, PATHS["wave"])
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="#e7f0f7" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{content}</g></svg>'
    pix = QPixmap(48, 48)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    return QIcon(pix)
