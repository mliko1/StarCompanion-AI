# -*- coding: utf-8 -*-
"""儿童 Windows 桌面训练端（升级建议文档第六阶段）。

面向儿童的大按钮界面：展示任务、播放语音提示、观察动作、记录。
依赖：PySide6（pip install PySide6）

注意：本模块为框架，需安装 PySide6 后测试；语音提示第一版先用文字代替。
运行：python desktop/main_window.py
"""

import sys

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication, QLabel, QListWidget, QMainWindow, QPushButton,
        QVBoxLayout, QWidget,
    )
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


class MainWindow(QMainWindow):
    """儿童训练端主窗口：大按钮 + 步骤提示。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("星伴AI · 训练")
        self.resize(480, 680)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setSpacing(16)

        self.title_label = QLabel("今天的训练任务")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 26px; font-weight: bold;")

        self.task_label = QLabel("拍手")
        self.task_label.setAlignment(Qt.AlignCenter)
        self.task_label.setStyleSheet("font-size: 40px; color: #409eff;")

        self.step_list = QListWidget()
        for s in ["寻找玩具", "接近玩具", "拿起玩具", "移动玩具", "放入收纳盒"]:
            self.step_list.addItem(s)
        self.step_list.setStyleSheet("font-size: 20px;")

        self.hint_label = QLabel("跟着做哦，加油！")
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setStyleSheet("font-size: 18px; color: #999;")

        self.start_btn = QPushButton("开始")
        self.start_btn.setStyleSheet(
            "font-size: 24px; padding: 16px; background: #409eff; color: white;")
        self.stop_btn = QPushButton("结束")
        self.stop_btn.setStyleSheet(
            "font-size: 24px; padding: 16px; background: #f56c6c; color: white;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.task_label)
        layout.addWidget(self.step_list)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        self.setCentralWidget(central)


def main():
    if not HAS_PYSIDE6:
        print("未安装 PySide6，请先执行：pip install PySide6")
        return
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
