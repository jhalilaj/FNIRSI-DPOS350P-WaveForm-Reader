"""PNG and standalone SVG exports of the actual plot plus current readouts."""

from pathlib import Path
from PySide6 import QtCore, QtGui, QtSvg
import textwrap


def export_image(viewer, path):
    path = Path(path)
    width = max(800, viewer.plot.width())
    plot_height = max(250, viewer.plot.height())
    lines = [
        viewer.filename.name + " | " + viewer.units + " | zero: " + viewer.time_origin,
        viewer.trigger_readout,
        viewer.live_readout,
        viewer.cursor_readout,
    ]
    wrapped = [
        piece
        for line in lines
        for piece in textwrap.wrap(
            line,
            width=max(40, (width - 32) // 7),
            break_long_words=False,
            break_on_hyphens=False,
        )
    ]
    height = plot_height + 58 + 22 * len(wrapped)
    if path.suffix.lower() == ".svg":
        device = QtSvg.QSvgGenerator()
        device.setFileName(str(path))
        device.setSize(QtCore.QSize(width, height))
        device.setViewBox(QtCore.QRect(0, 0, width, height))
        device.setTitle("DPOS350P offline waveform")
    elif path.suffix.lower() == ".png":
        device = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
        device.fill(QtGui.QColor("#111b24"))
    else:
        raise ValueError("Choose PNG or SVG image format")
    painter = QtGui.QPainter(device)
    if not painter.isActive():
        raise OSError("Cannot create image at the selected location")
    painter.fillRect(0, 0, width, height, QtGui.QColor("#111b24"))
    painter.setPen(QtGui.QColor("#ecf4fa"))
    painter.setFont(QtGui.QFont("Segoe UI", 10))
    painter.drawText(16, 25, "FNIRSI  DPOS350P / Offline Replay")
    viewer.plot.render(
        painter, QtCore.QRectF(0, 40, width, plot_height), viewer.plot.rect()
    )
    for i, line in enumerate(wrapped):
        painter.drawText(16, plot_height + 65 + i * 22, line)
    painter.end()
    if path.suffix.lower() == ".png" and not device.save(str(path), "PNG"):
        raise OSError("Unable to save PNG")
    if not path.is_file() or path.stat().st_size == 0:
        raise OSError("Image export produced no data")


def export_svg(viewer, path):
    export_image(viewer, path)
