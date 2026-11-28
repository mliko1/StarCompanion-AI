# -*- coding: utf-8 -*-
"""星伴AI 家长一键启动器（产品入口为 星伴AI.exe，双击无黑色命令行窗口）。

家长使用：
  双击桌面「星伴AI」图标 → 出现一个窗口 → 点「打开训练系统」
  自动启动后端、打开浏览器、就绪后显示地址；点「停止系统」即可关闭。

开发使用：
  双击 星伴AI启动器.pyw 也可运行；运行 `python scripts/build_launcher.py`
  可打包出 星伴AI.exe 并把快捷方式装到桌面。
"""

import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
import urllib.request

if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(os.path.abspath(sys.executable))
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))

PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
if not os.path.exists(PY):
    PY = shutil.which("python") or shutil.which("python3") or sys.executable
    if getattr(sys, "frozen", False):
        PY = ""
BACKEND_URL = "http://127.0.0.1:8000"

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def is_ready():
    try:
        with urllib.request.urlopen(BACKEND_URL, timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def _desktop_dir():
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Desktop"),
        os.path.join(home, "OneDrive", "Desktop"),
        os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return ""


def _shortcut_paths():
    paths = []
    desktop = _desktop_dir()
    if desktop:
        paths.append(os.path.join(desktop, "星伴AI.lnk"))
    programs = os.path.join(
        os.environ.get("APPDATA", ""), "Microsoft", "Windows",
        "Start Menu", "Programs")
    if os.path.isdir(programs):
        paths.append(os.path.join(programs, "星伴AI.lnk"))
    return paths


def create_shortcut():
    """在桌面和开始菜单创建「星伴AI」入口，兼容中文路径与打包后的 exe。"""
    paths = _shortcut_paths()
    if not paths:
        return False, "找不到桌面或开始菜单目录"

    if getattr(sys, "frozen", False):
        target = os.path.abspath(sys.executable)
        arguments = ""
        icon = target + ",0"
    else:
        target = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(target):
            target = sys.executable
        arguments = '"' + os.path.join(ROOT, "星伴AI启动器.pyw") + '"'
        icon = target + ",0"

    # 路径通过环境变量传入 PowerShell，脚本本身全 ASCII，彻底避开中文编码问题
    env = os.environ.copy()
    env.update(XB_PATHS="|".join(paths), XB_TARGET=target, XB_ARGS=arguments,
               XB_WORKDIR=ROOT, XB_ICON=icon)
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        "foreach ($p in ($env:XB_PATHS -split '\\|')) { "
        "$sc = $ws.CreateShortcut($p); "
        "$sc.TargetPath = $env:XB_TARGET; "
        "$sc.Arguments = $env:XB_ARGS; "
        "$sc.WorkingDirectory = $env:XB_WORKDIR; "
        "$sc.IconLocation = $env:XB_ICON; "
        "$sc.Description = '星伴AI 儿童康复训练系统'; "
        "$sc.Save() }"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            env=env, capture_output=True, text=True, timeout=20,
            creationflags=CREATE_NO_WINDOW)
        if r.returncode == 0 and all(os.path.exists(p) for p in paths):
            return True, f"已创建快捷方式 {len(paths)} 处（桌面 / 开始菜单）"
        raise RuntimeError((r.stderr or r.stdout or "未知错误").strip()[:200])
    except Exception as e:
        # 兜底：VBS 用系统 ANSI 编码写到临时目录，避免 cscript 按 GBK 解析 UTF-8 中文
        try:
            import tempfile
            q = lambda s: s.replace('"', '""')
            vbs = os.path.join(tempfile.gettempdir(), "_xingban_shortcut.vbs")
            arr = ", ".join(f'"{q(p)}"' for p in paths)
            script = (
                'Set ws = CreateObject("WScript.Shell")\n'
                f'For Each p In Array({arr})\n'
                'sc = ws.CreateShortcut(p)\n'
                f'sc.TargetPath = "{q(target)}"\n'
                f'sc.Arguments = "{q(arguments)}"\n'
                f'sc.WorkingDirectory = "{q(ROOT)}"\n'
                f'sc.IconLocation = "{q(icon)}"\n'
                'sc.Description = "星伴AI 儿童康复训练系统"\n'
                'sc.Save\n'
                'Next\n'
            )
            with open(vbs, "w", encoding="mbcs") as f:
                f.write(script)
            subprocess.run(["cscript", "//nologo", vbs], check=True,
                           creationflags=CREATE_NO_WINDOW, timeout=20)
            os.remove(vbs)
            return True, f"已创建快捷方式 {len(paths)} 处（桌面 / 开始菜单）"
        except Exception as e2:
            return False, f"创建失败：{e}；兜底失败：{e2}"


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
        if not PY or not os.path.exists(PY):
            self._set("找不到 Python 运行环境，请确认 .venv 与 exe 在同一目录", "#a12d2d")
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
    if "--shortcut" in sys.argv:
        ok, msg = create_shortcut()
        print(msg)
        sys.exit(0 if ok else 1)
    Launcher().mainloop()
