"""
倒计时程序 (PyQt5)
==================
支持设置时、分、秒，开始 / 暂停 / 重置，倒计时结束时弹出提示。

用法:
    python countdown.py
"""

import sys

from PyQt5.QtCore import QTime, QTimer, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class CountdownApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("倒计时程序")
        self.setFixedSize(400, 280)

        self._remaining_ms: int = 0
        self._running: bool = False

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self._build_ui()

    # ──────────────────────────────────────────
    # UI 构建
    # ──────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        # 时间显示
        self._display = QLabel("00:00:00", self)
        self._display.setAlignment(Qt.AlignCenter)
        font = QFont("Consolas", 52, QFont.Bold)
        self._display.setFont(font)
        self._display.setStyleSheet("color: #1a73e8;")
        root.addWidget(self._display)

        # 输入行：时 分 秒
        input_row = QHBoxLayout()
        input_row.setSpacing(12)

        self._spin_h = self._make_spin(0, 23, "时")
        self._spin_m = self._make_spin(0, 59, "分")
        self._spin_s = self._make_spin(0, 59, "秒")

        for widget in self._spin_h + self._spin_m + self._spin_s:
            input_row.addWidget(widget)

        root.addLayout(input_row)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._btn_start = QPushButton("开始")
        self._btn_start.setFixedHeight(40)
        self._btn_start.setStyleSheet(self._btn_style("#1a73e8"))
        self._btn_start.clicked.connect(self._on_start_pause)

        self._btn_reset = QPushButton("重置")
        self._btn_reset.setFixedHeight(40)
        self._btn_reset.setStyleSheet(self._btn_style("#757575"))
        self._btn_reset.clicked.connect(self._on_reset)

        btn_row.addWidget(self._btn_start)
        btn_row.addWidget(self._btn_reset)
        root.addLayout(btn_row)

    def _make_spin(self, lo: int, hi: int, suffix: str):
        """返回 [QSpinBox, QLabel] 一对控件。"""
        spin = QSpinBox(self)
        spin.setRange(lo, hi)
        spin.setFixedWidth(70)
        spin.setFixedHeight(36)
        spin.setAlignment(Qt.AlignCenter)
        spin.setStyleSheet(
            "QSpinBox { font-size: 16px; border: 1px solid #ccc;"
            " border-radius: 4px; padding: 2px; }"
        )
        label = QLabel(suffix, self)
        label.setStyleSheet("font-size: 15px;")
        return [spin, label]

    @staticmethod
    def _btn_style(color: str) -> str:
        return (
            f"QPushButton {{ background-color: {color}; color: white;"
            f" font-size: 15px; border-radius: 6px; }}"
            f"QPushButton:hover {{ background-color: {color}cc; }}"
            f"QPushButton:pressed {{ background-color: {color}99; }}"
        )

    # ──────────────────────────────────────────
    # 逻辑
    # ──────────────────────────────────────────

    def _total_seconds(self) -> int:
        h = self._spin_h[0].value()
        m = self._spin_m[0].value()
        s = self._spin_s[0].value()
        return h * 3600 + m * 60 + s

    def _update_display(self, seconds: int):
        t = QTime(0, 0, 0).addSecs(seconds)
        self._display.setText(t.toString("HH:mm:ss"))
        # 最后 10 秒变红提醒
        color = "#e53935" if seconds <= 10 and seconds > 0 else "#1a73e8"
        self._display.setStyleSheet(f"color: {color};")

    def _set_inputs_enabled(self, enabled: bool):
        for spin, _ in [self._spin_h, self._spin_m, self._spin_s]:
            spin.setEnabled(enabled)

    def _on_start_pause(self):
        if not self._running:
            # 开始 / 继续
            if self._remaining_ms == 0:
                total = self._total_seconds()
                if total == 0:
                    QMessageBox.warning(self, "提示", "请先设置倒计时时间！")
                    return
                self._remaining_ms = total * 1000

            self._running = True
            self._btn_start.setText("暂停")
            self._set_inputs_enabled(False)
            self._timer.start()
        else:
            # 暂停
            self._running = False
            self._btn_start.setText("继续")
            self._timer.stop()

    def _on_reset(self):
        self._timer.stop()
        self._running = False
        self._remaining_ms = 0
        self._btn_start.setText("开始")
        self._set_inputs_enabled(True)
        self._update_display(0)

    def _tick(self):
        self._remaining_ms -= 1000
        if self._remaining_ms <= 0:
            self._remaining_ms = 0
            self._timer.stop()
            self._running = False
            self._btn_start.setText("开始")
            self._set_inputs_enabled(True)
            self._update_display(0)
            self._display.setStyleSheet("color: #e53935;")
            QMessageBox.information(self, "时间到！", "⏰ 倒计时结束！")
        else:
            self._update_display(self._remaining_ms // 1000)


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = CountdownApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
