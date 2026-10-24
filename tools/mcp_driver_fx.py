"""pyxel-mcp 驱动：直达战斗场景（跳过菜单/指南流程），用于战斗反馈专项取证。

与 mcp_driver_wb 同款模式：暴露 App 类到模块命名空间（harness 据此识别并驱动），
开局即与 xe=1 的敌人交战（HP8 DEF0：正弦波首回合 N=8 一炮可杀，可验证击杀爆散）。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pyxel

import star_voyage as sv


class App(sv.App):
    """直达战斗的 App：绕过菜单/指南，构造完即与 xe=1 的敌人开战。"""

    def __init__(self):
        """手动初始化（不走 sv.App.__init__ 的菜单流程），直接落进战斗场景。"""
        pyxel.init(sv.WIN_W, sv.WIN_H, title="fx-kill")
        sv.apply_palette()                     # 最终 UI 调色板（与真实启动一致）
        sv.load_assets()
        self.ship = None
        self.world = None
        self.fight = None
        self.ending_win = False
        self.scene = None
        self._trans = None
        self.start_run(42, "正弦波")             # 建星图与飞船（内部会排队 guide 过场）
        self._trans = None                      # 抹掉排队的过场：直达战斗
        self.ship.move_to(0, 1)               # 假装已跳到敌人附近
        self.fight = sv.Fight(self.ship, 1)    # 与 xe=1 的敌人开战
        self.change_scene("fight")
        pyxel.run(self.update, self.draw)      # harness 接管主循环


App()
