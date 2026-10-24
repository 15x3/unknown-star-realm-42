"""Juice 效果实验室 —— 像素游戏常见"打击感/表现力"效果的独立演示。

用途：调研性质的演示脚本，不接入 star_voyage 游戏本体；
     按 [←]/[→] 或数字键 1-7 切换效果页，人工观感评估后再决定采用哪些。

页面一览：
  1 过场转场：淡入淡出 / 光圈开合 / 条带擦除 / 白闪
  2 攻击表现：斩击弧线 / 枪口闪光 / 弹道拖尾
  3 受击表现：白闪 / 击退 / 伤害数字 / 顿帧(hitstop) / 屏幕震动
  4 悬浮表现：正弦浮动 / 影子缩放 / 呼吸动画
  5 移动残影：历史位置回放（调色板降阶 + 棋盘抖动模拟透明）
  6 CRT 后处理：抖动扫描线 / 四角暗角（空格开关；预生成叠加层，保证帧率）

运行：python effects_lab.py（240x160 窗口；ESC 退出）
技术来源（调研）：hitstop/震屏/白闪（egmatic、Anton Slashcev 的 game feel 指南：
震屏 80-300ms、白闪要快而淡、避免长闪光）；CRT（RetroArch crt-geom 系：
扫描线+荫罩+暗角+弯曲，亮度校准是常见痛点）。
"""
import math
import os

import pyxel

W, H = 240, 160
T = 0                 # 当前页内的帧计数（翻页时归零）
PAGE = 0              # 当前页码
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "assets", "fonts")

# 调色板常用色号：0黑 1深蓝 5暗蓝灰 6浅蓝 7白 8红 9橙 10黄 11绿 12蓝 13紫灰
FONT_12 = None        # 凤凰点阵体 12px（init 后加载，见 load_font）


def load_font():
    """惰性加载凤凰点阵体（须在 pyxel.init 之后调用）。"""
    global FONT_12
    if FONT_12 is None:
        FONT_12 = pyxel.Font(
            os.path.join(FONT_DIR, "VonwaonBitmap-12px.ttf"), 12)


def txt(x, y, s, col):
    """统一文本绘制（12px 中文）。"""
    pyxel.text(x, y, s, col, FONT_12)


