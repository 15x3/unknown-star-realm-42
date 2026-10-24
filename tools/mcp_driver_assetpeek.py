"""资产探针：加载资产包并即刻退出，供 read_image/read_audio 检查。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pyxel

pyxel.init(32, 8, headless=True)
pyxel.load(os.path.join(ROOT, "assets", "star_voyage.pyxres"))
pyxel.run(pyxel.quit, lambda: None)   # 进主循环一帧即退，让 MCP 完成捕获
