"""CRT 实验室 v3 —— 基于 MAME HLSL 教程的 CRT 效果研究（独立脚本，不接游戏）。

参考（B 站 beorht 的 MAME HLSL 三部曲）：
  [1] 《修改mame.ini达成比较真实的crt效果》——CRT=荫栅/荫罩(彩色子像素遮罩，
      乘法混色而非黑点) + 扫描线(亮度自适应：越亮的像素扫描线越细) + 泛光提亮补偿；
  [2] 《修改mame.ini达成比较真实的反射屏效果》——遮罩的画法：子像素位置上，
      主通道亮、其余通道压暗；横向黑缝只占 25%；
  [3] 《修改mame.ini调节游戏画面色彩》——信号函数
      f(s) = floor^p + ((1-floor^p)·scale·s + offset)^p（逐通道）+ 比例矩阵 + 饱和度。

pyxel 的两条移植思路（无 shader/无 alpha 约束下的等效实现）：
  A. 信号函数 -> 【调色板级变换】：pyxel 是色号索引制，f(s) 只需作用于 16 个
     调色板槽位（等价于 MAME 在 shader 里做整屏逐像素，但成本≈0）；
  B. 扫描线/荫栅 -> 【逐像素 LUT 后处理】：pget 返回色号→亮度 O(1) 查表，
     按 (行奇偶, 列相位) 共 6 组 16→16 映射表一次构建；实测全屏 pass 13ms，
     30fps 预算内。扫描线暗度随该像素亮度变化（[1] 的 scanline_variation 思想）。

诚实声明（pyxel 的物理极限）：真荫罩/泛光需要输出分辨率余量（MAME 在 1080p
下让每个游戏像素覆盖多个屏幕像素），pyxel 像素=屏幕像素 1:1，故：
  - 荫栅只做"轻度通道缩放"（0.78），不做满强度子像素条纹；
  - 泛光无法实现（需模糊采样），以"亮像素几乎不压暗"近似补偿。

操作：[←→] 翻页  [空格] 原始/效果对比  [Q/A] 扫描线强度  [W/S] 明度自适应
运行：python crt_lab.py（右上角实时显示每帧耗时 ms）
"""
import math
import os

import pyxel

W, H = 240, 160
T = 0                       # 帧计数
PAGE = 0                    # 当前页码
BYPASS = False              # 空格：跳过后处理（A/B 对比）
SCAN_A = 0.70               # 扫描线暗度系数（Q/A 调）——需足够大跨过最近色中点，
                            # 否则压暗后量化回原色=不可见（16 色量化的固有约束）
SCAN_V = 0.9                # 明度自适应强度（W/S 调）：亮像素少压暗
FONT_12 = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 原始调色板（启动时抓取；后处理的一切量化都以它为准）
ORIG = []
# 后处理用数据
XFORM = []                  # 信号函数变换后的 16 色（RGB 浮点 0..1）
LUT = [[None] * 3 for _ in range(2)]   # LUT[行奇偶][列相位] = 16->16 映射
PERF_MS = 0.0               # 最近一帧 draw 耗时（EMA）


def load_font():
    """惰性加载凤凰点阵体（pyxel.init 之后）。"""
    global FONT_12
    if FONT_12 is None:
        FONT_12 = pyxel.Font(os.path.join(
            BASE_DIR, "assets", "fonts", "VonwaonBitmap-12px.ttf"), 12)


def txt(x, y, s, col):
    """统一文本绘制。"""
    pyxel.text(x, y, s, col, FONT_12)


def txt_right(y, s, col):
    """右对齐绘制（页码/耗时）。"""
    pyxel.text(W - FONT_12.text_width(s) - 2, y, s, col, FONT_12)


# ==================== 信号函数（[3] 的公式，逐通道） ====================
def signal(s, floor, scale, offset, power):
    """f(s) = floor^p + ((1-floor^p)·scale·s + offset)^p，s∈[0,1]。"""
    fp = floor ** power
    v = fp + (1 - fp) * scale * s + offset
    return max(0.0, v) ** power


def apply_signal(rgb01, floor, scale, offset, power, sat):
    """对一个 RGB(0..1) 施加逐通道信号曲线 + 饱和度（[3]）。"""
    r, g, b = (signal(c, floor[i], scale[i], offset[i], power)
               for i, c in enumerate(rgb01))
    if sat != 1.0:                                  # 饱和度：绕亮度轴缩放
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        r, g, b = (lum + (c - lum) * sat for c in (r, g, b))
    return tuple(min(1.0, max(0.0, c)) for c in (r, g, b))


