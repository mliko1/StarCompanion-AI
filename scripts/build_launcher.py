# -*- coding: utf-8 -*-
"""把家长启动器打包为产品入口 星伴AI.exe，并安装桌面快捷方式。

用法：
    python scripts/build_launcher.py            # 打包 + 装桌面快捷方式
    python scripts/build_launcher.py --no-shortcut
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
if not os.path.exists(PY):
    PY = sys.executable
EXE = os.path.join(ROOT, "星伴AI.exe")
ICON = os.path.join(ROOT, "assets", "xingban.ico")
WORK = os.path.join(ROOT, "build", "launcher")


def run(cmd, **kwargs):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True, **kwargs)


def main():
    if not os.path.exists(ICON):
        run([PY, os.path.join(ROOT, "scripts", "make_icon.py")])
    try:
        run([PY, "-m", "PyInstaller", "--version"])
    except subprocess.CalledProcessError:
        run([PY, "-m", "pip", "install", "pyinstaller>=6.0"])

    run([
        PY, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--noconsole",
        "--name", "星伴AI",
        "--distpath", ROOT, "--workpath", WORK, "--specpath", WORK,
        "--icon", ICON,
        os.path.join(ROOT, "星伴AI启动器.pyw"),
    ])
    if not os.path.exists(EXE):
        raise SystemExit("打包失败：未生成 " + EXE)
    print("已生成产品入口:", EXE)

    if "--no-shortcut" not in sys.argv:
        code = subprocess.run([EXE, "--shortcut"], cwd=ROOT, timeout=30).returncode
        print("桌面快捷方式安装结果:", "成功" if code == 0 else "失败")


if __name__ == "__main__":
    main()
