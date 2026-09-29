"""Render our native microphone mark into a multi-resolution Windows ICO."""
from pathlib import Path
import struct

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen


def main():
    app = QGuiApplication([])
    folder = Path(__file__).resolve().parents[1] / "src/whisper_desk/assets"
    folder.mkdir(parents=True, exist_ok=True)
    images = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size / 256, size / 256)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#6250d8"))
        painter.drawRoundedRect(QRectF(8, 8, 240, 240), 58, 58)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(QRectF(103, 54, 50, 99), 25, 25)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#ffffff"), 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(82, 98, 92, 83), 180 * 16, 180 * 16)
        painter.drawLine(128, 181, 128, 204)
        painter.drawLine(104, 204, 152, 204)
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buffer, "PNG")
        images.append((size, bytes(data)))
        if size == 256:
            img.save(str(folder / "app.png"))
    offset = 6 + 16 * len(images)
    entries, payloads = [], []
    for size, data in images:
        entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        payloads.append(data)
        offset += len(data)
    (folder / "app.ico").write_bytes(struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries + payloads))


if __name__ == "__main__":
    main()
