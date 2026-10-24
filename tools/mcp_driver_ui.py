"""pyxel-mcp 驱动：直达结算场景（最终 UI 的胜/负样式取证）。

绕过 App.__init__ 的 pyxel.run 阻塞，直接构造一局并跳到 EndingScene。
"""
import pyxel

import star_voyage as sv


def build():
    """构造一个已进入胜利结算的 App。"""
    app = sv.App.__new__(sv.App)
    pyxel.init(sv.WIN_W, sv.WIN_H, title="ui-ending")
    sv.apply_palette()                     # 最终 UI 调色板（与真实启动一致）
    sv.load_assets()
    app.ship = None
    app.world = None
    app.fight = None
    app.ending_win = True                  # 胜利样式（败北仅文字变红，布局相同）
    app.scene = None
    app._trans = None
    app.start_run(42, "正弦波")             # 建星图与飞船（结算页不依赖，走完整流程）
    app._trans = None                      # 抹掉 start_run 排队的地图淡入过场
    app.change_scene("ending")             # 直接进结算场景
    return app


APP = build()


def update():
    """每帧逻辑：转发给场景。"""
    APP.update()


def draw():
    """每帧绘制：转发给场景。"""
    APP.draw()


pyxel.run(update, draw)
