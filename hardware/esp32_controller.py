# -*- coding: utf-8 -*-
"""ESP32 智能交互盒串口控制器（升级建议文档第四阶段硬件）。

功能：通过 USB 串口与 ESP32 通信，控制大按键、LED、蜂鸣器。
依赖：pyserial（pip install pyserial）

协议（需与 ESP32 固件约定一致，示例）：
- 发送 "LED:ON" / "LED:OFF"       控制 LED
- 发送 "BUZZ:500"                  蜂鸣 500 毫秒
- 读取按键：ESP32 主动上报 "BTN:1"（按下）/ "BTN:0"（松开）

注意：本模块为软件框架，需配合实际 ESP32 硬件与固件联调。
未连接设备时所有操作优雅降级，不阻塞训练主流程。
"""

import threading
import time

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    serial = None
    HAS_SERIAL = False


class ESP32Controller:
    def __init__(self, port="COM3", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.connected = False
        self._lock = threading.Lock()
        self._read_thread = None
        self._running = False
        self.last_button = None          # {"pressed": bool, "ts": float}
        self.on_button = None            # 回调 on_button(pressed)

    def connect(self):
        if not HAS_SERIAL:
            return {"ok": False, "msg": "未安装 pyserial，请先执行 pip install pyserial"}
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.connected = True
            self._running = True
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return {"ok": True, "msg": f"已连接 {self.port}"}
        except Exception as e:
            self.connected = False
            return {"ok": False, "msg": f"串口连接失败: {e}"}

    def _read_loop(self):
        while self._running and self.ser:
            try:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if line.startswith("BTN:"):
                    pressed = line.split(":")[1] == "1"
                    self.last_button = {"pressed": pressed, "ts": time.time()}
                    if self.on_button:
                        self.on_button(pressed)
            except Exception:
                time.sleep(0.05)

    def set_led(self, on):
        return self._send(f"LED:{'ON' if on else 'OFF'}")

    def buzz(self, ms=500):
        return self._send(f"BUZZ:{int(ms)}")

    def _send(self, cmd):
        if not self.connected:
            return {"ok": False, "msg": "设备未连接"}
        try:
            with self._lock:
                self.ser.write((cmd + "\n").encode("utf-8"))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def status(self):
        return {"connected": self.connected, "port": self.port,
                "last_button": self.last_button}

    def close(self):
        self._running = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.connected = False


# 全局单例（未连接时 status 返回 connected=False，不报错）
esp32 = ESP32Controller()
