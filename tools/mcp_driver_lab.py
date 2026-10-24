"""pyxel-mcp 驱动器：运行效果实验室 effects_lab（独立演示，不接游戏）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import effects_lab

effects_lab.main()
