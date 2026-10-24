"""CRT Shader Lab —— pyxel 渲染 + OpenCV 后处理的外部管线实验。

架构（用户提出的原理）：
    pyxel(headless 渲染游戏帧, 色号索引)
      -> pget 抓帧 -> numpy 索引图 -> 调色板查色 -> RGB 帧(240x160)
      -> OpenCV 在【显示分辨率】(x4=960x640) 做全浮点后处理:
           桶形失真 / 色差 / 子像素荫栅 / 亮度自适应扫描线 / 泛光 / 暗角圆角
      -> cv2.imshow 显示；waitKey 键盘 -> pyxel.set_btn 回注（游戏逻辑照常 btnp）

为什么这版能做全效果（前几代 pyxel 原生方案做不到）：
  - MAME HLSL 教程的荫罩/泛光需要"每个游戏像素覆盖多个屏幕像素"的分辨率余量，
    pyxel 内部像素=屏幕像素 1:1 且只有 16 色，量化吃掉一切细节；
  - OpenCV 在显示分辨率 x4 上做浮点运算：4x4 显示像素对应 1 个游戏像素，
    子像素条纹/扫描线变细/高斯泛光都有了物理空间。
  - 键盘经 waitKey -> set_btn 注入，pyxel 的 btnp 语义不变（pyxel-mcp 同款机制）。

操作（在 OpenCV 窗口内）：1-6 开关各级  0 全关  A/D 或 ←→ 移动飞船（验证输入回注）
                          ESC 退出
运行：python crt_shader_lab.py            # 交互窗口
      python crt_shader_lab.py --selftest # 无窗口自检，输出 runs/crtcv_*.png 与耗时
效果参数沿三篇 B 站 MAME HLSL 教程：荫栅子像素值(非主通道0.5)、扫描线亮度自适应、
泛光补偿提亮；色差/桶形失真是 CRT 教材通用默认值。
"""
import ctypes
import math
import os
import sys
import time

import numpy as np

import pyxel

W, H = 240, 160                 # pyxel 逻辑分辨率
SCALE = 3                       # 显示放大倍数（荫栅/扫描线/泛光的分辨率余量）
DW, DH = W * SCALE, H * SCALE   # 显示分辨率 720x480
TARGET_FPS = 30

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_12 = None

# ---- 各级开关（数字键切换）----
STAGES = ["桶形失真", "色差", "子像素荫栅", "扫描线", "泛光", "暗角圆角"]
ON = [True] * len(STAGES)

# ---- 输入回注：waitKey 码 -> pyxel 键常量 ----
KEYMAP = {
    13: pyxel.KEY_RETURN, 32: pyxel.KEY_SPACE,
    ord("a"): pyxel.KEY_A, ord("d"): pyxel.KEY_D,
    ord("q"): pyxel.KEY_Q, ord("w"): pyxel.KEY_W,
    2424832: pyxel.KEY_LEFT, 2490368: pyxel.KEY_UP,     # Windows 方向键扩展码
    2555904: pyxel.KEY_RIGHT, 2621440: pyxel.KEY_DOWN,
}
held = {}                       # waitKey 码 -> 是否按住（边沿检测用）

# ---- 性能统计 ----
PERF = {"grab": 0.0, "shader": 0.0, "total": 0.0}


def load_font():
    """惰性加载凤凰点阵体（pyxel.init 之后）。"""
    global FONT_12
    if FONT_12 is None:
        FONT_12 = pyxel.Font(os.path.join(
            BASE_DIR, "assets", "fonts", "VonwaonBitmap-12px.ttf"), 12)


def txt(x, y, s, col):
    """pyxel 侧文本（会随帧进入后处理管线，验证 HUD 也能被 CRT 化）。"""
    pyxel.text(x, y, s, col, FONT_12)


# ==================== pyxel 侧：游戏/演示场景（headless 渲染） ====================
SHIP_X = [120]                  # 飞船 x（A/D 可移动——验证输入回注闭环）


