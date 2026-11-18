# -*- coding: utf-8 -*-
"""语音播报服务：训练过程中的实时语音指令。

基于 pyttsx3（Windows SAPI5 引擎），异步播报，不阻塞训练主流程。
未安装引擎或系统无声卡时优雅降级（HAS_TTS=False，静默）。
"""

import threading

try:
    import pyttsx3
    _engine = pyttsx3.init()
    try:
        # 优先选中文语音
        for v in _engine.getProperty("voices"):
            name = (v.name or "").lower()
            if "chinese" in name or "zh" in str(v.id).lower():
                _engine.setProperty("voice", v.id)
                break
    except Exception:
        pass
    _engine.setProperty("rate", 160)   # 语速稍慢，适合儿童听清
    _engine.setProperty("volume", 0.9)
    HAS_TTS = True
except Exception:
    _engine = None
    HAS_TTS = False

_lock = threading.Lock()


def speak(text):
    """异步播报一段文字（立即返回，后台播放）。"""
    if not HAS_TTS or not text:
        return

    def _run():
        try:
            with _lock:
                _engine.say(text)
                _engine.runAndWait()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def available():
    return HAS_TTS
