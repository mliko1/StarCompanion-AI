# -*- coding: utf-8 -*-
"""设备服务：统一管理 ESP32 智能交互盒（升级建议文档第四阶段）。

第一版策略：设备未连接时所有操作优雅降级（返回 ok=False），
不阻塞训练主流程；后续联调硬件时再接入实际反馈。
"""

from hardware.esp32_controller import esp32


def device_status():
    return esp32.status()


def connect_device(port="COM3"):
    """连接 ESP32；可指定端口（如 COM3），已连接时先切换端口再开。"""
    if port and port != esp32.port:
        if esp32.connected:
            esp32.close()
        esp32.port = port
    return esp32.connect()


def set_led(on):
    return esp32.set_led(on)


def buzz(ms=500):
    return esp32.buzz(ms)


def on_button_pressed(callback):
    """注册按键回调（ESP32 按键按下时触发）。"""
    esp32.on_button = callback
