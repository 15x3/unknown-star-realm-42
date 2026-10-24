"""pyxel-mcp 驱动器：运行 CRT 实验室 v3（独立研究脚本，不接游戏）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import crt_lab

crt_lab.main()
