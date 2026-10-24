"""pyxel-mcp run 驱动器：直达结算场景（跳过对局，用于最终 UI 快照验收）。

正常对局要到 x>42 才能见结算页，快照验收用本驱动直接切场景：
临时占住 pyxel.run 拿到 App 实例 -> 建局 -> 立即切 EndingScene -> 恢复主循环。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pyxel
from star_voyage import App

_real_run = pyxel.run
pyxel.run = lambda u, d: None      # 先占住主循环：只为拿到 App 实例
app = App()                        # pyxel.init + 换装 YU-NO 调色板 + 菜单
pyxel.run = _real_run              # 恢复真主循环
app.start_run(42, "正弦波")        # 建局（写种子/星图/飞船）
app.ending_win = True              # 胜利结算样式
app.change_scene("ending")         # 立即切结算（无过场）
app._trans = None                  # 清掉 start_run 排队的地图过场
pyxel.run(app.update, app.draw)    # 正常起跑（ESC 退出）