# ==================== 页面配置 ====================
# 每页: (名称, 信号参数 dict 或 None, 扫描线?, 荫栅?)
# CRT 信号预设取自 [1]（scale~0.5-0.6 提对比，靠"亮不压暗"补回亮度）；
# GBA 反射屏预设取自 [3] 的实例（floor 0.34/0.4/0.4, power 2, scale 1）。
PAGES = [
    ("原始画面（基准）",   None, False, False),
    ("信号曲线·CRT 荧光",  dict(floor=(0.05,)*3, scale=(0.62,)*3,
                                offset=(0.02,)*3, power=1.25, sat=1.05),
     False, False),
    ("信号曲线·GBA 反射屏", dict(floor=(0.34, 0.40, 0.40), scale=(1.0,)*3,
                                 offset=(0.0,)*3, power=2.0, sat=1.0),
     False, False),
    ("扫描线（亮度自适应）", None, True, False),
    ("荧光荫栅（亮区可辨）", None, False, True),
    ("完整 CRT（组合）",    dict(floor=(0.05,)*3, scale=(0.62,)*3,
                                offset=(0.02,)*3, power=1.25, sat=1.05),
     True, True),
]


def rebuild():
    """按当前页配置重建：变换后调色板 + 6 组相位 LUT，并写入 pyxel.colors。

    BYPASS=True 时完全还原原始调色板（旁路=真·原始画面，仅动画在动）。
    """
    global XFORM
    cfg = PAGES[PAGE][1]
    if BYPASS:                                      # 旁路：彻底还原
        cfg = None
    # 1) 信号函数 -> 调色板级变换（[3]：MAME 在 shader 做的事，这里 16 次搞定）
    if cfg:
        XFORM = [apply_signal(((c >> 16) / 255, ((c >> 8) & 255) / 255,
                               (c & 255) / 255),
                              cfg["floor"], cfg["scale"], cfg["offset"],
                              cfg["power"], cfg["sat"])
                 for c in ORIG]
    else:
        XFORM = [((c >> 16) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255)
                 for c in ORIG]
    for i, (r, g, b) in enumerate(XFORM):           # 写回引擎调色板
        pyxel.colors[i] = int(r * 255) << 16 | int(g * 255) << 8 | int(b * 255)
    # 2) 空间部分 -> 6 组 LUT（行奇偶 × 荫栅列相位；旁路时为恒等映射）
    use_scan = PAGES[PAGE][2] and not BYPASS
    use_grille = PAGES[PAGE][3] and not BYPASS
    for rowph in (0, 1):
        for colph in (0, 1, 2):
            lut = []
            for idx, (r, g, b) in enumerate(XFORM):
                nr, ng, nb = r, g, b
                if use_grille:                      # 荫栅：本列主通道保持，
                    k = 0.50                        # 其余通道压到 0.5（[2] 原文的
                    nr, ng, nb = [                  # 1:1 像素下的温和版）
                        (r, k * g, k * b), (k * r, g, k * b),
                        (k * r, k * g, b)][colph]
                if use_scan and rowph == 1:         # 扫描线暗度随亮度变化（[1]）：
                    lum = min(1.0, 0.299 * nr + 0.587 * ng + 0.114 * nb)
                    dark = SCAN_A * (1.0 - lum * SCAN_V)   # 亮->几乎不压暗
                    nr, ng, nb = nr * (1 - dark), ng * (1 - dark), nb * (1 - dark)
                lut.append(nearest_index(nr, ng, nb))
            LUT[rowph][colph] = lut


def nearest_index(r, g, b):
    """在变换后调色板中找最近色号（平方距离，16 项线性扫足够快）。"""
    best, bd = 0, 1e9
    for i, (pr, pg, pb) in enumerate(XFORM):
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < bd:
            best, bd = i, d
    return best


def post_process():
    """全屏逐像素后处理：色号 -> 相位 LUT -> 色号（实测 ~13ms/帧）。"""
    for y in range(H):
        lut_r = LUT[y & 1]
        for x in range(W):
            pyxel.pset(x, y, lut_r[x % 3][pyxel.pget(x, y)])


