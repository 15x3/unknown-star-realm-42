"""字体探针：验证凤凰点阵体在 pyxel 下渲染中文（headless，供 MCP 截帧）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pyxel

pyxel.init(240, 160, headless=True)
F12 = os.path.join(ROOT, "assets", "fonts", "VonwaonBitmap-12px.ttf")
F16 = os.path.join(ROOT, "assets", "fonts", "VonwaonBitmap-16px.ttf")
font12 = pyxel.Font(F12, 12)   # 12px 原生字号
font16 = pyxel.Font(F16, 16)   # 16px 原生字号

FRAME = [0]

def update():
    FRAME[0] += 1
    if FRAME[0] > 8:
        pyxel.quit()

def draw():
    pyxel.cls(0)
    pyxel.text(8, 8, "凤凰点阵体 12px：正弦波引擎", 7, font12)
    pyxel.text(8, 26, "星球 敌人 升级 护盾 能量 火炮", 10, font12)
    pyxel.text(8, 48, "16px 标题字测试：逃离成功！", 11, font16)
    pyxel.text(8, 90, "ABC 123 GEO SIN", 6, font12)
    # 宽度测量 API
    w = font12.text_width("宽度测量ABC")
    pyxel.line(8, 76, 8 + w, 76, 8)
    pyxel.text(8, 108, f"w={w}", 7, font12)

pyxel.run(update, draw)