def game_update():
    """演示场景逻辑：A/D/方向键移动飞船（输入来自 OpenCV 窗口回注）。"""
    if pyxel.btn(pyxel.KEY_A) or pyxel.btn(pyxel.KEY_LEFT):
        SHIP_X[0] = max(10, SHIP_X[0] - 2)
    if pyxel.btn(pyxel.KEY_D) or pyxel.btn(pyxel.KEY_RIGHT):
        SHIP_X[0] = min(W - 10, SHIP_X[0] + 2)


def game_draw():
    """演示场景绘制：明暗跨度大 + 高对比边缘 + HUD（全部只写色号）。"""
    pyxel.cls(0)
    pyxel.rect(0, 20, W, 46, 1)                     # 深色天空三层
    pyxel.rect(0, 66, W, 26, 2)
    pyxel.rect(0, 92, W, 10, 3)
    for i in range(18):                             # 星星：多亮度档
        sx = (i * 53 + 9) % W
        sy = 24 + (i * 31) % 70
        pyxel.pset(sx, sy, 7 if i % 3 == 0 else (6 if i % 3 == 1 else 13))
    pyxel.circ(196, 54, 12, 10)                     # 太阳（泛光源）
    pyxel.circ(196, 54, 8, 7)
    pyxel.circ(60, 64, 14, 11)                      # 星球
    pyxel.circ(60, 64, 8, 3)
    for k in range(4):                              # 远山（暗部）
        bx = 12 + k * 64
        pyxel.tri(bx, 102, bx + 34, 102, bx + 17, 72 + (k % 2) * 10, 4)
    pyxel.rect(0, 102, W, 24, 5)
    bx = SHIP_X[0] + int(2 * (pyxel.frame_count % 20 < 10))   # 待机微移
    pyxel.tri(bx, 106, bx - 9, 120, bx + 9, 120, 7)           # 飞船
    if pyxel.frame_count % 6 < 3:
        pyxel.line(bx, 121, bx, 126, 9)
    for i in range(16):                             # 16 级明度条
        pyxel.rect(8 + i * 14, 132, 12, 10, i)
    # HUD：标题 + 各级开关状态（左侧竖排）+ 帧耗时（随帧走完整管线）
    txt(4, 2, "CRT管线: 0全关 1-6开关 A/D移船", 7)
    for i, name in enumerate(STAGES):
        txt(4, 24 + i * 13, f"{i + 1}{name} {'开' if ON[i] else '关'}",
            10 if ON[i] else 5)
    txt(W - 60, 2, f"{PERF['total']:.0f}ms", 6)


# ==================== 抓帧：pyxel 色号帧 -> RGB numpy ====================
_palette = None       # (16,3) uint8 RGB
_pal_list = None      # list 化的 pyxel.colors（pget 返回色号，用查表替代属性访问）

def grab_frame():
    """整帧抓取：pyxel.screen.data_ptr -> ctypes 数组 -> numpy 零拷贝视图 -> 查色。

    data_ptr 返回帧缓存的 ctypes 字节数组（色号 1 字节/像素），
    np.ctypeslib.as_array 建零拷贝视图，比逐点 pget 快两个数量级。
    """
    idx = np.ctypeslib.as_array(pyxel.screen.data_ptr()).reshape(H, W)
    return _palette[idx]                 # 高级索引查色：一次得到 RGB 帧


# ==================== OpenCV 后处理链（显示分辨率，全浮点） ====================
import cv2  # noqa: E402  （放此处：确保 pyxel 侧先自洽，也便于阅读分节）

_maps_barrel = None     # cv2.remap 预计算映射
_mask_grille = None     # (DH,DW,3) 子像素荫栅
_mask_vignette = None   # (DH,DW,1) 暗角 + 圆角
_row_odd = None         # (DH,DW) 奇数显示行=1、偶行=0（扫描线用）


