"""pyxel-mcp run 驱动器：白盒版 star_voyage（run 工具按路径执行本文件）。

用 from-import 把 App 暴露到本模块全局命名空间，
便于 pyxel-mcp 自动识别 App 实例（state/until 快照的求值目标）。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from star_voyage import App

App()
