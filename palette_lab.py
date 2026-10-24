"""调色板实验室 —— 同一张图，切换不同配色方案。

用途：示范性脚本（调研/观感评估），不接入 star_voyage 游戏本体。
     按 [←]/[→] 或数字键 1-8 切换调色板；画面内容完全不变，
     只改写 pyxel 的 16 个调色板槽位（pyxel.colors 运行时可写，已实测）。

配色来源：
  · pyxel 原生 16 色（启动时抓取默认值，作为第 1 页与还原基准）
  · lospec.com（.pal 文件存于 assets/palettes/，启动时解析）：
      PICO-8 / Sweetie 16 / Endesga 16 / Steam Lords / Original GameBoy
  · 按用户规格构造（"灰阶"=基色的明暗版本，非中性灰）：
      「8位·亮暗」= 8 色 × 亮/暗两档（CGA 兼容结构，IBM CGA 16 色标准值）
      「4位·四档明暗」= 4 基色 × 各 4 档亮度（25%/50%/75%/100%）

GameBoy 只有 4 色：按"pyxel 原生各槽位亮度"映射到 4 档绿灰（模拟 DMG 屏幕）。
运行：python palette_lab.py（240x160；ESC 退出）
"""
import math
import os

import pyxel

W, H = 240, 160
T = 0                       # 帧计数（场景动画用）
IDX = 0                     # 当前调色板下标
PALETTES = []               # [(名称, 来源, [16 个 0xRRGGBB])]，启动时填充
FONT_12 = None              # 凤凰点阵体（init 后加载）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAL_DIR = os.path.join(BASE_DIR, "assets", "palettes")
FONT_PATH = os.path.join(BASE_DIR, "assets", "fonts", "VonwaonBitmap-12px.ttf")


def load_font():
    """惰性加载凤凰点阵体 12px（须在 pyxel.init 之后）。"""
    global FONT_12
    if FONT_12 is None:
        FONT_12 = pyxel.Font(FONT_PATH, 12)


def txt(x, y, s, col):
    """统一文本绘制（中文）。"""
    pyxel.text(x, y, s, col, FONT_12)


def parse_pal(path):
    """解析 lospec 的 JASC-PAL 文件（头三行后每行一个 'R G B'）。"""
    colors = []
    with open(path, encoding="ascii") as f:
        lines = f.read().split("\n")
    for line in lines[3:]:                       # 跳过 JASC-PAL / 版本 / 色数
        parts = line.split()
        if len(parts) == 3:
            r, g, b = (int(p) for p in parts)
            colors.append(r << 16 | g << 8 | b)  # 打包成 0xRRGGBB
    return colors