def build_constants():
    """预计算与帧无关的映射/遮罩（启动一次）。"""
    global _maps_barrel, _mask_grille, _mask_vignette, _row_odd
    # 桶形失真：归一化坐标 -> 畸变坐标（教材标准公式 r_d = r(1+k1·r²)）
    k1 = 0.08
    ys, xs = np.mgrid[0:DH, 0:DW].astype(np.float32)
    nx = (xs - DW / 2) / (DW / 2)
    ny = (ys - DH / 2) / (DH / 2)
    r2 = nx * nx + ny * ny
    scale = 1.0 + k1 * r2                       # 向外拉伸边缘
    _maps_barrel = (ny * scale * (DH / 2) + DH / 2,
                    nx * scale * (DW / 2) + DW / 2)   # (map_y, map_x)
    # 子像素荫栅：3 显示像素一个周期，列相位 R/G/B 主通道 1、其余 0.5
    # （三篇教程[2]的子像素值：主通道 255，其余 127 -> 归一化 1.0/0.5）
    phase_colors = np.array([[1.0, 0.5, 0.5],
                             [0.5, 1.0, 0.5],
                             [0.5, 0.5, 1.0]], dtype=np.float32)
    _mask_grille = np.broadcast_to(
        phase_colors[np.arange(DW) % 3], (DH, DW, 3)).copy()
    # 暗角（径向 1->0.7）+ 四角圆角黑边（半径 28）
    r = np.sqrt(nx * nx + ny * ny)
    vig = 1.0 - 0.3 * np.clip((r - 0.75) / 0.45, 0, 1) ** 2
    corner = np.ones((DH, DW), dtype=np.float32)
    cr = 28.0
    cx = np.maximum(np.abs(xs - DW / 2) - (DW / 2 - cr), 0)
    cy = np.maximum(np.abs(ys - DH / 2) - (DH / 2 - cr), 0)
    corner[np.sqrt(cx * cx + cy * cy) > cr] = 0.0
    _mask_vignette = (vig * corner)[..., None].astype(np.float32)
    # 奇数显示行掩码（扫描线压暗只作用于奇行）
    _row_odd = np.zeros((DH, DW), dtype=np.float32)
    _row_odd[1::2, :] = 1.0


def apply_shader(rgb_small):
    """后处理链：rgb_small (H,W,3) uint8 -> (DH,DW,3) uint8。

    顺序：放大 -> 桶形失真 -> 色差 -> 荫栅 -> 扫描线(亮度自适应) -> 泛光 -> 暗角。
    """
    t0 = time.perf_counter()
    # 1) 最近邻放大到显示分辨率（保持像素块边缘锐利）
    big = cv2.resize(rgb_small, (DW, DH), interpolation=cv2.INTER_NEAREST)
    img = big.astype(np.float32)
    # 2) 桶形失真（cv2.remap，预计算映射）
    if ON[0]:
        img = cv2.remap(img, _maps_barrel[1], _maps_barrel[0],
                        interpolation=cv2.INTER_LINEAR)
    # 3) 色差：R 左移 1px、B 右移 1px（显示分辨率上=子像素级偏移）
    if ON[1]:
        r = np.roll(img[..., 0], -1, axis=1)
        b = np.roll(img[..., 2], 1, axis=1)
        img = np.stack((r, img[..., 1], b), axis=-1)
    # 亮度图（扫描线/泛光共用）：0..1 浮点
    lum = (0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]) / 255.0
    # 4) 子像素荫栅（乘法混色，[2]）
    if ON[2]:
        img *= _mask_grille
    # 5) 扫描线：隔显示行压暗，强度随该像素亮度自适应（[1] scanline_variation：
    #    亮像素扫描线"变细" -> 几乎不压暗；全浮点无 16 色量化限制）
    if ON[3]:
        s, v = 0.45, 0.9                          # 暗度 / 自适应系数
        darken = s * (1.0 - np.clip(lum, 0, 1) * v)
        factor = 1.0 - darken * _row_odd          # 偶行 1，奇行 1-darken
        img *= factor[..., None]
    # 6) 泛光：亮部提取 -> 高斯模糊 -> 加回（MAME 用泛光补偿荫罩压暗，[1]）
    if ON[4]:
        bright = img * np.clip((lum - 0.55) / 0.45, 0, 1)[..., None]
        bloom = cv2.GaussianBlur(bright, (0, 0), sigmaX=4.0)
        img = img + bloom * 0.8
    # 7) 暗角 + 圆角
    if ON[5]:
        img *= _mask_vignette
    PERF["shader"] = (PERF["shader"] * 0.9
                      + (time.perf_counter() - t0) * 1000 * 0.1)
    return np.clip(img, 0, 255).astype(np.uint8)


