# -*- coding: utf-8 -*-
"""
星伴AI 第一阶段环境测试程序
检查：Python / NumPy / OpenCV / MediaPipe / 摄像头
运行方式：在项目根目录执行
    .venv\\Scripts\\python.exe environment_test\\test_python.py
"""

import sys

results = []  # 保存每项检查结果 (名称, 是否成功, 信息)


def record(name, ok, info=""):
    results.append((name, ok, info))
    mark = "[成功]" if ok else "[失败]"
    print(f"{mark} {name}" + (f" —— {info}" if info else ""))


# ---------- 1. Python ----------
record("1. Python 运行",
       True,
       f"版本 {sys.version.split()[0]}（{sys.executable}）")

# ---------- 2. NumPy ----------
try:
    import numpy
    record("2. NumPy 导入", True, f"版本 {numpy.__version__}")
except Exception as e:
    record("2. NumPy 导入", False, f"错误: {e}")

# ---------- 3. OpenCV ----------
cv2 = None
try:
    import cv2
    record("3. OpenCV 导入", True, f"版本 {cv2.__version__}")
except Exception as e:
    record("3. OpenCV 导入", False, f"错误: {e}")

# ---------- 4. MediaPipe ----------
try:
    import mediapipe
    record("4. MediaPipe 导入", True, f"版本 {mediapipe.__version__}")
except Exception as e:
    record("4. MediaPipe 导入", False, f"错误: {e}")

# ---------- 5. 摄像头 ----------
if cv2 is not None:
    cap = None
    opened = False
    for idx in range(3):  # 依次尝试摄像头 0、1、2
        try:
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                ok, frame = cap.read()
                if ok and frame is not None:
                    h, w = frame.shape[:2]
                    record("5. 摄像头检测", True,
                           f"摄像头 {idx} 可用，分辨率 {w}x{h}")
                    opened = True
                cap.release()
                if opened:
                    break
            else:
                cap.release()
        except Exception as e:
            record("5. 摄像头检测", False, f"错误: {e}")
            opened = True  # 已记录错误，避免重复
            break
    if not opened:
        record("5. 摄像头检测", False,
               "未检测到可用摄像头。请检查：① 电脑是否自带/外接摄像头；"
               "② 是否被其他软件（如腾讯会议）占用；③ Windows 隐私设置中"
               "是否允许应用访问摄像头。")
else:
    record("5. 摄像头检测", False, "OpenCV 未导入，无法测试摄像头")

# ---------- 汇总 ----------
print("-" * 50)
failed = [r for r in results if not r[1]]
if failed:
    print(f"共 {len(results)} 项检查，{len(failed)} 项失败：")
    for name, _, info in failed:
        print(f"  - {name}: {info}")
    sys.exit(1)
else:
    print(f"全部 {len(results)} 项检查通过，开发环境就绪！")
