# -*- coding: utf-8 -*-
"""星伴AI 家长一键启动器（双击运行，无黑色命令行窗口）。

家长使用：
  双击本文件 → 出现一个窗口 → 点「打开训练系统」
  自动启动后端、打开浏览器、就绪后显示地址；点「停止系统」即可关闭。
  也可点「创建桌面快捷方式」，以后从桌面图标打开。

技术：tkinter（Python 标准库）+ subprocess；不依赖额外包。
"""

import os
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
PYW = sys.executable
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
if not os.path.exists(PY):
    PY = sys.executable
BACKEND_URL = "http://127.0.0.1:8000"

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def is_ready():
    try:
        with urllib.request.urlopen(BACKEND_URL, timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def create_shortcut():
    """在桌面创建「星伴AI」快捷方式（VBS 生成 .lnk，兼容中文路径）。"""
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop):
        desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
    if not os.path.isdir(desktop):
        return False, "找不到桌面目录"
    vbs = os.path.join(ROOT, "_make_shortcut.vbs")
    lnk = os.path.join(desktop, "星伴AI.lnk")
    target = os.path.join(ROOT, "星伴AI启动器.pyw")
    script = (
        'Set ws = CreateObject("WScript.Shell")\n'
        f'sc = ws.CreateShortcut("{lnk}")\n'
        f'sc.TargetPath = "{PYW}"\n'
        f'sc.Arguments = """{target}"""\n'
        f'sc.WorkingDirectory = "{ROOT}"\n'
        f'sc.IconLocation = "{PYW},0"\n'
        'sc.Description = "星伴AI 儿童康复训练系统"\n'
        'sc.Save\n'
    )
    try:
        with open(vbs, "w", encoding="utf-8") as f:
            f.write(script)
        subprocess.run(["cscript", "//nologo", vbs],
                       creationflags=CREATE_NO_WINDOW, check=True)
        os.remove(vbs)
        return True, f"已创建桌面快捷方式：{lnk}"
    except Exception as e:
        return False, f"创建失败：{e}"


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("星伴AI · 一键启动")
        self.geometry("520x380")
        self.resizable(False, False)
        self.configure(bg="#f3f7fc")
        self.proc = None
        self._build()

    def _build(self):
        tk.Label(self, text="星伴AI", font=("Microsoft YaHei", 30, "bold"),
                 fg="#0b63ce", bg="#f3f7fc").pack(pady=(26, 4))
        tk.Label(self, text="儿童家庭康复训练辅助系统", font=("Microsoft YaHei", 12),
                 fg="#7b8aa0", bg="#f3f7fc").pack()
        self.status = tk.Label(self, text="准备就绪，点下面按钮开始",
                               font=("Microsoft YaHei", 11), fg="#4b5568",
                               bg="#f3f7fc", wraplength=460)
        self.status.pack(pady=24)

        btn_style = dict(font=("Microsoft YaHei", 13, "bold"), fg="white",
                         width=22, height=2, relief="flat", cursor="hand2")
        tk.Button(self, text="打开训练系统", bg="#0b63ce",
                  command=self.start_system, **btn_style).pack(pady=5)
        tk.Button(self, text="打开儿童训练大屏", bg="#2e9e6b",
                  command=self.open_screen, **btn_style).pack(pady=5)
        row = tk.Frame(self, bg="#f3f7fc")
        row.pack(pady=10)
        tk.Button(row, text="创建桌面快捷方式", font=("Microsoft YaHei", 10),
                  bg="#e8eef7", fg="#26374d", command=self.shortcut,
                  relief="flat", cursor="hand2").pack(side="left", padx=6)
        tk.Button(row, text="停止系统", font=("Microsoft YaHei", 10),
                  bg="#f5d6d6", fg="#a12d2d", command=self.stop_system,
                  relief="flat", cursor="hand2").pack(side="left", padx=6)

    def _set(self, text, color="#4b5568"):
        self.status.config(text=text, fg=color)
        self.update_idletasks()

    def start_system(self):
        if is_ready():
            self._set("系统已经在运行，正在打开浏览器…", "#2e9e6b")
            webbrowser.open(BACKEND_URL)
            return
        self._set("正在启动，请稍候约 10 秒…", "#a06a1f")
        try:
            self.proc = subprocess.Popen(
                [PY, "-m", "server.run"], cwd=ROOT,
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self._set(f"启动失败：{e}", "#a12d2d")
            return
        threading.Thread(target=self._wait_ready, daemon=True).start()

    def _wait_ready(self):
        for _ in range(60):
            if is_ready():
                self.after(0, lambda: self._set("启动成功！浏览器已打开", "#2e9e6b"))
                webbrowser.open(BACKEND_URL)
                return
            if self.proc and self.proc.poll() is not None:
                self.after(0, lambda: self._set("启动失败，请查看 README 排错", "#a12d2d"))
                return
            time.sleep(1)
        self.after(0, lambda: self._set("启动超时，请检查杀毒软件是否拦截", "#a12d2d"))

    def open_screen(self):
        if not is_ready():
            self._set("请先点「打开训练系统」", "#a06a1f")
            return
        webbrowser.open(BACKEND_URL + "/#/training-screen")
        self._set("已打开训练大屏", "#2e9e6b")

    def stop_system(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
            self.proc = None
            self._set("系统已停止", "#4b5568")
        else:
            self._set("系统未由本启动器运行（可在任务管理器结束 python 进程）", "#a06a1f")

    def shortcut(self):
        ok, msg = create_shortcut()
        self._set(msg, "#2e9e6b" if ok else "#a12d2d")


if __name__ == "__main__":
    Launcher().mainloop()
