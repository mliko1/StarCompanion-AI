# -*- coding: utf-8 -*-
"""语音播报服务：训练过程中的实时语音指令。

改用 Windows 自带 PowerShell + System.Speech（SAPI）播报：
- 每次播报启动一个独立 PowerShell 进程，自带干净的 COM 环境，后台进程也能正常出声；
- 相比 pyttsx3（在 uvicorn 后台进程的异步线程里会静默失败）更可靠。
"""

import subprocess
import threading
import sys

_play_lock = threading.Lock()   # 串行播放，避免多个播报声音重叠


def _play(text):
    safe = text.replace("'", "''")   # 转义单引号
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "try { $s.SelectVoice('Microsoft Huihui Voice') } catch {};"
        "$s.Rate=-1;"
        "$s.Volume=100;"
        "$s.Speak('%s')" % safe
    )
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as e:
        print(f"[tts] 播放失败: {e}", flush=True)


def speak(text):
    """异步播报一段文字（立即返回，后台播放）。"""
    if not text:
        return

    def _run():
        with _play_lock:
            _play(text)

    threading.Thread(target=_run, daemon=True).start()


def available():
    return True