def txt_center(y, s, col):
    """按实测宽度居中绘制。"""
    pyxel.text(max(0, (W - FONT_12.text_width(s)) // 2), y, s, col, FONT_12)


def ease_out_cubic(p):
    """缓动：先快后慢（p∈[0,1]）。用于伤害数字上飘、闪光衰减等。"""
    return 1 - (1 - p) ** 3


def ease_out_back(p):
    """缓动：过冲回弹（p∈[0,1]）。用于击退位移、弹出菜单等。"""
    c = 1.70158
    return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2


# ==================== 通用小工具 ====================
def draw_ship(x, y, col):
    """简易像素飞船（三角形舰体 + 尾焰），col 为舰体主色。"""
    pyxel.tri(x, y - 5, x - 5, y + 4, x + 5, y + 4, col)   # 舰体三角
    pyxel.pset(x, y - 2, 7 if col != 7 else 6)             # 驾驶舱高光
    if T % 6 < 3:                                          # 尾焰闪烁（3帧亮3帧暗）
        pyxel.line(x, y + 5, x, y + 8, 9)                  # 橙色尾焰


def draw_enemy(x, y, flash=False):
    """简易敌人方块；flash=True 时画纯白剪影（受击白闪的载体）。"""
    col = 7 if flash else 8                                # 白闪=整体替换为白色
    pyxel.rect(x - 8, y - 8, 16, 16, col)
    if not flash:                                          # 非闪白时补细节
        pyxel.rect(x - 5, y - 5, 10, 10, 2)
        pyxel.pset(x - 3, y - 2, 7)
        pyxel.pset(x + 2, y - 2, 7)


def shake(strength):
    """屏幕震动：用 pyxel.camera 偏移全部绘制（震屏强度=像素半径）。

    调研要点：震屏持续 80~300ms、方向随机但可控，过强过久会晕。
    """
    pyxel.camera(
        pyxel.rndi(-strength, strength),
        pyxel.rndi(-strength, strength))


# ==================== 页1：过场转场 ====================
def update_transitions():
    """过场页逻辑：无交互，四个面板各自按 60 帧周期循环。"""
    pass


def panel_fade(x, y, w, h):
    """面板1 淡入淡出：整块矩形按相位在两种底色间过渡（帧率无关的阶梯渐变）。"""
    p = (T % 60) / 60                                      # 循环相位
    darkness = int(4 * abs(p - 0.5) * 2)                   # 0..4 的离散明暗档
    cols = (11, 3, 5, 1, 0)                                # 绿->黑的5档色阶
    pyxel.rect(x, y, w, h, cols[darkness])
    txt(x + 4, y + 4, "淡入淡出", 7 if darkness < 2 else 6)


def panel_iris(x, y, w, h):
    """面板2 光圈开合：圆形遮罩半径动画（星球大战式转场的像素版）。"""
    p = (T % 60) / 60
    r = int(max(w, h) * 0.75 * (1 - abs(p - 0.5) * 2))     # 半径先收后放
    pyxel.rect(x, y, w, h, 0)                              # 黑底
    pyxel.clip(x, y, w, h)                                 # 限制圆不溢出面板
    pyxel.circ(x + w // 2, y + h // 2, r, 1)               # 深蓝"洞"
    pyxel.circb(x + w // 2, y + h // 2, r, 6)              # 光圈边缘亮环
    pyxel.clip()
    txt(x + 4, y + 4, "光圈开合", 7)


def panel_wipe(x, y, w, h):
    """面板3 条带擦除：竖条按错峰相位依次翻面（廉价而华丽的过场）。"""
    pyxel.rect(x, y, w, h, 1)
    for i in range(6):                                     # 6 根竖条
        bar_p = ((T + i * 5) % 60) / 60                    # 每条错开 5 帧
        if bar_p < 0.5:
            col = 11 if i % 2 else 3                       # 翻面前色
        else:
            col = 0 if i % 2 else 5                        # 翻面后色
        pyxel.rect(x + i * (w // 6), y, w // 6, h, col)
    txt(x + 4, y + 4, "条带擦除", 7)


def panel_flash(x, y, w, h):
    """面板4 白闪：短促高亮（调研要点：要快要淡，避免长闪光/频闪）。"""
    pyxel.rect(x, y, w, h, 5)
    if T % 60 < 4:                                         # 仅 4 帧白闪
        pyxel.rect(x, y, w, h, 7)
    txt(x + 4, y + 4, "白闪", 7)


def draw_transitions():
    """过场页绘制：2x2 四面板。"""
    panel_fade(4, 24, 114, 62)
    panel_iris(122, 24, 114, 62)
    panel_wipe(4, 92, 114, 62)
    panel_flash(122, 92, 114, 62)


# ==================== 页2：攻击表现 ====================
def update_attack():
    """攻击页逻辑：斩击每 36 帧自动触发一次；弹道持续飞行。"""
    pass


def draw_slash(cx, cy):
    """斩击弧线：3 帧扫过的扇形残迹 + 起手白点（攻击动画的最小实现）。"""
    ph = T % 36
    if ph < 12:                                            # 只在动画期绘制
        p = ph / 12
        a0 = math.radians(-60)                             # 起始角
        a1 = a0 + math.radians(120) * p                    # 扫过 120°
        for k in range(3):                                 # 三段渐隐残迹
            t = max(0.0, p - k * 0.18)
            ang = a0 + math.radians(120) * t
            r = 26 - k * 2
            pyxel.line(cx, cy,
                       cx + math.cos(ang) * r,
                       cy + math.sin(ang) * r,
                       (7, 6, 5)[k])                       # 白->暗 三阶
        if ph < 3:                                         # 起手帧白点
            pyxel.circ(cx, cy, 3, 7)


def draw_projectile():
    """弹道拖尾：弹头 + 历史位置渐隐小点（速度感的廉价来源）。"""
    x = 30 + (T * 3) % 180                                 # 弹头往复飞行
    for k in range(8):                                     # 8 段拖尾
        tx = x - k * 5
        col = (10, 9, 9, 9, 5, 5, 1, 1)[k]                 # 黄->暗 色阶
        pyxel.line(tx, 120, tx + 3, 120, col)
    pyxel.circ(x, 120, 3, 7)                               # 弹头本体
    pyxel.circb(x, 120, 4, 10)
    if T % 4 < 2:                                          # 枪口闪光（在弹头重生处）
        base_x = 30 + (T * 3) % 180
        if base_x < 40:
            pyxel.circ(30, 120, 5, 10)


def draw_attack():
    """攻击页绘制：左侧斩击演示、右侧目标、下方弹道。"""
    draw_enemy(170, 60)
    draw_slash(150, 62)                                    # 斩击扫过敌人
    txt(60, 30, "斩击弧线", 7)
    txt(60, 96, "弹道拖尾 + 枪口闪光", 7)
    draw_projectile()


# ==================== 页3：受击表现 ====================
HIT_T = -999               # 最近一次受击的全局帧（-999=尚未发生）
DMG = 0                    # 最近一次伤害数字


def update_hit():
    """受击页逻辑：每 50 帧自动"打一下"敌人（触发全套受击反馈）。"""
    global HIT_T, DMG
    if T % 50 == 0:
        HIT_T = T                                          # 记录受击帧
        DMG = pyxel.rndi(6, 12)                            # 随机伤害数字


def draw_hit():
    """受击页绘制：白闪+击退+伤害数字+顿帧+震屏 全家桶。"""
    since = T - HIT_T                                      # 受击后经过的帧数
    pyxel.cls(0)
    pyxel.camera(0, 0)                                     # 先复位镜头
    if since < 3:
        shake(3)                                           # 顿帧期间震屏（半径3px）
    elif since < 8:
        shake(1)                                           # 余震衰减到 1px
    else:
        pyxel.camera(0, 0)                                 # 震动结束复位
    flash = since < 3                                      # 前3帧：白闪
    knock = 0
    if since < 10:                                         # 前10帧：击退过冲回弹
        knock = int(14 * ease_out_back(min(1.0, since / 10)))
    draw_enemy(90 + knock, 70, flash)                      # 受击本体
    if 0 <= since < 18:                                    # 伤害数字：上飘+渐变
        p = since / 18
        dy = int(20 * ease_out_cubic(p))                   # 上飘20px(先快后慢)
        col = (8, 8, 9, 9, 10, 10, 6, 5, 5, 1)[since // 2] # 红->黄->暗 色序
        txt(84, 44 - dy, f"-{DMG}", col)
    if since < 3:                                          # hitstop 提示：
        txt(140, 34, "顿帧中", 6)                           # 逻辑帧被冻结的体感
    txt(30, 118, "白闪·击退·伤害数字·顿帧·震屏", 7)
    if since >= 3:                                         # 顿帧结束后才画弹孔
        pyxel.pset(98 + knock, 66, 0)


# ==================== 页4：悬浮表现 ====================
def update_hover():
    """悬浮页逻辑：纯时间函数，无状态。"""
    pass


def draw_hover():
    """悬浮页绘制：正弦浮动 + 影子随高度缩放 + 待机呼吸（选单图标常用）。"""
    bob = math.sin(T * 0.08) * 3                           # ±3px 正弦浮动
    h = int(20 + bob)                                      # 离地高度（影子依据）
    y = 70 - h                                             # 图标本体 y
    # 影子：宽度随高度反比缩放（越高越小越淡）
    sw = max(4, 18 - h // 3)                               # 影宽
    # 地面椭圆影：pyxel 无椭圆图元，用 3 行矩形拼（中宽上下窄）
    pyxel.rect(120 - sw, 107, sw * 2, 1, 1)             # 影子上缘
    pyxel.rect(120 - sw - 2, 108, sw * 2 + 4, 1, 1)     # 影子中段(最宽)
    pyxel.rect(120 - sw, 109, sw * 2, 1, 1)             # 影子下缘
    # 呼吸：图标尺寸 ±1 缓慢脉动（待机"活着"的感觉）
    breath = 1 if (T // 20) % 2 == 0 else 0
    pyxel.rect(120 - 6 - breath, y - 6 - breath,
               12 + breath * 2, 12 + breath * 2, 11)       # 绿色箱子图标
    pyxel.rectb(120 - 6 - breath, y - 6 - breath,
                12 + breath * 2, 12 + breath * 2, 7)
    # 参照线：展示浮动轨迹
    pyxel.line(148, 70 - 23, 148, 70 + 3, 1)
    pyxel.pset(148, y, 10)
    txt(28, 118, "正弦浮动 · 影子缩放 · 待机呼吸", 7)


# ==================== 页5：移动残影 ====================
TRAIL = []                 # 飞船历史位置 [(x, y), ...]（最新在前）


def update_afterimage():
    """残影页逻辑：飞船沿 8 字路线移动，记录最近 14 个历史位置。"""
    t = T * 0.09
    x = 120 + int(70 * math.sin(t))                        # 8 字的 x
    y = 75 + int(24 * math.sin(2 * t))                     # 8 字的 y
    TRAIL.insert(0, (x, y))                                # 头插最新位置
    if len(TRAIL) > 14:                                    # 只保留 14 帧
        TRAIL.pop()


def draw_afterimage():
    """残影页绘制：历史位置按新旧降色阶，旧的加棋盘抖动模拟半透明。

    pyxel 无透明度：用"隔行/隔列跳点"（棋盘抖动）让旧残影像素密度减半，
    视觉上等效 50%/25% 透明——像素游戏的标准做法。
    """
    pyxel.cls(0)
    for i in range(len(TRAIL) - 1, 0, -1):                 # 从旧到新绘制
        x, y = TRAIL[i]
        col = (7, 7, 6, 6, 5, 5, 1, 1)[min(7, i // 2)]     # 白->暗蓝 8 档色阶
        density = 2 if i < 6 else 4                        # 旧残影更稀疏
        # 抖动三角：只有 (x+y)%density==0 的点才画，密度越低视觉上越透明
        for dy in range(-5, 5):
            for dx in range(-5, 6):
                if abs(dx) + abs(dy) < 6 and (x + dx + y + dy) % density == 0:
                    pyxel.pset(x + dx, y + dy, col)
    x, y = TRAIL[0]                                        # 本体（满密度）
    draw_ship(x, y, 7)
    txt(28, 118, "移动残影：色阶渐隐 + 棋盘抖动透明", 7)


# ==================== 页6：CRT 后处理 ====================
CRT_SCAN = None            # 扫描线叠加层（棋盘抖动暗缝，静态无频闪）
CRT_VIGN = None            # 暗角叠加层（仅四角，径向渐暗）
CRT_ON = True              # 扫描线开关（空格键切换，便于 A/B 对比观感）


def build_crt_masks():
    """预生成两张叠加层（启动算一次；运行时每帧各 blt 一次，保证 30fps）。

    v2 修复（首版实心暗线+荫罩+逐帧闪烁，观感发暗发糊且 15Hz 频闪）：
    - 扫描线：隔行暗缝改**棋盘抖动**（隔行×隔点各取 50%）——感知暗度减半，
      呈"荧光点阵"质感而非整行涂黑；
    - **去掉逐帧相位闪烁**：30fps 全屏翻相=15Hz 频闪，调研明确劝退；
    - **去掉荫罩点**：与抖动扫描线叠加会糊掉，二选一取扫描线；
    - 暗角只留四角（半径>0.95 才渐暗）；
    - 亮度校准是 CRT 滤镜头号痛点，故提供空格开关做 A/B 对比。
    真·桶形弯曲/色差需逐像素重映射，Python 逐点太慢，以暗角近似（已注明）。
    """
    global CRT_SCAN, CRT_VIGN
    CRT_SCAN = pyxel.Image(W, H)
    CRT_VIGN = pyxel.Image(W, H)
    for y in range(H):
        for x in range(W):
            if y % 2 == 1 and (x + y) % 2 == 0:            # 隔行+棋盘各取一半
                CRT_SCAN.pset(x, y, 1)
            nx = (x - W / 2) / (W / 2)                     # 暗角：归一化半径
            ny = (y - H / 2) / (H / 2)
            r = math.hypot(nx, ny)
            if r > 0.95 and (x + y) % 2 == 0:              # 仅四角，抖动渐暗
                CRT_VIGN.pset(x, y, 1)


def update_crt():
    """CRT 页逻辑：空格切换扫描线开关（A/B 对比用）。"""
    global CRT_ON
    if pyxel.btnp(pyxel.KEY_SPACE):
        CRT_ON = not CRT_ON


def draw_crt():
    """CRT 页绘制：小场景 ->（可选）抖动扫描线 + 四角暗角。"""
    pyxel.cls(0)
    for i in range(40):                                    # 星空（滚动视差）
        sx = (i * 61 + T // 2) % W                         # 慢速横滚
        sy = (i * 37) % H
        pyxel.pset(sx, sy, 6 if i % 3 else 13)
    pyxel.circ(60, 60, 14, 11)                             # 星球
    pyxel.circb(60, 60, 14, 3)
    draw_ship(150 + int(math.sin(T * 0.05) * 20), 70, 7)   # 摆动飞船
    if CRT_ON:                                             # 空格可关：对比有无
        pyxel.blt(0, 0, CRT_SCAN, 0, 0, W, H, 0)           # 抖动扫描线（colkey=0）
        pyxel.blt(0, 0, CRT_VIGN, 0, 0, W, H, 0)           # 四角暗角
        txt(24, 118, "CRT：抖动扫描线·四角暗角 [空格]关", 7)
    else:
        txt(24, 118, "原始画面（无后处理） [空格]开", 7)


# ==================== 页面注册表 ====================
PAGES = [
    ("过场转场", update_transitions, draw_transitions),
    ("攻击表现", update_attack, draw_attack),
    ("受击表现", update_hit, draw_hit),
    ("悬浮表现", update_hover, draw_hover),
    ("移动残影", update_afterimage, draw_afterimage),
    ("CRT 后处理", update_crt, draw_crt),
]


def update():
    """全局更新：翻页键 + 当前页逻辑。"""
    global T, PAGE
    if pyxel.btnp(pyxel.KEY_RIGHT):
        PAGE = (PAGE + 1) % len(PAGES)
        T = 0
    if pyxel.btnp(pyxel.KEY_LEFT):
        PAGE = (PAGE - 1) % len(PAGES)
        T = 0
    for i in range(len(PAGES)):                            # 数字键直达
        if pyxel.btnp(pyxel.KEY_1 + i):
            PAGE, T = i, 0
    T += 1
    pyxel.camera(0, 0)                                     # 每帧复位镜头（震屏页会改）
    PAGES[PAGE][1]()                                       # 当前页 update


def draw():
    """全局绘制：页头 + 当前页内容 + 翻页提示。"""
    pyxel.cls(0)
    pyxel.camera(0, 0)
    name = PAGES[PAGE][0]
    txt(4, 2, f"{PAGE + 1}/{len(PAGES)} {name}", 10)       # 页头（黄）
    txt(W - 96, 2, "[←→] 翻页", 5)                          # 翻页提示
    pyxel.line(0, 18, W, 18, 1)                            # 页头分隔线
    pyxel.clip(0, 20, W, H - 20)                           # 内容区裁剪
    PAGES[PAGE][2]()                                       # 当前页 draw
    pyxel.clip()


def main():
    """入口：初始化、加载字体与 CRT 叠加层、启动主循环。"""
    pyxel.init(W, H, title="Juice Effects Lab", fps=30)
    load_font()
    build_crt_masks()
    pyxel.run(update, draw)


if __name__ == "__main__":
    main()
