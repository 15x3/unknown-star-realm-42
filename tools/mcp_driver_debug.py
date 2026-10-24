"""诊断驱动器：记录当前场景名到 App 实例，供 run 的 state 快照观察。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from star_voyage import App as _BaseApp


class App(_BaseApp):
    """在原 App 上加 scene_name 观察（不改变任何游戏行为）。"""

    scene_name = "menu"

    def change_scene(self, name):
        self.scene_name = name          # 记录切换目标名
        super().change_scene(name)


App()