# ==================== 场景（色号绘制；明暗跨度大以展示扫描线变化） ====================
def draw_scene():
    """绘制测试场景：暗空/亮星/太阳/星球/飞船 + 底部 16 级明度条。"""
    pyxel.rect(0, 20, W, 46, 1)                     # 深色天空
    pyxel.rect(0, 66, W, 26, 2)
    pyxel.rect(0, 92, W, 10, 3)
    for i in range(18):                             # 星星：跨多个亮度档
        sx = (i * 53 + 9) % W
        sy = 24 + (i * 31) % 70
        pyxel.pset(sx, sy, 7 if i % 3 == 0 else (6 if i % 3 == 1 else 13))
    pyxel.circ(196, 54, 12, 10)                     # 太阳（最亮区）
    pyxel.circ(196, 54, 8, 7)
    pyxel.circ(60, 64, 14, 11)                      # 星球
    pyxel.circ(60, 64, 8, 3)
    for k in range(4):                              # 暗色远山
        bx = 12 + k * 64
        pyxel.tri(bx, 102, bx + 34, 102, bx + 17, 72 + (k % 2) * 10, 4)
    pyxel.rect(0, 102, W, 24, 5)                    # 地面
    bx = 160 + int(3 * (T % 30 < 15))               # 飞船 + 尾焰
    pyxel.tri(bx, 106, bx - 9, 120, bx + 9, 120, 7)
    if T % 6 < 3:
        pyxel.line(bx, 121, bx, 126, 9)
    for i in range(16):                             # 16 级明度条：直接观察
        pyxel.rect(8 + i * 14, 132, 12, 10, i)      # 每级在扫描线下的变化
    txt(8, 148, "明度条 0→15", 7)


# ==================== 主循环 ====================
def update():
    """输入：翻页（←→/数字键）/对比开关/参数调节。"""
    global T, PAGE, BYPASS, SCAN_A, SCAN_V
    if pyxel.btnp(pyxel.KEY_RIGHT):
        PAGE = (PAGE + 1) % len(PAGES)
        BYPASS = False
        rebuild()
    if pyxel.btnp(pyxel.KEY_LEFT):
        PAGE = (PAGE - 1) % len(PAGES)
        BYPASS = False
        rebuild()
    for i in range(len(PAGES)):                     # 数字键直达
        if pyxel.btnp(pyxel.KEY_1 + i):
            PAGE = i
            BYPASS = False
            rebuild()
    if pyxel.btnp(pyxel.KEY_SPACE):                 # 空格：效果/原始 切换
        BYPASS = not BYPASS
        rebuild()
    if PAGES[PAGE][2]:                              # 仅扫描线相关页可调参
        if pyxel.btnp(pyxel.KEY_Q):
            SCAN_A = min(0.9, SCAN_A + 0.1)
            rebuild()
        if pyxel.btnp(pyxel.KEY_A):
            SCAN_A = max(0.0, SCAN_A - 0.1)
            rebuild()
        if pyxel.btnp(pyxel.KEY_W):
            SCAN_V = min(1.0, SCAN_V + 0.1)
            rebuild()
        if pyxel.btnp(pyxel.KEY_S):
            SCAN_V = max(0.0, SCAN_V - 0.1)
            rebuild()
    T += 1


def draw():
    """绘制：场景 ->（可选）逐像素后处理 -> 页头信息（含帧耗时）。"""
    import time
    global PERF_MS
    t0 = time.perf_counter()
    pyxel.cls(0)
    draw_scene()
    if PAGES[PAGE][2] or PAGES[PAGE][3]:            # 仅空间效果页做逐像素 pass
        if not BYPASS:
            post_process()
    name = PAGES[PAGE][0] + ("（已关闭·空格开启）" if BYPASS else "")
    txt(4, 2, name, 10)
    txt_right(2, f"{PAGE + 1}/{len(PAGES)}  {PERF_MS:.1f}ms", 6)
    if PAGES[PAGE][2]:
        txt(4, 118, f"暗度{SCAN_A:.1f}[QA] 自适应{SCAN_V:.1f}[WS]", 7)
    PERF_MS = PERF_MS * 0.9 + (time.perf_counter() - t0) * 1000 * 0.1  # EMA


def main():
    """入口：抓原始调色板 -> 构建当前页 -> 主循环。"""
    global ORIG
    pyxel.init(W, H, title="CRT Lab v3", fps=30)
    load_font()
    ORIG = [pyxel.colors[i] for i in range(16)]
    rebuild()
    pyxel.run(update, draw)


if __name__ == "__main__":
    main()
