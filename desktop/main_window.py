# -*- coding: utf-8 -*-
"""儿童 Windows 桌面训练端（个性化方案 + 连续训练 + 语音鼓励）。

功能：
- 打开自动从后端拉取「今日推荐训练计划」（免手动选任务）；
- 一键「开始训练」按计划顺序连续练多个动作，练完一个自动进下一个；
- 每 250ms 显示摄像头画面，每 1s 刷新方案进度；
- 结束弹出本次完成情况（完成动作数、用时、累计 PDI、独立完成率）；
- 儿童化大按钮界面，训练全程有语音播报（后端 TTS）。

依赖：PySide6。后端需先启动（python -m server.run）。
运行：python desktop/main_window.py
"""

import json
import sys
import time
import urllib.error
import urllib.request

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QListWidget, QMainWindow,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

BACKEND = "http://127.0.0.1:8000"
KIND_CN = {"strengthen": "需加强", "consolidate": "巩固",
           "new": "新动作", "review": "复习"}


def http_get(path):
    with urllib.request.urlopen(BACKEND + path, timeout=2) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post(path, payload, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BACKEND + path, data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("星伴AI · 训练")
        self.resize(560, 800)
        self._plan = []                 # 推荐方案 [{task_id,name,kind,reason,rate}]
        self._last_status = None
        self._plan_start_time = None

        self._apply_theme()

        central = QWidget()
        central.setObjectName("central")
        root = QVBoxLayout(central)
        root.setSpacing(16)
        root.setContentsMargins(24, 22, 24, 24)

        # ---------- 标题 ----------
        title = QLabel("星伴AI · 儿童训练")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)

        # ---------- 摄像头画面 ----------
        self.video_label = QLabel("摄像头画面（点「开始」后显示）")
        self.video_label.setObjectName("video")
        self.video_label.setAlignment(Qt.AlignCenter)
        # 只固定高度，不用 Ignored 策略（Ignored 会让布局不占位、控件重叠）
        self.video_label.setFixedHeight(250)
        self.video_timer = QTimer(self)
        self.video_timer.setInterval(250)
        self.video_timer.timeout.connect(self._update_video)
        self.video_timer.start()

        # ---------- 今日训练计划 ----------
        plan_title = QLabel("今日训练计划（自动推荐）")
        plan_title.setObjectName("section")
        self.plan_list = QListWidget()
        self.plan_list.setObjectName("planList")

        # ---------- 状态 ----------
        self.status_label = QLabel("正在加载训练计划…")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)

        # ---------- 按钮 ----------
        self.start_btn = QPushButton("开始训练")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.clicked.connect(self.start_plan)
        self.stop_btn = QPushButton("结束")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.clicked.connect(self.stop_training)
        self.stop_btn.setEnabled(False)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(14)
        btn_row.addWidget(self.start_btn, 1)
        btn_row.addWidget(self.stop_btn, 1)

        root.addWidget(title)
        root.addWidget(self.video_label)
        root.addWidget(plan_title)
        root.addWidget(self.plan_list, 1)
        root.addWidget(self.status_label)
        root.addLayout(btn_row)
        self.setCentralWidget(central)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1000)
        self.poll_timer.timeout.connect(self.poll_status)

        self.load_plan()
        self._sync_backend_state()

    # ---------- 主题 ----------
    def _apply_theme(self):
        self.setStyleSheet("""
            QWidget { font-family: "SimSun", "宋体"; }
            #central { background: #f4f6fb; }
            #title { font-size: 28px; font-weight: 800; color: #2b2f3e; letter-spacing: 1px; }
            #section { font-size: 16px; font-weight: 700; color: #4a5168; }
            #video {
                background: #14161f; color: #7a8199; font-size: 15px;
                border-radius: 18px; border: 1px solid #e6e9f5;
            }
            #planList {
                font-size: 19px; border: none; background: #fff;
                border-radius: 16px; padding: 8px;
            }
            #planList::item { padding: 10px 14px; border-radius: 10px; margin: 3px 0; }
            #status { font-size: 16px; color: #5b6480; }
            #startBtn {
                font-size: 24px; font-weight: 700; padding: 18px; border-radius: 16px;
                color: #fff; border: none;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5b7cfa, stop:1 #8b5cf6);
            }
            #startBtn:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6a89ff, stop:1 #9a6cff); }
            #startBtn:disabled { background: #c9cfdd; }
            #stopBtn {
                font-size: 24px; font-weight: 700; padding: 18px; border-radius: 16px;
                color: #fff; border: none;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff7a7a, stop:1 #f56c6c);
            }
            #stopBtn:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff8c8c, stop:1 #ff6f6f); }
            #stopBtn:disabled { background: #c9cfdd; }
        """)

    # ---------- 推荐方案 ----------
    def load_plan(self):
        try:
            data = http_get("/api/plan")
        except Exception:
            self.plan_list.clear()
            self.plan_list.addItem("连不上后端，请先双击「启动训练系统.bat」")
            self.status_label.setText("后端未启动")
            return
        self._plan = data.get("plan") or []
        self.plan_list.clear()
        for i, p in enumerate(self._plan):
            kind = KIND_CN.get(p.get("kind"), "")
            tag = f"（{kind}）" if kind else ""
            self.plan_list.addItem(f"{i + 1}. {p['name']}{tag}")
        if self._plan:
            self.status_label.setText(
                f"今日计划 {len(self._plan)} 个动作，点「开始训练」就开始啦")
        else:
            self.plan_list.addItem("暂无训练计划，先开始一次训练吧")
            self.status_label.setText("暂无训练计划")

    def _sync_backend_state(self):
        """打开时同步后端训练状态：上次训练若未正常结束，自动接管显示。"""
        try:
            st = http_get("/api/training/status")
        except Exception:
            return
        if st.get("state") == "running":
            self._last_status = st
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.poll_timer.start()
            self.status_label.setText(
                "检测到上次训练未结束，点「结束」即可终止")

    # ---------- 开始 / 结束 ----------
    def start_plan(self):
        if not self._plan:
            QMessageBox.warning(self, "提示", "暂无训练计划，无法开始")
            return
        task_ids = [p["task_id"] for p in self._plan]
        try:
            resp = http_post("/api/training/start_plan", {"task_ids": task_ids})
        except Exception as e:
            # 首次开摄像头+加载模型可能较慢；超时后确认后端实际状态
            try:
                st = http_get("/api/training/status")
            except Exception:
                st = {}
            if st.get("state") == "running":
                resp = {"ok": True, "msg": st.get("message") or "训练中"}
            else:
                QMessageBox.critical(self, "启动失败", f"无法启动训练：{e}")
                return
        if not resp.get("ok"):
            # 后端残留上次未结束的训练时，自动终止旧的并重试一次
            if "已有训练" in (resp.get("msg") or ""):
                try:
                    http_post("/api/training/stop", {}, timeout=15)
                    resp = http_post("/api/training/start_plan",
                                     {"task_ids": task_ids})
                except Exception:
                    pass
        if not resp.get("ok"):
            QMessageBox.warning(self, "启动失败", resp.get("msg", "未知错误"))
            return
        self._plan_start_time = time.time()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.poll_timer.start()
        self.status_label.setText(resp.get("msg", "训练中"))

    def stop_training(self):
        self.poll_timer.stop()
        try:
            http_post("/api/training/stop", {})
        except Exception:
            pass
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._show_result()

    # ---------- 轮询 ----------
    def poll_status(self):
        try:
            st = http_get("/api/training/status")
        except Exception:
            return
        self._last_status = st
        self._update_plan_list(st)
        if st.get("plan_mode"):
            idx = st.get("plan_index", 0) + 1
            total = st.get("plan_total", len(self._plan))
            name = self._plan[idx - 1]["name"] if 0 < idx <= len(self._plan) else ""
            hint = "√ 做对了，保持住！" if st.get("detected_now") else "请跟着语音做动作"
            self.status_label.setText(f"第 {idx}/{total} 个动作：{name}　{hint}")

    def _update_plan_list(self, st):
        results = st.get("plan_results") or []
        idx = st.get("plan_index", 0)
        for i in range(self.plan_list.count()):
            item = self.plan_list.item(i)
            name = self._plan[i]["name"] if i < len(self._plan) else str(i + 1)
            if i < len(results):
                done = results[i].get("completed")
                item.setText(f"[{'√' if done else '×'}] {i + 1}. {name}")
                item.setForeground(Qt.darkGreen if done else Qt.red)
            elif i == idx:
                item.setText(f"[>] {i + 1}. {name}")
                item.setForeground(Qt.blue)
            else:
                item.setText(f"[ ] {i + 1}. {name}")
                item.setForeground(Qt.gray)

    # ---------- 摄像头画面 ----------
    def _update_video(self):
        try:
            req = urllib.request.Request(BACKEND + "/api/camera/snapshot")
            with urllib.request.urlopen(req, timeout=1) as r:
                data = r.read()
        except Exception:
            return
        pix = QPixmap()
        if not pix.loadFromData(data):
            return
        # 缩放目标用固定高度，宽度取布局分配值（不低于 320），
        # 保证 pixmap 尺寸恒定 ≤ 框体，不会形成"放大循环"
        w = max(self.video_label.width(), 320)
        self.video_label.setPixmap(pix.scaled(
            w, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # ---------- 结果弹窗 ----------
    def _show_result(self):
        st = self._last_status or {}
        results = st.get("plan_results") or []
        done = sum(1 for r in results if r.get("completed"))
        total = len(results) or len(self._plan)

        elapsed = ""
        if self._plan_start_time:
            sec = int(time.time() - self._plan_start_time)
            elapsed = f"\n用时：{sec // 60} 分 {sec % 60} 秒"

        stats_txt = ""
        try:
            dash = http_get("/api/reports/dashboard")
            pdi = dash.get("pdi")
            ind = dash.get("independent_rate")
            if pdi is not None and ind is not None:
                stats_txt = (f"\n累计提示依赖指数 PDI：{pdi:.2f}"
                             f"\n累计独立完成率：{ind * 100:.0f}%")
        except Exception:
            pass

        text = f"本次完成 {done}/{total} 个动作{elapsed}{stats_txt}\n\n（识别结果仅供参考，请家长确认）"
        QMessageBox.information(self, "训练结果", text)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