def luminance(rgb):
    """相对亮度（加权绿色——人眼对绿最敏感的标准近似）。"""
    r, g, b = (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255
    return 0.299 * r + 0.587 * g + 0.114 * b


def expand_gb(gb4, base16):
    """4 色 GameBoy -> 16 槽：按 base16 各槽亮度分桶映射到 4 档绿灰。"""
    out = []
    for c in base16:
        lum = luminance(c)
        bucket = 0 if lum < 60 else 1 if lum < 120 else 2 if lum < 190 else 3
        out.append(gb4[bucket])
    return out


def build_palettes(default16):
    """构建全部 8 套配色（lospec 解析 + 构造 + 原生）。"""
    pals = [("pyxel 原生 16 色", "引擎默认", list(default16))]
    for slug, name in [("pico-8", "PICO-8"),
                       ("sweetie-16", "Sweetie 16"),
                       ("endesga-16", "Endesga 16"),
                       ("steam-lords", "Steam Lords")]:
        cols = parse_pal(os.path.join(PAL_DIR, slug + ".pal"))
        pals.append((name, "lospec.com/palette-list/" + slug, cols[:16]))
    gb4 = parse_pal(os.path.join(PAL_DIR, "original-gameboy.pal"))
    pals.append(("GameBoy 绿灰", "lospec.com/palette-list/original-gameboy",
                 expand_gb(gb4, default16)))
    # 「8位·亮暗」：CGA 兼容——0-7 暗色系（含黑/浅灰），8-15 亮色系（含深灰/白）
    cga = [
        0x000000, 0x0000AA, 0x00AA00, 0x00AAAA,          # 黑/暗蓝/暗绿/暗青
        0xAA0000, 0xAA00AA, 0xAA5500, 0xAAAAAA,          # 暗红/暗紫/暗棕/浅灰
        0x555555, 0x5555FF, 0x55FF55, 0x55FFFF,          # 深灰/亮蓝/亮绿/亮青
        0xFF5555, 0xFF55FF, 0xFFFF55, 0xFFFFFF,          # 亮红/亮紫/亮黄/白
    ]
    pals.append(("8位·亮暗（CGA 兼容）", "8 亮 + 8 暗（IBM CGA 标准值构造）", cga))
    # 「4位·四档明暗」：4 个基色 × 各自 4 档明暗（亮度 25%/50%/75%/100%），
    # 共 16 槽；按整体亮度从深到浅布槽，场景明暗关系大致保持
    # （"灰阶"=每个基色的明暗版本，而非中性灰——按用户澄清的语义构造）
    bases = [(36, 102, 231),    # 蓝（天空/阴影系）
             (28, 173, 96),     # 绿（星球/地面系）
             (255, 140, 36),    # 橙（太阳/尾焰系）
             (232, 52, 66)]     # 红（敌碟/警示系）
    quads = []
    for r, g, b in bases:
        for f in (0.25, 0.5, 0.75, 1.0):         # 每基色压暗三档
            quads.append((int(r * f), int(g * f), int(b * f)))
    quads.sort(key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
    gray4 = [c[0] << 16 | c[1] << 8 | c[2] for c in quads]
    pals.append(("4位·四档明暗", "4 色 × 4 档明暗（按规格构造）", gray4))
    return pals


def apply_palette(pal):
    """把 16 个颜色写入 pyxel 调色板槽位——切换配色就这一步。"""
    for i in range(16):
        pyxel.colors[i] = pal[i]


# ==================== 场景（全部按色号绘制，不含任何绝对颜色） ====================
def draw_scene():
    """绘制示范场景：天空/星/日/山/地/飞船/敌碟/水晶——只用色号 0-15。

    场景刻意覆盖全部 16 个槽位（配合底部两条色带），任何配色下都能看出差异。
    """
    # 天空：三条横向色带（上深下浅，用 1/2/3 号暗色槽）
    pyxel.rect(0, 20, W, 40, 1)
    pyxel.rect(0, 60, W, 30, 2)
    pyxel.rect(0, 90, W, 12, 3)
    # 星星：亮/次亮色点（6/7 号）
    for i in range(14):
        sx = (i * 47 + 11) % W
        sy = 24 + (i * 29) % 60
        pyxel.pset(sx, sy, 7 if i % 3 == 0 else 6)
        if i % 4 == 0:                            # 大星带十字光芒
            pyxel.pset(sx - 1, sy, 6)
            pyxel.pset(sx + 1, sy, 6)
    # 太阳：9 号本体 + 14 号辉光边（在多数配色里是暖色槽）
    pyxel.circb(190, 52, 14, 14)
    pyxel.circ(190, 52, 11, 9)
    pyxel.circ(190, 52, 6, 10)
    # 远山：4 号暗色三角群
    for k in range(4):
        bx = 20 + k * 60
        pyxel.tri(bx, 102, bx + 34, 102, bx + 17, 70 + (k % 2) * 12, 4)
    # 地面：3 号基底 + 5 号抖动点缀
    pyxel.rect(0, 102, W, 30, 3)
    for i in range(60):
        gx = (i * 37) % W
        gy = 104 + (i * 13) % 28
        if (gx + gy) % 2 == 0:                    # 棋盘抖动=若隐若现的纹理
            pyxel.pset(gx, gy, 5)
    # 敌碟（左）：14 号舱罩（用圆代替椭圆，pyxel 无椭圆图元）+ 8 号碟身 + 10 号灯
    pyxel.circ(52, 92, 8, 14)
    pyxel.rect(36, 98, 32, 6, 8)
    for i in range(4):                            # 起落灯：轮流闪
        if (T // 8 + i) % 4 == 0:
            pyxel.pset(40 + i * 8, 101, 10)
    # 飞船（右）：7 号本体 + 6 号阴影 + 12 号舷窗 + 9/10 号尾焰
    bx = 170 + int(3 * (T % 30 < 15))             # 待机左右微移
    pyxel.tri(bx, 108, bx - 10, 122, bx + 10, 122, 7)
    pyxel.tri(bx, 116, bx - 10, 122, bx + 10, 122, 6)
    pyxel.pset(bx, 114, 12)
    if T % 6 < 3:                                 # 尾焰两帧闪
        pyxel.line(bx, 123, bx, 128, 9)
        pyxel.pset(bx, 126, 10)
    # 悬浮水晶（中）：11 号本体 + 7 号高光，正弦浮动
    bob = int(3 * math.sin(T * 0.08))
    cx, cy = 120, 88 + bob
    pyxel.tri(cx, cy - 8, cx - 6, cy + 4, cx + 6, cy + 4, 11)
    pyxel.tri(cx, cy - 8, cx - 2, cy, cx + 2, cy, 11)
    pyxel.line(cx, cy - 6, cx - 2, cy + 1, 7)     # 左棱高光
    pyxel.pset(cx + 4, cy + 2, 5)                 # 右棱暗面
    # 灰阶条（第 132 行）：常用灰槽 0/5/6/13/7 —— 检验配色灰阶保留度
    for i, slot in enumerate((0, 5, 6, 13, 7)):
        pyxel.rect(8 + i * 20, 132, 16, 8, slot)
    txt(112, 133, "灰阶槽 0/5/6/13/7", 7)
    # 16 槽色带（第 146 行）：从左到右完整展示当前配色
    for i in range(16):
        pyxel.rect(8 + i * 14, 146, 12, 8, i)
    txt(8, 156, "0", 7)
    txt(196, 156, "15", 7)


# ==================== 主循环 ====================
def update():
    """全局更新：翻页切换调色板并即时套用。"""
    global T, IDX
    if pyxel.btnp(pyxel.KEY_RIGHT):
        IDX = (IDX + 1) % len(PALETTES)
        apply_palette(PALETTES[IDX][2])
    if pyxel.btnp(pyxel.KEY_LEFT):
        IDX = (IDX - 1) % len(PALETTES)
        apply_palette(PALETTES[IDX][2])
    for i in range(len(PALETTES)):                # 数字键直达
        if pyxel.btnp(pyxel.KEY_1 + i):
            IDX = i
            apply_palette(PALETTES[IDX][2])
    T += 1


def draw():
    """全局绘制：页头（名称/来源/页码）+ 场景 + 配色说明。"""
    pyxel.cls(0)
    name, source, _ = PALETTES[IDX]
    txt(4, 2, f"{IDX + 1}/{len(PALETTES)} {name}", 10)      # 名称（黄）
    txt(W - 88, 2, "[←→] 换配色", 5)                        # 操作提示
    txt(4, 13, source, 6)                                   # 来源（浅蓝小字）
    draw_scene()


def main():
    """入口：抓取默认调色板 -> 构建全部配色 -> 进入主循环。"""
    global PALETTES
    pyxel.init(W, H, title="Palette Lab", fps=30)
    load_font()
    default16 = [pyxel.colors[i] for i in range(16)]        # 先存原生配色
    PALETTES = build_palettes(default16)
    apply_palette(PALETTES[0][2])                           # 首页=原生
    pyxel.run(update, draw)


if __name__ == "__main__":
    main()
