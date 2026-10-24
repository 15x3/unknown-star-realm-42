"""pyxel-mcp run 驱动器：资产版 star_voyage_assets（run 工具按路径执行本文件）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from star_voyage_assets import App

App()
