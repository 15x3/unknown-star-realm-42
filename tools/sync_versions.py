"""从白盒版 star_voyage.py 生成资产版 star_voyage_assets.py。

两版约定“唯一的区别是是否有资产”：本工具把白盒版中标记的【资产层区块】
整体替换为资产版实现、替换文件头的版本说明行，其余代码逐字复制——
从机制上保证两版游戏逻辑一致（同一套 pytest 会跑两遍来验证）。

运行：python tools/sync_versions.py
核对：diff star_voyage.py star_voyage_assets.py   # 差异应只在文件头与资产层
注意：请只编辑 star_voyage.py（白盒版），改完重跑本工具同步出资产版。
"""
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "star_voyage.py")            # 源：白盒版（唯一手写处）
DST = os.path.join(ROOT, "star_voyage_assets.py")    # 目标：资产版（生成物）

# ---- 文件头版本说明行：白盒 -> 资产 ----
WB_NOTE = "本文件为【无资产·纯白盒】版本：不加载任何资源文件，图形用几何图元绘制，全程静音；"
AS_NOTE = ("本文件为【带资产】版本：启动时加载 assets/star_voyage.pyxres"
           "（由 tools/make_assets.py 生成，可用 pyxel edit 润色），精灵 blt 绘制，带音效与 BGM；")

# ---- 资产层区块的起止围栏（围栏本身随区块一起被替换） ----
START_WB = "# ==================== 资产层（两版唯一差异区·白盒） ===================="
END = "# ==================== 全局状态（沿用骨架约定） ===================="

# ---- 资产版的资产层区块全文 ----
ASSET_REGION = '''# ==================== 资产层（两版唯一差异区·资产版） ====================

USE_ASSETS = True  # 资产版：启动时加载 .pyxres，精灵经 blt 绘制，音效/BGM 经 play 播放

# 资产包路径：随本文件定位 assets/star_voyage.pyxres
# （包内：图像库0顶部一排 8x8 精灵=船/星球/敌/升级；音效槽 0-7；音乐 0=BGM）
ASSET_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "assets", "star_voyage.pyxres"))


def load_assets():
    """加载资产包（App 启动时调用一次）。BGM 不在此启动——由 play_bgm 随场景切换。"""
    pyxel.load(ASSET_PATH)              # 读入图像/音效/音乐到各资源库槽位


def draw_sprite(sx, sy, spr):
    """把精灵槽位 spr=(u,v) 的 8x8 图块 blt 到屏幕 (sx,sy)（中心对齐，色键0透明）。"""
    pyxel.blt(sx - 4, sy - 4,   # 屏幕左上角 = 中心减去半宽半高（8x8 -> 4px）
              0,                # 图像库 0（四个精灵都排在图库顶部一排）
              spr[0], spr[1],   # 精灵在图库内的 (u, v) 坐标
              8, 8,             # 图块尺寸 8x8
              0)                # 色键 0：图库中 0 号色按透明处理


def play_sfx(snd):
    """在通道3播放一次音效槽位 snd（0-18；通道3 为音效专用，与 BGM 通道并存）。"""
    pyxel.play(3, snd)


def play_bgm(music):
    """切换并循环播放背景音乐槽位 music（0=菜单 1=地图 2=战斗 3=结算）。"""
    pyxel.stop()                        # 先停旧曲（含残留音效），再起新曲干净利落
    pyxel.playm(music, loop=True)

'''

def main():
    """读白盒版 -> 替换版本行与资产层区块 -> 写出资产版。"""
    with open(SRC, encoding="utf-8") as f:
        text = f.read()
    # 三道围栏都必须恰好存在，否则拒绝生成（防止源文件被误改后静默出错版）
    for fence in (WB_NOTE, START_WB, END):
        if text.count(fence) != 1:
            raise SystemExit(f"围栏不唯一或缺失: {fence!r}")
    pre, rest = text.split(START_WB, 1)       # 资产层之前的部分
    _, post = rest.split(END, 1)              # 资产层之后的部分（白盒区块弃用）
    out = pre.replace(WB_NOTE, AS_NOTE, 1) + ASSET_REGION + END + post
    with open(DST, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("written:", DST)

if __name__ == "__main__":
    main()