# ==================== OpenCV 窗口输入 -> pyxel.set_btn 回注 ====================
def pump_input(key):
    """把 waitKey 码翻译成 pyxel 按键（按下沿 set_btn True，松开沿 False）。"""
    if key == -1:                                  # 无按键：处理松开沿
        for code, was in list(held.items()):
            if was:
                held[code] = False
                pyxel.set_btn(KEYMAP[code], False)
        return True
    if key == 27:                                  # ESC：退出实验室
        return False
    # 数字键 0-6：切换管线级（不注入 pyxel，属于实验室自身 UI）
    if ord("0") <= key <= ord("6"):
        n = key - ord("0")
        if n == 0:
            for i in range(len(ON)):
                ON[i] = False
        else:
            ON[n - 1] = not ON[n - 1]
        return True
    if key in KEYMAP:                              # 游戏按键：边沿检测后注入
        if not held.get(key):
            held[key] = True
            pyxel.set_btn(KEYMAP[key], True)
        else:
            held[key] = True                       # 持续按住（btn 为真）
    return True


# ==================== 主循环 ====================
def run_frames(n_frames=None, interactive=True, save_at=None):
    """驱动主循环：pyxel update/draw -> 抓帧 -> shader -> 显示/存档。

    interactive=True 弹 OpenCV 窗口并回注键盘；False 为 --selftest 模式。
    save_at={帧号: 输出路径} 在对应帧存处理结果（自检/留证）。
    """
    frame = 0
    prev = time.perf_counter()
    while n_frames is None or frame < n_frames:
        pyxel.frame_count = frame                  # 与 pyxel-mcp 相同的驱动序列
        game_update()
        game_draw()
        t0 = time.perf_counter()
        rgb = grab_frame()                         # pyxel -> numpy RGB
        out = apply_shader(rgb)                    # OpenCV 后处理链
        PERF["grab"] = (PERF["grab"] * 0.9
                        + (time.perf_counter() - t0) * 1000 * 0.1)
        if save_at and frame in save_at:
            # cv2.imwrite 不支持含中文的 Windows 路径，用 imencode+open 绕开
            ok, png = cv2.imencode(".png", cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
            with open(save_at[frame], "wb") as fp:
                fp.write(png.tobytes())
        if interactive:
            cv2.imshow("CRT Shader Lab", cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
            key = cv2.waitKeyEx(1)                 # 收键盘（兼做 1ms 事件泵）
            if not pump_input(key):
                break
        PERF["total"] = (PERF["total"] * 0.9
                         + (time.perf_counter() - prev) * 1000 * 0.1)
        prev = time.perf_counter()
        # 30fps 节拍（selftest 模式全速跑完）
        if interactive:
            dt = time.perf_counter() - prev
            if dt < 1 / TARGET_FPS:
                time.sleep(1 / TARGET_FPS - dt)
        frame += 1
    if interactive:
        cv2.destroyAllWindows()


def main():
    """入口：初始化 pyxel(headless) 与 OpenCV 常量，进入循环。"""
    pyxel.init(W, H, title="CRT Shader Lab", headless=True, fps=10000)
    load_font()
    global _palette
    _palette = np.array([[((c >> 16) & 255), ((c >> 8) & 255), c & 255]
                         for c in (pyxel.colors[i] for i in range(16))],
                        dtype=np.uint8)
    build_constants()
    if "--selftest" in sys.argv:                   # 自检：无窗口跑 60 帧存档
        presets = {
            9: ("全关",  [False] * 6),
            19: ("全开", [True] * 6),
            29: ("仅扫描线", [False, False, False, True, False, False]),
            39: ("仅荫栅", [False, False, True, False, False, False]),
            49: ("仅泛光", [False, False, False, False, True, False]),
        }
        save_at = {}
        for f, (name, st) in presets.items():
            ON[:] = st
            run_frames(n_frames=f + 1, interactive=False,
                       save_at={f: os.path.join(BASE_DIR, "runs",
                                                f"crtcv_{name}.png")})
        print(f"selftest ok  grab~{PERF['grab']:.1f}ms "
              f"shader~{PERF['shader']:.1f}ms total~{PERF['total']:.1f}ms")
    else:
        run_frames()


if __name__ == "__main__":
    main()
