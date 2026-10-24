"""Star Voyage —— 《游戏设计文档.pdf》的 Pyxel 完整实现。

本文件为【无资产·纯白盒】版本：不加载任何资源文件，图形用几何图元绘制，全程静音；
带资产版本见 star_voyage_assets.py（由 tools/sync_versions.py 从本文件生成，
两版唯一的区别是资产层区块，游戏逻辑逐字一致，同一套测试跑两遍以保证）。

架构（遵循官方示例 10_platformer.py 的鸭子类型惯例）：
  - 场景类（Menu/Map/Fight/Levelup/Ending）与飞船实体自带 update()/draw()，
    App 只持有当前场景对象并逐帧转发；
  - 纯计算类（Engine/StarMap/Enemy/Fight）不依赖 pyxel、不挂空壳 update/draw，
    便于 pytest 直接覆盖；
  - 屏幕 UI 中英双语（菜单/指南页按 TAB 切换，见"多语言层"）：默认中文；
    逻辑键（引擎/技能/子系统/兴趣点的中文名）只经对照表翻译显示层；
  - 中文经 pyxel.Font 加载"凤凰点阵体"（assets/fonts/VonwaonBitmap-12/16px.ttf，见字体层）。

运行：python star_voyage.py（240x160 窗口，阻塞常驻；ESC 退出）。
"""
import math
import os

import pyxel

# ==================== 常量 ====================
PLAYER_HP = 8              # 飞船初始HP（文档未规定，沿用骨架取值）
PLAYER_MAX_MOVE_DIS = 5.0  # 初始最大移动距离（cm），文档默认 5cm
CM_TO_PX = 10              # 单位换算：1cm = 10px（文档用 cm，屏幕用 px）
Y_OFFSET_PX = 30           # 世界 y=0 基线在"世界像素"里的向下偏移（敌人 y 可为负）
WIN_W, WIN_H = 240, 160    # 窗口尺寸
ESCAPE_X = 42              # 胜利条件：抵达 x > 42 的兴趣点即逃离成功
WORLD_W_CM, WORLD_H_CM = 56, 52  # 世界范围（cm），仅供参考——摄像机夹取已改为
                                 # 按实际点云边界外扩计算（见 MapScene.camera_bounds）

# 引擎分支名（PDF 权威命名，勿改——这些中文字符串是分支依据，改名即断功能）
ENG_SIN, ENG_GEO, ENG_CHAOS = "正弦波", "等比数列", "迭代混沌"
ENGINES = (ENG_SIN, ENG_GEO, ENG_CHAOS)              # 菜单三选一的顺序
ENGINE_ABC = {                                        # 引擎参数 A/B/C 含义图例（菜单随选中切换）
    ENG_SIN: "A振幅 B频率 C抬升",                      # 振幅=波动大小，频率=周期疏密，抬升=整体高度
    ENG_GEO: "A基数 B倍率 C公比",                      # |公比|>1：奇数回合固定负值、后期爆发
    ENG_CHAOS: "A初值 B系数 C偏移",                    # 上一项喂下一项的确定混沌序列
}
PARAM_NAME = {                                        # 参数字母 -> 含义名（升级子选单用）
    ENG_SIN: {"A": "振幅", "B": "频率", "C": "抬升"},
    ENG_GEO: {"A": "基数", "B": "倍率", "C": "公比"},
    ENG_CHAOS: {"A": "初值", "B": "系数", "C": "偏移"},
}

SYS_LIST = ("火炮", "护盾", "能量")        # 三个子系统的固定顺序（对应按键 1/2/3）
SKILL_KEYS_ORDER = ("火力过载", "应急护盾", "输出校准器", "故障抑制器")  # 对应 Q/W/E/R
SKILL_COST = {  # 每个主动技能三级的能量消耗：Lv1/Lv2/Lv3（PDF 明确数值）
    "火力过载": (3, 2, 1),
    "应急护盾": (4, 4, 4),
    "输出校准器": (2, 2, 2),
    "故障抑制器": (3, 2, 1),
}
SKILL_HOTKEY = {"火力过载": "Q", "应急护盾": "W",      # 技能 -> 键位（屏显提示用）
                "输出校准器": "E", "故障抑制器": "R"}

# ---- 资产槽位约定（白盒版与资产版共用同一套槽位号，只是绘制方式不同） ----
SPR_SHIP = (0, 0)      # 图像库0 顶部一排 8x8 精灵：飞船
SPR_PLANET = (8, 0)    # 普通星球
SPR_ENEMY = (16, 0)    # 敌人（三角）
SPR_UPGRADE = (24, 0)  # 升级点（方块）
SPR_OF = {"星球": SPR_PLANET, "敌人": SPR_ENEMY, "升级": SPR_UPGRADE}  # 类型->槽位
SND_CURSOR, SND_CANNON, SND_SHIELD, SND_ENERGY = 0, 1, 2, 3   # 音效槽位：光标/火炮/护盾/能量
SND_HIT, SND_KILL, SND_WIN, SND_LOSE = 4, 5, 6, 7             # 受击/击破/胜利/失败
SND_FAULT = 12         # 故障警报（音效槽 8-11 已被 BGM 乐句占用，故放 12）
SND_TYPE, SND_CONFIRM, SND_JUMP, SND_LAND = 13, 14, 15, 16    # 输入滴答/确认/跳迁起跳/落地
SND_GAIN, SND_ALARM = 17, 18                                   # 升级获得/战斗开场警报
MUSIC_MENU = 0                # 音乐槽 0：菜单 BGM（乐句 8-11）
MUSIC_MAP, MUSIC_FIGHT, MUSIC_END = 1, 2, 3   # 音乐槽：地图/战斗/结算 BGM（乐句 19-27）

# ---- Juice 可调参数（帧数@30fps，30 帧=1 秒；原则五：反馈效果集中于此，改表不动逻辑） ----
JUICE = {
    "enabled": True,        # 总开关：一键关全部表现层动画（转场直切、无震屏/粒子/数字）
    "reduce_flash": False,  # 无障碍：削减白闪/红闪强度（遵守 WCAG 每秒≤3 次闪光）
    "reduce_shake": False,  # 无障碍：震屏幅度×0.4
    "trans": {"fade_f": 7, "iris_f": 10, "flash_f": 8},          # 过场：淡入淡出/光圈/白闪
    "jump":  {"ship_f": 12, "cam_f": 15, "pre_f": 2, "dust_n": 4},  # 跳迁：飞行/镜头/后坐/落地尘
    "map":   {"float_a": 1},                                     # 地图：兴趣点悬浮振幅(px)
    "fight": {"freeze_f": 5, "react_f": 10, "red_f": 15, "banner_f": 32,
              "num_f": 20, "kill_n": 10},                        # 战斗：顿帧/受击/红闪/横幅/数字/粒子
    "shake": {"max_px": 2.0, "decay": 0.07, "hit": 0.4, "kill": 0.7},  # trauma 震屏（skill 模型）
}
SHIP_ANCHOR_X = WIN_W // 2 - 15   # 飞船锚定的屏幕 x：正中偏左 15 像素

# ==================== 最终 UI 配色（lospec「YU-NO (PC-98)」十六色，槽位语义重排） ====================
# 色值来源 https://lospec.com/palette-list/yu-no-pc-98 （by sop），未改任何色值；
# 只是把 16 色分配到 pyxel 槽位时对齐了旧调色板的语义与资产精灵的色号：
#   槽 7=白（飞船/白闪）、8=红（敌人/警报）、10=橙黄（升级点/强调）、11=青绿（星球/磷光）、
#   槽 3=岩青（星球暗面/终端暗纹）、6=灰蓝（边框/次级文字）、9=棕橙（升级点外框）——
# 因此 assets/star_voyage.pyxres 里的精灵（用 7/8/9/10/11/3/6 号色）无需重新生成。
# 场景风格：菜单/战斗/升级/结算=PC-98 ADV 实心窗+双线描边；地图=冷战磷光终端（青绿）。
PALETTE = (
    0x000000,  # 0  黑：底色
    0x222222,  # 1  炭灰：窗口实底 / 暗网格
    0x444444,  # 2  深灰：内描边 / 零线 / 扫描线
    0x556666,  # 3  岩青：终端暗纹 / 星球暗面（资产精灵 3 号）
    0x773333,  # 4  深红：危险暗调
    0xBBCCFF,  # 5  淡蓝：亮辅助
    0x99AABB,  # 6  灰蓝：窗口外描边 / 次级文字（资产精灵 6 号）
    0xFFFFFF,  # 7  白：正文 / 飞船 / 白闪（资产精灵 7 号）
    0xDD4455,  # 8  红：敌人 / 警报 / 失败（资产精灵 8 号）
    0xBB7766,  # 9  棕橙：升级点外框（资产精灵 9 号）
    0xFFBB66,  # 10 琥珀：升级点芯 / 强调 / 引擎曲线（资产精灵 10 号）
    0x339988,  # 11 青绿：星球 / 地图磷光主色（资产精灵 11 号）
    0xFFDDCC,  # 12 奶油：亮字（标题/胜利）
    0x5566CC,  # 13 选中蓝：选中项实底
    0xFF99AA,  # 14 粉：备用
    0xEEAA99,  # 15 鲑：备用
)
# ---- 语义色名（场景绘制一律引用这些名字，勿裸写数字色号） ----
C_BG, C_PANEL, C_DIM, C_SLATE, C_DRED = 0, 1, 2, 3, 4
C_LBLUE, C_GREY, C_WHITE, C_RED, C_BROWN = 5, 6, 7, 8, 9
C_ORANGE, C_TEAL, C_CREAM, C_BLUE, C_PINK, C_SALMON = 10, 11, 12, 13, 14, 15


def apply_palette():
    """把 YU-NO(PC-98) 十六色写入 pyxel 全局调色板（须在 pyxel.init 之后调用）。

    pyxel.colors[i] 运行时可写（palette_lab 已验证）；资产版精灵存的是槽位号，
    槽位语义已对齐（见 PALETTE 注释），换板后精灵观感自动正确。
    """
    for i, c in enumerate(PALETTE):
        pyxel.colors[i] = c


def ease_out_cubic(p):
    """缓动函数 ease-out-cubic：1-(1-p)^3，起步快、收尾缓（跳迁/摄像机跟随共用）。"""
    return 1.0 - (1.0 - p) ** 3


def ease_out_back(p):
    """缓动函数 ease-out-back：过冲约 10% 后回弹（胜利横幅弹入用，game-feel 配方）。"""
    c1 = 1.70158
    return 1 + (c1 + 1) * (p - 1) ** 3 + c1 * (p - 1) ** 2

# ==================== 资产层（两版唯一差异区·白盒） ====================

USE_ASSETS = False  # 白盒版：不加载资源文件，图形用几何图元，静音


def _shape_ship(sx, sy):
    """白盒飞船：中心 2px 白色小圆（引擎喷口方向略去，仅示意）。"""
    pyxel.circ(sx, sy, 2, 7)  # 7 = 白色


def _shape_planet(sx, sy):
    """白盒星球：3px 绿色圆（对应资产版星球精灵）。"""
    pyxel.circ(sx, sy, 3, 11)  # 11 = 绿色


def _shape_enemy(sx, sy):
    """白盒敌人：红色三角（文档建议的符号：敌人=三角）。"""
    pyxel.tri(sx, sy - 4, sx - 4, sy + 3, sx + 4, sy + 3, 8)  # 8 = 红色


def _shape_upgrade(sx, sy):
    """白盒升级点：6x6 黄色方块（文档建议的符号：升级=方块）。"""
    pyxel.rect(sx - 3, sy - 3, 6, 6, 10)  # 10 = 黄色


# 精灵槽位 -> 白盒图元绘制函数（与资产版的 SPR_* 槽位一一对应）
_SPR_SHAPE = {SPR_SHIP: _shape_ship, SPR_PLANET: _shape_planet,
              SPR_ENEMY: _shape_enemy, SPR_UPGRADE: _shape_upgrade}


def load_assets():
    """加载资产（App 启动时调用一次）。白盒版无资产可载：空操作。"""
    pass  # 无 BGM、无音效，保持与资产版完全相同的调用点


def draw_sprite(sx, sy, spr):
    """按精灵槽位 spr=(u,v) 在屏幕 (sx,sy) 画图形。白盒版用几何图元代替 blt。"""
    _SPR_SHAPE[spr](sx, sy)  # 查表分派到对应的图元函数


def play_sfx(snd):
    """播放音效槽位 snd。白盒版静音：空操作（调用点与资产版完全一致）。"""
    pass


def play_bgm(music):
    """切换背景音乐槽位 music。白盒版静音：空操作（调用点与资产版完全一致）。"""
    pass

# ==================== 全局状态（沿用骨架约定） ====================
SEED_NOW = 42         # 本局个人种子（开局由菜单写入）
SEED_USED = 0         # 已启用过的种子（首次落子时与 SEED_NOW 对齐）
CURRENT_DISTANCE_X = 0.0  # 当前遭遇敌人的 x 坐标（Enemy 构造时同步）


# ==================== 字体层（凤凰点阵体，两版共用） ====================
# pyxel 内置字体渲染不了中文，但 pyxel.Font 可加载 TTF/BDF 点阵字体；
# 此处用"凤凰点阵体"（VonwaonBitmap，原生 12/16px 点阵，免费商用）实现中文 UI。
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "assets", "fonts")   # 字体文件随项目分发
_FONT_CACHE = {}       # 字号 -> pyxel.Font 缓存（见 font() 说明）

def font(size=12):
    """惰性加载凤凰点阵体（首次调用需在 pyxel.init 之后，故不放在模块顶层——
    pytest 导入本模块时 pyxel 尚未初始化）。"""
    f = _FONT_CACHE.get(size)
    if f is None:
        path = os.path.join(FONT_DIR, f"VonwaonBitmap-{size}px.ttf")
        f = pyxel.Font(path, size)          # 第二参数=渲染字号（用原生点阵字号最锐利）
        _FONT_CACHE[size] = f
    return f

def txt(x, y, s, col, big=False):
    """统一文本绘制：默认 12px；big=True 用 16px（标题/横幅）。"""
    pyxel.text(x, y, s, col, font(16 if big else 12))

def txt_center(y, s, col, big=False):
    """按 text_width 实测宽度做水平居中绘制。"""
    f = font(16 if big else 12)
    pyxel.text(max(0, (WIN_W - f.text_width(s)) // 2), y, s, col, f)


# ==================== 多语言层（zh 中文 / en 英文；菜单与指南页按 TAB 切换） ====================
# 只翻译显示层：引擎/技能/子系统/兴趣点的中文名是逻辑分支键（改名即断功能），
# 一律经 *_EN 对照表映射显示名；Fight.log 的中文原文保留（pytest 断言不受影响），
# 上屏前经 tr_log() 按行格式重建英文。全部英文文案已用 font().text_width 实测宽度。
LANG = "zh"   # 当前界面语言（会话级：菜单/指南 TAB 切换，回到菜单不清空）

T = {         # 固定文案对照表（英文全部实测不超窗）
    # ---- 菜单 ----
    "星际远航": "STAR VOYAGE",
    "种子 SEED": "SEED",
    "退格删除": "Bksp",
    "上下选引擎": "Up/Down",
    "回车 · 启航": "Enter Launch",
    # ---- 指南 ----
    "航行指南 GUIDE": "GUIDE",
    "目标：跳到 x>42 的兴趣点即可逃离": "Goal: POI beyond x>42",
    "移动：上下选目标，回车跳迁，距离有限": "Arrows pick, Enter jump",
    "星球=跳板  敌人=战斗  升级=强化": "Planets hop, Foes fight",
    "战斗：引擎每回合掷出出力 N": "Engine rolls N each turn",
    "N≤0 为故障，按 1/2/3 任意键跳过": "N<=0 fault: 1/2/3 skips",
    "1 攻击  2 防御  3 蓄力": "1 Attack 2 Def 3 Charge",
    "Q/W/E/R 主动技能，消耗备用能量": "Q/W/E/R skills use NRG",
    "敌人越远越强，其坐标决定数值": "Farther foes are stronger",
    "升级：移动力 / 引擎 / 子系统强化": "Upgrades: range/eng/sys",
    "无可达目标时燃料耗尽，任务失败": "No target = out of fuel",
    # ---- 地图 ----
    "逃离线 x>42": "ESCAPE x>42",
    "回车 跳跃": "Enter Jump",
    # ---- 战斗 ----
    "敌舰 HOSTILE": "HOSTILE",
    "本舰 SHIP": "SHIP",
    "引擎 N-i": "ENG N-i",
    "按 [1][2][3] 跳过故障回合": "Press 1/2/3 to skip fault",
    "按回车继续": "Enter to continue",
    "胜利！": "VICTORY!",
    "战败": "DEFEAT",
    "未拥有该技能": "No such skill",
    "本场已用过": "Used this fight",
    "引擎未故障": "Engine not faulted",
    "能量不足": "Not enough energy",
    "战斗已结束": "Fight is over",
    "非故障回合": "Not a fault turn",
    "故障：无法分配": "Fault: cannot assign",
    # ---- 升级 ----
    "升级 UPGRADE": "UPGRADE",
    "升级": "Upgrade",
    "上下选 回车确认": "Up/Dn Enter",
    "远航升级：移动力+0.5cm": "Sail: range +0.5cm",
    "引擎改造：选2个参数×1.1": "Engine: 2 params x1.1",
    "强化子系统：分配时+2": "System: assign +2",
    "被动·半衰：战后留一半能量": "Passive: half energy",
    "被动·回收：火炮伤害+2能量": "Passive: hit +2 NRG",
    "引擎改造 · 选 ×1.1 参数": "Engine: pick x1.1",
    "强化子系统 · 选择目标": "System: pick one",
    "二级选项应用后返回地图": "Back to map",
    "上下选 回车确认 ESC返回": "Up/Dn Enter ESC back",
    # ---- 结算 ----
    "逃离成功！": "ESCAPED!",
    "游戏结束": "GAME OVER",
    "航程 x>42 · 任务日志已归档": "Beyond x>42 · archived",
    "能源耗尽 · 任务中止": "Out of fuel · mission end",
    "按回车返回菜单": "Enter for menu",
}

# 逻辑名 -> 英文显示名（逻辑键中文保持不变）
ENGINE_EN = {ENG_SIN: "SINE", ENG_GEO: "GEOMETRIC", ENG_CHAOS: "CHAOS"}
SYS_EN = {"火炮": "Cannon", "护盾": "Def", "能量": "Pwr"}
SKILL_EN = {"火力过载": "Overload", "应急护盾": "E Shield",
            "输出校准器": "Calibr", "故障抑制器": "Suppress"}
POI_EN = {"星球": "Planet", "敌人": "Enemy", "升级": "Upgrade"}
PARAM_EN = {ENG_SIN: {"A": "amp", "B": "freq", "C": "lift"},   # 升级子选单的参数含义
            ENG_GEO: {"A": "base", "B": "mult", "C": "ratio"},
            ENG_CHAOS: {"A": "init", "B": "coef", "C": "bias"}}
ENGINE_ABC_EN = {ENG_SIN: "A amp B freq C lift",               # 菜单图例（EN 独占一行）
                 ENG_GEO: "A base B mult C ratio",
                 ENG_CHAOS: "A init B coef C bias"}


def tr(s):
    """固定文案显示翻译：en 查 T 表（缺译原样返回，宁显示中文不出错）；zh 原样。"""
    return T.get(s, s) if LANG == "en" else s


def tr_name(name, table):
    """逻辑名 -> 显示名：en 查对照表；zh 原样。"""
    return table.get(name, name) if LANG == "en" else name


def tr_log(line):
    """战斗流水的显示翻译：按行格式重建英文（Fight.log 中文原文不变，逻辑/测试不受影响）。"""
    if LANG != "en":
        return line
    if line.startswith("回合"):                       # "回合12 N=8【故障】"
        return line.replace("回合", "T", 1).replace("【故障】", " FAULT")
    if line.startswith("  故障·跳过"):
        return "  Fault skip"
    if line.startswith("  火炮"):                     # "  火炮 8 → 伤害6"
        return line.replace("  火炮", "  Cannon", 1).replace(" → 伤害", " d")
    if line.startswith("  敌击"):                     # "  敌击2 盾抵0"
        return line.replace("  敌击", "  Hit", 1).replace(" 盾抵", " blk")
    if line.startswith("  护盾"):
        return line.replace("  护盾", "  Def", 1)
    if line.startswith("  能量"):
        return line.replace("  能量", "  Pwr", 1)
    if line.startswith("  回收"):
        return "  Recyc +2"
    if line.startswith("  ") and "·" in line:         # "  Q·火力过载 耗3能"
        k, rest = line[2:].split("·", 1)
        name, cost = rest.split(" 耗")
        return f"  {k}·{SKILL_EN.get(name, name)} c{cost[:-1]}"
    return tr(line)                                   # 胜利！/战败 走通用表


def tr_skill_label(payload, lv_next):
    """升级选单的技能项标签：中文模板式，英文重建（火力过载 -> Skill: Overload L2）。"""
    if LANG == "en":
        return f"Skill: {SKILL_EN.get(payload, payload)} L{lv_next}"
    return f"技能·{payload} → Lv{lv_next}"


# ==================== UI chrome 助手（最终方案的公共仪表画法） ====================
def ui_window(x, y, w, h, label=None):
    """PC-98 ADV 窗口：炭灰实底 + 灰蓝外描边 + 深灰内描边；label 为嵌在上边线的铭牌。

    90 年代日式电脑 ADV 的经典窗口样式（实心深灰 + 双线描边），
    五个场景的面板全部经由本函数绘制，保证「全舰总线」观感统一。
    """
    pyxel.rect(x, y, w, h, C_PANEL)                      # 实心窗底
    pyxel.rectb(x, y, w, h, C_GREY)                      # 外描边（灰蓝）
    pyxel.rectb(x + 2, y + 2, w - 4, h - 4, C_DIM)       # 内描边（深灰）
    if label:                                            # 铭牌：擦开上边线嵌入小字
        lw = font().text_width(label)                    # 实测铭牌宽度
        pyxel.rect(x + 6, y, lw + 4, 1, C_PANEL)         # 用窗底色擦出缺口
        txt(x + 8, y - 6, label, C_GREY)                 # 铭牌悬于边线之上


def ui_corners(x, y, w, h, arm, col):
    """角括号（取景框/准星）：四角各画两条 arm 长的短线，比圆圈更像舰载 HUD。"""
    arm = max(2, int(arm))
    pyxel.rect(x, y, arm, 1, col); pyxel.rect(x, y, 1, arm, col)            # 左上
    pyxel.rect(x + w - arm, y, arm, 1, col); pyxel.rect(x + w - 1, y, 1, arm, col)  # 右上
    pyxel.rect(x, y + h - 1, arm, 1, col); pyxel.rect(x, y + h - arm, 1, arm, col)  # 左下
    pyxel.rect(x + w - arm, y + h - 1, arm, 1, col)                          # 右下
    pyxel.rect(x + w - 1, y + h - arm, 1, arm, col)


def ui_gauge(x, y, w, frac, col, crit=False):
    """分段仪表条：3px 一段（2 实 + 1 隙）；frac 夹取 [0,1]；crit=危险值整条闪烁。"""
    blink_on = pyxel.frame_count % 16 < 10               # 闪烁相位（约 0.53s 周期）
    frac = max(0.0, min(1.0, frac))
    n = w // 3                                           # 段数
    lit = round(n * frac)                                # 点亮段数
    for i in range(n):
        c = col if i < lit else C_DIM                    # 未点亮段画深灰刻度
        if crit and i < lit and not blink_on:
            c = C_DIM                                    # 危险闪烁：亮段间歇熄灭
        pyxel.rect(x + i * 3, y, 2, 5, c)


def ui_sparkline(x, y, w, h, vals, curve, zero, ylo=-6, yhi=14):
    """迷你函数曲线（菜单引擎槽缩略图）：零线虚线 + 相邻点连线，值超界截断。

    与战斗页示波器共用 [-6,14] 纵轴语义：曲线探到零线以下 = 该回合引擎故障，
    玩家在选引擎时即可凭曲线形状读懂三种引擎的性格差异。
    """
    def sy(v):
        """出力 v -> 曲线区像素 y（夹取在 [ylo,yhi] 显示范围内）。"""
        return y + h - 1 - (min(max(v, ylo), yhi) - ylo) / (yhi - ylo) * (h - 1)
    zy = int(sy(0))                                       # 零线（其下即故障区）
    for dx in range(x, x + w, 3):
        pyxel.rect(dx, zy, 2, 1, zero)
    prev = None
    for i, v in enumerate(vals):                          # 16 个预览点连线成曲线
        cur = (x + round(i * (w - 1) / (len(vals) - 1)), int(sy(v)))
        if prev is not None:
            pyxel.line(prev[0], prev[1], cur[0], cur[1], curve)
        prev = cur


def ui_backdrop():
    """ADV 场景公共背景：纯黑底 + 确定性星尘（同一种子每帧同一片星空）。"""
    for i in range(34):                                  # 34 颗星：亮暗两档
        sx, sy = (i * 89 + 17) % WIN_W, (i * 47 + 31) % WIN_H
        pyxel.pset(sx, sy, C_GREY if i % 5 == 0 else C_DIM)


def ui_bezel(corners_only=False):
    """屏幕外框：整屏当作一台仪器的边框；密集场景传 corners_only 只画四角省空间。"""
    if corners_only:
        ui_corners(0, 0, WIN_W, WIN_H, 6, C_GREY)
        return
    pyxel.rectb(1, 1, WIN_W - 2, WIN_H - 2, C_DIM)       # PC-98：单圈深灰细边


# ==================== 生成器引擎（纯逻辑） ====================
class Engine:
    """生成器引擎：战斗中每回合产出一个出力 Ni，驱动三个子系统。

    三种引擎对应 PDF 的三条公式，行为规则不同但接口一致：
      正弦波   Ni = ⌊A·sin(B·i) + C⌋            （周期波动，可预测）
      等比数列 Ni = A + ⌊B·(-C)^i⌋              （奇数回合固定出负值，后期更高）
      迭代混沌 N0 = A, Ni = ⌊B·sin(N(i-1)) + C⌋ （看似随机实则确定）
    """

    def __init__(self, name):
        """按引擎名初始化 ABC 参数并重置回合。未知引擎名直接抛 ValueError。"""
        self.name = name                    # 引擎名同时是公式分支依据
        if name == ENG_SIN:                 # 正弦波默认参数 A=5 B=1 C=4
            self.A, self.B, self.C = 5.0, 1.0, 4.0
        elif name == ENG_GEO:               # 等比数列默认参数 A=1 B=2 C=1.2
            self.A, self.B, self.C = 1.0, 2.0, 1.2
        elif name == ENG_CHAOS:             # 迭代混沌默认参数 A=4 B=7 C=2
            self.A, self.B, self.C = 4.0, 7.0, 2.0
        else:
            raise ValueError(f"未知引擎: {name}")  # 拼写保护：宁崩勿默跑
        self.reset()

    def reset(self):
        """重置回合状态（每场战斗开始时调用；迭代混沌的 N0 = A）。"""
        self.turn = 0        # 已生成的回合计数，generate() 时先自增
        self.prev = self.A   # 迭代混沌的上一项 N(i-1)，初始即 N0 = A

    def generate(self):
        """生成下一个出力 Ni（floor 取整，负值代表引擎故障）。"""
        self.turn += 1
        i = self.turn                          # 公式中的回合号 i 从 1 开始
        if self.name == ENG_SIN:
            # Ni = ⌊A·sin(B·i) + C⌋：A=振幅，B=角频率，C=直流抬升
            return math.floor(self.A * math.sin(self.B * i) + self.C)
        if self.name == ENG_GEO:
            # Ni = A + ⌊B·(-C)^i⌋：(-C)^i 交替变号 -> 奇数回合出负值
            return math.floor(self.A + self.B * (-self.C) ** i)
        # 迭代混沌：Ni = ⌊B·sin(N(i-1)) + C⌋，用上一项喂下一项（无 i）
        self.prev = math.floor(self.B * math.sin(self.prev) + self.C)
        return self.prev

    def preview(self, upto):
        """预览从战斗起点起 upto 个回合的出力序列（不推进自身状态）。

        战斗界面用它绘制"Ni-回合"函数图像：每场战斗开始时引擎都会 reset，
        故预览固定从 N0=A 起算，与实战逐回合结果完全一致。
        """
        out = []
        prev = self.A                        # 与 reset() 后的初始状态一致
        for i in range(1, upto + 1):
            if self.name == ENG_SIN:         # 正弦波：回合号的闭式函数
                out.append(math.floor(self.A * math.sin(self.B * i) + self.C))
            elif self.name == ENG_GEO:       # 等比数列：同为闭式
                out.append(math.floor(self.A + self.B * (-self.C) ** i))
            else:                            # 迭代混沌：喂局部变量逐项迭代
                prev = math.floor(self.B * math.sin(prev) + self.C)
                out.append(prev)
        return out

    def upgrade_params(self, pair):
        """引擎改造（永久升级项之一）：pair 取 'AB'/'AC'/'BC'，所选两参数各 x1.1。"""
        for k in pair:                 # pair 是两位字符串，如 "AB" -> A、B
            setattr(self, k, getattr(self, k) * 1.1)  # 参数乘 1.1（PDF 升级规则）
        self.reset()                   # 参数变了，序列从头开始才可复现


# ==================== 星图（纯逻辑） ====================
class StarMap:
    """星图：用个人种子 S 按文档公式生成三类兴趣点，坐标四舍五入为整数（cm）。

    points 为 [(类型, x, y), ...]：前 12 个普通星球、中 15 个敌人、后 15 个升级点。
    """

    def __init__(self, seed):
        """以种子 seed 生成整张星图。"""
        self.seed = seed      # 个人种子 S（建议不超过 5 位数，PDF 建议）
        self.points = []      # 全部兴趣点，顺序固定：星球12 + 敌人15 + 升级15
        self.generate()

    def generate(self):
        """按文档公式批量生成 42 个兴趣点并四舍五入成整数坐标。"""
        s10 = self.seed / 10.0                # 公式中的公共因子 S/10
        self.points = []
        for i in range(1, 13):                # 普通星球：i ∈ [1,12]
            x = round(3 * i + math.sin(i + s10))       # xi = 3i + sin(i + S/10)
            y = round(3 * i + math.cos(i * s10))       # yi = 3i + cos(i·S/10)
            self.points.append(("星球", x, y))
        for i in range(1, 16):                # 敌人：i ∈ [1,15]
            x = round(3.5 * i + 2 * math.cos(i * s10))  # xi = 3.5i + 2cos(i·S/10)
            y = round(2.5 * i + 5 * math.sin(i * s10))  # yi = 2.5i + 5sin(i·S/10)
            self.points.append(("敌人", x, y))
        for i in range(1, 16):                # 升级点：i ∈ [1,15]
            x = round(3 * i + 3 * math.sin(i + s10))    # xi = 3i + 3sin(i + S/10)
            y = round(3.2 * i + 3 * math.sin(i * s10))  # yi = 3.2i + 3sin(i·S/10)
            self.points.append(("升级", x, y))


# ==================== 敌人（纯逻辑） ====================
class Enemy:
    """敌人：三项数值全部由【它自己的坐标 xe】按文档公式决定（越远越强）。"""

    def __init__(self, xe):
        """按敌人坐标 xe 计算生命/攻击/防御。"""
        global CURRENT_DISTANCE_X
        CURRENT_DISTANCE_X = xe               # 同步全局（沿用骨架变量，供外部观察）
        self.xe = xe                          # 敌人自身 x 坐标（数值来源）
        self.max_hp = 8 + xe // 2             # HP = 8 + ⌊xe/2⌋（// 即 floor）
        self.hp = self.max_hp                 # 当前 HP（战斗中被火炮扣减）
        self.atk = 1 + xe // 10               # ATK = 1 + ⌊xe/10⌋（骨架误用 /2，已纠）
        self.defence = abs(xe) // 4           # DEF = ⌊|xe|/4⌋（骨架漏了取整，已纠）


# ==================== 飞船（逻辑 + 实体绘制） ====================
class Ship:
    """飞船实体：引擎 + 火炮/护盾/能量三子系统 + 升级成长 + 地图移动。

    逻辑方法不碰 pyxel（pytest 可覆盖）；唯一例外是 draw()——
    实体自带绘制是官方示例惯例，由 MapScene 每帧调用。
    """

    def __init__(self, engine_name):
        """以指定引擎开局：满血、零护盾/能量、停在原点。"""
        self.engine = Engine(engine_name)     # 生成器引擎（开局三选一）
        self.hp = PLAYER_HP                   # 飞船 HP（归零即失败）
        self.max_move_dis = PLAYER_MAX_MOVE_DIS  # 最大移动距离 cm（远航升级可+0.5）
        self.shield = 0                       # 护盾值（每场战斗开始清零，无上限）
        self.energy = 0                       # 备用能量（主动技能的燃料）
        self.bonus = dict.fromkeys(SYS_LIST, 0)  # 子系统升级加成：分配到该系统时 +2/级
        self.passives = set()                 # 已获得的被动技能名集合
        self.skills = {}                      # 主动技能名 -> 等级(1..3)
        self.used_skills = set()              # 本场战斗已用过的主动技能（限一次）
        self.x, self.y = 0, 0                 # 当前坐标（cm），从原点出发
        self.visited = {(0, 0)}               # 已探索坐标集合（原点即视为已探索）

    def start_battle(self):
        """战斗开始时的重置：护盾清零、技能限用清空、引擎序列重置。

        备用能量刻意不清零——"半衰期循环"被动的意义就是把能量带过场。
        """
        self.shield = 0                # 文档：护盾战斗开始时为 0
        self.used_skills.clear()       # 每种技能每场限一次 -> 换场重置
        self.engine.reset()            # 引擎序列每场从头跑（可复现）

    def reachable(self, points):
        """筛选当前可达的兴趣点：未探索 且 距离 <= 最大移动距离。

        返回 [(类型, x, y), ...]，供地图场景渲染与选择；不可重访已探索点。
        """
        out = []
        for t, x, y in points:                            # 遍历全部兴趣点
            if (x, y) in self.visited:                    # 规则：不可重访
                continue
            if math.hypot(x - self.x, y - self.y) <= self.max_move_dis + 1e-9:
                out.append((t, x, y))                     # 欧氏距离 <= 移动力
        return out

    def move_to(self, x, y):
        """跳迁到 (x,y) 并标记为已探索（每回合在两个兴趣点间移动一次）。"""
        self.x, self.y = x, y        # 更新飞船坐标
        self.visited.add((x, y))     # 落点即已探索（不可再次到访）

    # ---- 五种升级（升级点的选项，见 LevelupScene） ----
    def upgrade_sail(self):
        """永久升级·远航：最大移动距离 +0.5cm（可叠加）。"""
        self.max_move_dis += 0.5

    def upgrade_engine(self, pair):
        """永久升级·引擎改造：选 ABC 中两个参数各 x1.1（pair='AB'/'AC'/'BC'）。"""
        self.engine.upgrade_params(pair)

    def upgrade_subsystem(self, system):
        """永久升级·子系统升级：该系统每次分配出力时额外 +2（可叠加）。"""
        self.bonus[system] += 2

    def gain_passive(self, name):
        """获得被动技能（半衰期循环 / 能量回收，各只能获得一次）。"""
        self.passives.add(name)

    def gain_or_upgrade_skill(self, name):
        """获得主动技能或升一级（未拥有->Lv1；已有->+1；封顶 Lv3）。"""
        self.skills[name] = min(3, self.skills.get(name, 0) + 1)

    # ---- 绘制（官方示例惯例：实体自带 draw） ----
    def draw(self, cam_x, cam_y):
        """把飞船画到屏幕（尾焰双像素交替闪烁；光环职责已由地图页雷达圈取代）。"""
        sx = int(self.x * CM_TO_PX - cam_x)                  # 世界cm -> 屏幕px（x 轴向右）
        sy = int(self.y * CM_TO_PX + Y_OFFSET_PX - cam_y)    # y 轴向上 + 负坐标余量
        draw_sprite(sx, sy, SPR_SHIP)                        # 船体（白盒=图元/资产=精灵）
        on = pyxel.frame_count % 6 < 3                       # 尾焰两像素左右交替（青绿/白）
        pyxel.pset(sx - 1, sy + 3, C_TEAL if on else C_WHITE)
        pyxel.pset(sx + 1, sy + 3, C_WHITE if on else C_TEAL)


# ==================== 战斗（纯逻辑，声音走事件标签） ====================
class Fight:
    """一场战斗的回合制状态机：玩家先动，敌人还手，循环到一方 HP 归零。

    本类不直接发声：把 ship_hit/kill/win/lose 追加进 events，
    由 FightScene 消费并翻译成 pyxel.play（保持逻辑层可测）。
    """

    def __init__(self, player, enemy_x):
        """以飞船 player 迎战坐标 enemy_x 处的敌人，初始化一场战斗。"""
        self.player = player          # 参战的飞船（沿用其全部成长状态）
        self.enemy = Enemy(enemy_x)   # 敌人数值由其坐标决定
        player.start_battle()         # 护盾清零/技能限用重置/引擎重置
        self.turn_no = 0              # 当前回合号（begin_turn 后从 1 开始）
        self.ni = 0                   # 本回合引擎出力 Ni（<=0 即故障）
        self.fault = False            # 引擎故障标志（故障回合无法分配出力）
        self.msg = None               # 最近一次非法操作的英文提示（直接上屏）
        self.log = []                 # 战斗流水（屏显最近 7 行，纯 ASCII）
        self.events = []              # 反馈事件标签：ship_hit/kill/win/lose/fault
        self.last_dmg = 0             # 最近一次火炮伤害（场景上飘数字的数据源）
        self.last_hit = 0             # 最近一次敌击落到 HP 的伤害（同上）
        self.over = False             # 战斗是否结束
        self.win = False              # 结束时的胜负

    def begin_turn(self):
        """开启下一个玩家回合：掷引擎出力并判定故障（开场过场由场景层负责）。"""
        self.turn_no += 1                            # 回合推进
        self.ni = self.player.engine.generate()      # 本回合出力 Ni
        self.fault = self.ni <= 0                    # PDF：Ni<=0 视为引擎故障
        if self.fault:                               # 故障判定瞬间即发警报事件
            self.events.append("fault")              # （时机修正：原在"跳过"时才响）
        self.msg = None                              # 新回合清掉上一回合的报错
        self.log.append(f"回合{self.turn_no} N={self.ni}"
                        + ("【故障】" if self.fault else ""))  # 记流水（紧凑格式防溢窗）

    def cast_skill(self, name):
        """施放主动技能（技能名横幅动画由战斗场景在成功时触发）。
        成功返回 None，失败返回中文原因（上屏提示）。"""
        lv = self.player.skills.get(name, 0)
        if lv == 0:                                   # 没学过这个技能
            return "未拥有该技能"
        if name in self.player.used_skills:           # PDF：每场战斗限用一次
            return "本场已用过"
        if name == "故障抑制器" and not self.fault:    # 抑制器只在故障回合有意义
            return "引擎未故障"
        cost = SKILL_COST[name][lv - 1]               # 查本级消耗（随等级降低/不变）
        if self.player.energy < cost:                 # 备用能量不足
            return "能量不足"
        self.player.energy -= cost                    # 扣能量
        self.player.used_skills.add(name)             # 记名：本场不再可用
        if name == "火力过载":                         # 效果：本回合 Ni 翻倍
            self.ni *= 2
        elif name == "应急护盾":                       # 效果：护盾清零后立刻获得 4/5/6
            self.player.shield = 3 + lv               # lv1/2/3 -> 4/5/6
        elif name == "输出校准器":                     # 效果：Ni 强制改为 5/6/7
            self.ni = 4 + lv                          # lv1/2/3 -> 5/6/7
        elif name == "故障抑制器":                     # 效果：|Ni| 作为本回合最终结果
            self.ni = abs(self.ni)                    # 如 -3 -> 3，可解除故障
        self.fault = self.ni <= 0                     # 统一重判：校准/抑制可解故障，
        self.log.append(f"  {SKILL_HOTKEY[name]}·{name} 耗{cost}能")  # 流水（紧凑防溢窗）
        return None

    def assign(self, system):
        """把本回合出力 Ni(+子系统加成) 分配给三系统之一（顿帧由场景层负责）。
        成功返回 None。"""
        if self.fault:                                # 故障回合禁止攻击/防御
            return "故障：无法分配"
        val = self.ni + self.player.bonus[system]     # 子系统升级加成 +2/级 在此生效
        if system == "火炮":
            dmg = max(0, val - self.enemy.defence)    # 实际伤害 = 攻击 - 敌DEF（不低于0）
            self.last_dmg = dmg                        # 记录：场景命中数字的数据源
            self.enemy.hp -= dmg                      # 扣敌人 HP
            self.log.append(f"  火炮 {val} → 伤害{dmg}")
            if dmg > 0 and "能量回收" in self.player.passives:  # 被动：造成伤害即回能
                self.player.energy += 2
                self.log.append("  回收 +2能")
            if self.enemy.hp <= 0:                    # 敌人 HP 归零 -> 战斗胜利
                self.events.append("kill")
                self._finish(True)
        elif system == "护盾":
            self.player.shield += val                 # 获得护盾（无上限，本战斗有效）
            self.log.append(f"  护盾 +{val}")
        else:  # 能量
            self.player.energy += val                 # 存入备用能量（驱动主动技能）
            self.log.append(f"  能量 +{val}")
        return None

    def skip_fault_turn(self):
        """故障回合的"跳过"：无法攻击/防御，直接让敌人行动（红闪由场景层负责）。

        没有此接口时，故障回合若无可用的解故障技能，玩家将无法结束回合（软锁）。
        成功返回 None；非故障回合或战斗已结束时返回错误原因。
        """
        if self.over:                       # 战斗已结束
            return "战斗已结束"
        if not self.fault:                  # 非故障回合应走 assign 而不是跳过
            return "非故障回合"
        self.log.append("  故障·跳过")      # 记流水：本回合让过
        self.enemy_turn()                   # 敌人照常行动，随后自动开下一回合
        return None

    def enemy_turn(self):
        """敌人回合：造成 ATK 点伤害（护盾优先承受）；随后自动开启下一玩家回合。"""
        if self.over:                                 # 战斗已结束则不再行动
            return
        absorbed = min(self.player.shield, self.enemy.atk)  # 护盾能吃掉的部分
        self.player.shield -= absorbed               # 先扣护盾
        self.player.hp -= self.enemy.atk - absorbed  # 剩余伤害才落到 HP
        self.last_hit = self.enemy.atk - absorbed    # 记录：受击数字的数据源
        self.log.append(f"  敌击{self.enemy.atk} 盾抵{absorbed}")
        self.events.append("ship_hit")               # 事件：飞船受击（场景转音效）
        if self.player.hp <= 0:                      # 飞船 HP 归零 -> 战斗失败
            self._finish(False)
        else:
            self.begin_turn()                        # 下一玩家回合（玩家先动循环）

    def _finish(self, win):
        """战斗结算：无被动则能量清零；半衰期循环保留一半（向下取整）。"""
        self.over = True
        self.win = win
        if "半衰期循环" in self.player.passives:     # 被动：能量带一半去下一场
            self.player.energy //= 2                 # ⌊E/2⌋
        else:                                        # 常规：战斗结束能量归零
            self.player.energy = 0
        self.log.append("胜利！" if win else "战败")
        self.events.append("win" if win else "lose")  # 事件：胜负音效
        # 结束后的背景压暗渐入由战斗场景的 draw 负责（衬出胜负横幅）


# ==================== 场景层（每个场景都实现 update()/draw()） ====================
class MenuScene:
    """菜单场景：数字键输入个人种子 S + 上下键三选一引擎 + 回车开局。

    进出菜单的淡入淡出过场由 App.change_scene(trans="fade") 统一负责。
    """

    def __init__(self, app):
        """进入菜单：清空种子输入、光标停在第一个引擎，预取各引擎曲线。"""
        self.app = app           # 宿主 App（用于切换场景/开新局）
        self.seed_input = ""     # 已键入的种子字符串（空则默认 42）
        self.engine_idx = 0      # 引擎光标（0/1/2 对应 ENGINES 顺序）
        self.previews = {name: Engine(name).preview(16)   # 各引擎前 16 回合出力序列
                         for name in ENGINES}             # （纯构造无副作用，槽内缩略图用）

    def update(self):
        """处理菜单输入：TAB 切语言，数字/退格编辑种子，上下选引擎，回车开局。"""
        global LANG                                  # 语言是会话级全局（显示层专用）
        if pyxel.btnp(pyxel.KEY_TAB):                # TAB：中/英切换（每次开始都可改）
            LANG = "en" if LANG == "zh" else "zh"
            play_sfx(SND_CURSOR)
        for k in range(pyxel.KEY_0, pyxel.KEY_9 + 1):        # 扫一遍数字键 0-9
            if pyxel.btnp(k) and len(self.seed_input) < 5:   # 限 5 位（PDF 建议值）
                self.seed_input += str(k - pyxel.KEY_0)      # 键码差即数字字符
                play_sfx(SND_TYPE)                           # 输入滴答（T1 反馈）
        if pyxel.btnp(pyxel.KEY_BACKSPACE):                  # 退格：删最后一位
            self.seed_input = self.seed_input[:-1]
            play_sfx(SND_TYPE)
        if pyxel.btnp(pyxel.KEY_UP):                         # 上：引擎光标循环上移
            self.engine_idx = (self.engine_idx - 1) % len(ENGINES)
            play_sfx(SND_CURSOR)
        if pyxel.btnp(pyxel.KEY_DOWN):                       # 下：引擎光标循环下移
            self.engine_idx = (self.engine_idx + 1) % len(ENGINES)
            play_sfx(SND_CURSOR)
        if pyxel.btnp(pyxel.KEY_RETURN):                     # 回车：以当前种子+引擎开局
            play_sfx(SND_CONFIRM)                            # 开局确认音（T3 反馈）
            seed = int(self.seed_input) if self.seed_input else 42  # 空输入默认 42
            self.app.start_run(seed, ENGINES[self.engine_idx])

    def draw(self):
        """绘制菜单（PC-98 风，随 LANG 双语）：星尘+外框、标题饰线、种子窗、引擎槽、启航钮。"""
        pyxel.cls(C_BG)                                  # 黑底
        ui_backdrop()                                    # 确定性星尘
        ui_bezel()                                       # 屏幕外框
        txt(4, 2, "TAB 中/EN", C_DIM)                    # 语言切换提示（左上角，双语常显）
        txt_center(10, tr("星际远航"), C_WHITE, big=True)  # 标题（16px 居中）
        mid = WIN_W // 2                                 # 标题下饰线：断线+菱形
        for sx0 in (mid - 64, mid + 16):                 # 左右两段虚线（8px 周期）
            for dx in range(0, 48, 6):
                pyxel.rect(sx0 + dx, 29, 3, 1, C_DIM)
        for dx, dy in ((-6, -1), (-8, 0), (-6, 1), (5, -1), (7, 0), (5, 1)):
            pyxel.pset(mid + dx, 29 + dy, C_ORANGE)      # 中央两枚菱形（琥珀）
        # 种子输入窗（铭牌嵌上边线；光标块闪烁）
        fx, fy, fw, fh = 44, 36, 152, 17
        ui_window(fx, fy, fw, fh, tr("种子 SEED"))
        seed_show = self.seed_input if self.seed_input else "42"  # 空输入提示默认值
        txt(fx + 9, fy + 3, seed_show, C_WHITE)
        if pyxel.frame_count % 20 < 12:                  # 输入光标：亮 12 帧灭 8 帧
            pyxel.rect(fx + 9 + font().text_width(seed_show), fy + 3, 6, 10, C_ORANGE)
        txt(fx + fw - 9 - font().text_width(tr("退格删除")), fy + 3,
            tr("退格删除"), C_GREY)
        # 引擎选择行：中文=左提示+右图例合排；英文=图例独占一行（英文较长，提示由指南承担）
        if LANG == "en":
            txt(24, 59, ENGINE_ABC_EN[ENGINES[self.engine_idx]], C_ORANGE)
        else:
            txt(24, 59, "上下选引擎", C_GREY)
            legend = ENGINE_ABC[ENGINES[self.engine_idx]]     # 当前选中引擎的参数含义
            txt(216 - font().text_width(legend), 59, legend, C_ORANGE)
        # 引擎槽位：名称 + 各自的 Ni-i 曲线缩略图（函数可视化解释引擎性格）
        ex, ew = 24, 192
        for i, name in enumerate(ENGINES):
            ey = 72 + i * 20
            sel = i == self.engine_idx                   # 是否选中槽
            ui_window(ex, ey, ew, 18)                    # 每引擎一扇小窗
            if sel:
                pyxel.rect(ex + 3, ey + 3, ew - 6, 12, C_BLUE)   # 选中蓝底
            mark = "▸ " if sel else "  "                 # 选中行加光标箭头
            txt(ex + 8, ey + 3, mark + tr_name(name, ENGINE_EN),
                C_WHITE if sel else C_GREY)              # 选中白字反白、未选灰字
            ui_sparkline(ex + 104, ey + 3, 84, 12,       # 曲线缩略图（16 回合预览）
                         self.previews[name],
                         C_ORANGE if sel else C_GREY,    # 选中槽曲线与图例同色
                         C_WHITE if sel else C_DIM)      # 零线（其下=故障区）
        # 启航钮（呼吸提示）
        bw, bh, by = 112, 16, 137
        bx = (WIN_W - bw) // 2
        ui_window(bx, by, bw, bh)
        s = tr("回车 · 启航")
        col = C_CREAM if pyxel.frame_count % 30 < 20 else C_WHITE  # 周期性提亮
        txt(bx + (bw - font().text_width(s)) // 2, by + 2, s, col)


# ==================== 航行指南（开局玩法速览，每次开始先看一眼） ====================
GUIDE_LINES = (                                    # (文案, 是否白字强调)；宽度均实测 ≤216px
    ("目标：跳到 x>42 的兴趣点即可逃离", True),     # 首行白字点题
    ("移动：上下选目标，回车跳迁，距离有限", False),
    ("星球=跳板  敌人=战斗  升级=强化", False),
    ("战斗：引擎每回合掷出出力 N", False),
    ("N≤0 为故障，按 1/2/3 任意键跳过", False),    # 与战斗页故障警示条呼应
    ("1 攻击  2 防御  3 蓄力", False),
    ("Q/W/E/R 主动技能，消耗备用能量", False),
    ("敌人越远越强，其坐标决定数值", False),
    ("升级：移动力 / 引擎 / 子系统强化", False),
    ("无可达目标时燃料耗尽，任务失败", False),
)


class GuideScene:
    """航行指南场景：每次开局（菜单确认引擎后）先展示十行玩法速览，回车启航。"""

    def __init__(self, app):
        """进入指南页（纯展示，无内部状态）。"""
        self.app = app

    def update(self):
        """指南输入：TAB 切语言；回车确认启航（确认音），淡入淡出进入地图。"""
        global LANG                                  # 与菜单同一会话级语言开关
        if pyxel.btnp(pyxel.KEY_TAB):
            LANG = "en" if LANG == "zh" else "zh"
            play_sfx(SND_CURSOR)
        if pyxel.btnp(pyxel.KEY_RETURN):
            play_sfx(SND_CONFIRM)                    # 启航确认音
            self.app.change_scene("map", "fade")

    def draw(self):
        """绘制指南页（PC-98 窗，随 LANG 双语）：铭牌 + 十行速览 + 呼吸启航提示。"""
        ui_backdrop()                                    # 星尘背景
        ui_bezel()                                       # 屏幕外框
        ui_window(4, 6, WIN_W - 8, WIN_H - 12, tr("航行指南 GUIDE"))
        y = 16
        for line, bright in GUIDE_LINES:                 # 首行白字点题，正文灰
            txt(12, y, tr(line), C_WHITE if bright else C_GREY)
            y += 12
        col = C_CREAM if pyxel.frame_count % 30 < 20 else C_WHITE   # 启航提示呼吸
        txt_center(140, tr("回车 · 启航"), col)


class MapScene:
    """地图场景：滚动星图 + 跳迁两段动画（飞船残影飞行 -> 摄像机平滑跟随）+ 落点分流。"""

    def __init__(self, app):
        """进入地图：选中下标归零并把摄像机对准飞船。"""
        self.app = app
        self.sel_idx = 0        # 当前选中的可达目标下标
        self.cam_x = 0.0        # 摄像机左上角（世界像素）
        self.cam_y = 0.0
        self.jump = None        # 进行中的跳迁飞行（dict，见 start_jump；None=待命）
        self.cam_anim = None    # 摄像机平滑跟随动画（dict，见 start_cam；None=已就位）
        self.pending = None     # 落地待结算的目标 (类型, x, y)（摄像机走完后分流）
        self.dust = []          # 落地扬尘粒子（世界像素坐标，见 spawn_dust）
        self.update_camera()    # 立即对准飞船，避免第一帧跳变

    # ---- 坐标与摄像机 ----
    def w2s(self, wx, wy):
        """世界坐标(cm) -> 屏幕坐标(px)。y 轴世界向上、屏幕向下，故翻转。"""
        return (int(wx * CM_TO_PX - self.cam_x),              # x：减摄像机偏移
                int(wy * CM_TO_PX + Y_OFFSET_PX - self.cam_y))  # y：+基线-偏移

    def camera_bounds(self):
        """按实际点云外扩一圈计算摄像机可滚范围——边界兴趣点也能完整入镜。"""
        m = 14  # 外扩边距(px)：兴趣点图形半径 4 + 选中圈 7，再留呼吸余量
        xs = [x * CM_TO_PX for _, x, _ in self.app.world.points]
        ys = [y * CM_TO_PX + Y_OFFSET_PX for _, _, y in self.app.world.points]
        return (min(xs) - m, max(xs) + m - WIN_W,              # x 可滚范围
                min(ys) - m, max(ys) + m - WIN_H)              # y 可滚范围

    def camera_target(self):
        """摄像机期望位置：飞船锚定屏幕 x=SHIP_ANCHOR_X、纵向居中，并夹取界内。"""
        ship = self.app.ship
        tx = ship.x * CM_TO_PX - SHIP_ANCHOR_X                 # 锚点：正中偏左 15px
        ty = ship.y * CM_TO_PX + Y_OFFSET_PX - WIN_H / 2       # 纵向居中
        x0, x1, y0, y1 = self.camera_bounds()
        if x0 > x1:                                            # 世界比窗口窄：居中
            tx = (x0 + x1) / 2
        else:
            tx = max(x0, min(tx, x1))                          # 常规：夹取在界内
        if y0 > y1:
            ty = (y0 + y1) / 2
        else:
            ty = max(y0, min(ty, y1))
        return tx, ty

    def update_camera(self):
        """摄像机就位：无平滑动画时直接贴住目标（跳迁落地后由动画接管）。"""
        if self.cam_anim is not None:
            return                       # 平滑跟随进行中，不越权瞬移
        self.cam_x, self.cam_y = self.camera_target()

    def reachable_targets(self):
        """取当前可达目标列表（每帧重算：移动/移动力的函数）。"""
        return self.app.ship.reachable(self.app.world.points)

    # ---- 跳迁两段动画：先后坐蓄力，再飞行，后摄像机跟随 ----
    def start_jump(self, target):
        """下达跳迁指令：起跳音 + 先播飞船缓动飞行（带残影），逻辑落子推迟到落地。"""
        ship = self.app.ship
        play_sfx(SND_JUMP)                            # 起跳引擎音（资产版出声）
        self.jump = {"to": target, "t": 0,
                     "from": (ship.x, ship.y),   # 起点（cm）
                     "pos": (ship.x, ship.y),    # 当前插值位置（cm），供 draw 使用
                     "trail": []}                # 历史位置记录（残影取样点）

    def step_jump(self):
        """推进跳迁第一段：先后坐 2 帧（anticipation 蓄力），再 ease-out 飞行至落地。"""
        j = self.jump
        j["t"] += 1
        pre_f = JUICE["jump"]["pre_f"] if JUICE["enabled"] else 0   # 关 juice 时无后坐
        ship_f = JUICE["jump"]["ship_f"]
        fx, fy = j["from"]
        tx, ty = j["to"][1], j["to"][2]
        if j["t"] <= pre_f:                       # 起跳前：沿反方向后坐 1px（蓄力感）
            d = math.hypot(tx - fx, ty - fy) or 1.0
            j["pos"] = (fx - (tx - fx) / d, fy - (ty - fy) / d)
        else:                                     # 飞行：ease-out 直线插值（起步快收尾缓）
            e = ease_out_cubic(min(1.0, (j["t"] - pre_f) / ship_f))
            j["pos"] = (fx + (tx - fx) * e, fy + (ty - fy) * e)
        j["trail"].append(j["pos"])               # 记录轨迹供残影绘制
        if j["t"] >= pre_f + ship_f:              # 落地：落子 + 扬尘 + 落地音 + 镜头跟随
            global SEED_USED
            if SEED_USED != SEED_NOW:             # 首次落子：标记本局种子已启用
                SEED_USED = SEED_NOW
            self.app.ship.move_to(tx, ty)         # 移动并标记已探索
            self.spawn_dust(tx, ty)               # 落地扬尘（与落地音同拍）
            play_sfx(SND_LAND)
            self.jump = None
            self.pending = j["to"]                # 摄像机走完后结算落点
            self.start_cam()

    def spawn_dust(self, wx, wy):
        """落地扬尘：落点两侧弹起数粒 1px 尘埃（世界像素坐标，随摄像机移动）。"""
        if not JUICE["enabled"]:
            return
        px, py = wx * CM_TO_PX, wy * CM_TO_PX + Y_OFFSET_PX    # 转世界像素
        for i in range(JUICE["jump"]["dust_n"]):
            self.dust.append({"x": px, "y": py + 2,
                              "vx": 0.8 if i % 2 == 0 else -0.8,   # 左右交替弹开
                              "vy": -0.4 - 0.3 * (i % 2),          # 高度略有差异
                              "age": 0})

    def tick_dust(self):
        """推进落地尘埃（位置更新 + 4 帧寿命过滤）。"""
        for d in self.dust:
            d["x"] += d["vx"]
            d["y"] += d["vy"]
            d["age"] += 1
        self.dust = [d for d in self.dust if d["age"] < 4]

    def start_cam(self):
        """落地后启动摄像机平滑跟随：从当前位置缓动到新锚点（不瞬移）。"""
        tx, ty = self.camera_target()
        self.cam_anim = {"from": (self.cam_x, self.cam_y), "to": (tx, ty), "t": 0}

    def step_cam(self):
        """推进摄像机跟随：ease-out 缓动两轴同步，走完即贴准目标并结算落点。"""
        a = self.cam_anim
        a["t"] += 1
        e = ease_out_cubic(min(1.0, a["t"] / JUICE["jump"]["cam_f"]))
        fx, fy = a["from"]
        tx, ty = a["to"]
        self.cam_x = fx + (tx - fx) * e         # 两轴同步缓动
        self.cam_y = fy + (ty - fy) * e
        if a["t"] >= JUICE["jump"]["cam_f"]:    # 走完：贴准目标并结算落点
            self.cam_x, self.cam_y = tx, ty
            self.cam_anim = None
            if self.pending is not None:
                t = self.pending                # (类型, x, y)
                self.pending = None
                self.resolve_landing(t)

    def resolve_landing(self, t):
        """落点结算：按类型分流——逃离成功/开战斗（警报+白闪+光圈）/升级（淡入淡出）。"""
        if t[1] > ESCAPE_X:                     # 落点 x>42：逃离成功
            self.app.ending_win = True
            self.app.change_scene("ending")
        elif t[0] == "敌人":                    # 踩敌人：警报音 + 白闪两下+光圈开合
            play_sfx(SND_ALARM)
            self.app.fight = Fight(self.app.ship, t[1])
            self.app.change_scene("fight", "battle")
        elif t[0] == "升级":                    # 踩升级点：淡入淡出进升级选单
            self.app.change_scene("levelup", "fade")
        else:                                   # 普通星球：仅作中继跳板
            self.sel_idx = 0                    # 重置选中（返回地图后重选）

    def update(self):
        """地图输入：尘埃推进常开；跳迁/摄像机动画期间锁输入；待命时选目标跳迁。"""
        self.tick_dust()                            # 落地尘埃不受其它状态影响
        if self.jump is not None:               # 第一段：飞船飞行中
            self.step_jump()
            return
        if self.cam_anim is not None:           # 第二段：摄像机跟随中
            self.step_cam()
            return
        self.update_camera()                    # 待命：摄像机贴住飞船
        targets = self.reachable_targets()
        if not targets:                         # 移动距离内没有任何未探索点
            self.app.ending_win = False         # PDF：燃料耗尽 -> 游戏失败
            self.app.change_scene("ending")
            return
        self.sel_idx %= len(targets)            # 目标数量变化时收敛下标
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_LEFT):    # 上/左：上一个
            self.sel_idx = (self.sel_idx - 1) % len(targets)
            play_sfx(SND_CURSOR)
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_RIGHT):  # 下/右：下一个
            self.sel_idx = (self.sel_idx + 1) % len(targets)
            play_sfx(SND_CURSOR)
        if pyxel.btnp(pyxel.KEY_RETURN):        # 回车：下达跳迁（先动画后落子）
            self.start_jump(targets[self.sel_idx])

    def draw(self):
        """绘制星图（冷战磷光终端风）：星空背景、导航网格、雷达扫描、HUD 仪条。"""
        ship = self.app.ship
        pyxel.cls(C_BG)                                  # 黑底
        # 星空背景（2026-10-24 定稿：全屏扫描线取消，改 72 星三档亮度 + 呼吸闪烁）
        for i in range(72):                              # 确定性位置：每帧同一片星空
            sx, sy = (i * 97 + 5) % WIN_W, (i * 53 + 13) % WIN_H
            if 22 < sy < WIN_H - 22:                     # 避开上下 HUD 条区域
                if i % 11 == 0 and pyxel.frame_count % 30 >= 20:
                    continue                             # 每 11 颗取 1：灭相跳过=闪烁
                if i % 9 == 0:
                    col = C_TEAL                         # 稀疏青绿星（呼应磷光主色）
                elif i % 4 == 0:
                    col = C_GREY                         # 亮星
                else:
                    col = C_DIM                          # 暗星（占多数）
                pyxel.pset(sx, sy, col)
        # 1cm 间隔的导航网格（只画屏幕内的线，深灰低调不抢主体）
        cx0 = int(self.cam_x // CM_TO_PX)
        cx1 = int((self.cam_x + WIN_W) // CM_TO_PX) + 1
        for cx in range(cx0, cx1 + 1):
            sx = cx * CM_TO_PX - self.cam_x
            pyxel.line(sx, 0, sx, WIN_H, C_DIM)
        cy0 = int((self.cam_y - Y_OFFSET_PX) // CM_TO_PX) - 1
        cy1 = int((self.cam_y + WIN_H - Y_OFFSET_PX) // CM_TO_PX) + 1
        for cy in range(cy0, cy1 + 1):
            sy = cy * CM_TO_PX + Y_OFFSET_PX - self.cam_y
            pyxel.line(0, sy, WIN_W, sy, C_DIM)
        # x 轴本体（世界 y=0 那条横线，磷光青绿）
        _, sy0 = self.w2s(0, 0)
        pyxel.line(0, sy0, WIN_W, sy0, C_TEAL)
        # 逃生边界 x=42：右侧青绿虚线 + 标注（虚线=6px 周期逐段画）
        sx42, _ = self.w2s(ESCAPE_X, 0)
        if 0 <= sx42 < WIN_W:
            for yy in range(22, WIN_H - 22, 6):
                pyxel.rect(sx42, yy, 1, 3, C_TEAL)
            txt(min(sx42 + 3, WIN_W - 80), 24, tr("逃离线 x>42"), C_TEAL)
        # 兴趣点：已探索画岩青暗点（不动）；未探索画类型图形并按类型相位悬浮
        targets = self.reachable_targets()
        sel = targets[self.sel_idx % len(targets)] if targets else None
        float_a = JUICE["map"]["float_a"] if JUICE["enabled"] else 0
        phase = {"星球": 0, "敌人": 20, "升级": 40}    # 分相位：三类点不同步浮动
        for t, x, y in self.app.world.points:
            sx, sy = self.w2s(x, y)
            if (x, y) in ship.visited:
                pyxel.circ(sx, sy, 2, C_SLATE)           # 已探索：暗色小圆
            else:
                sy -= round(math.sin((pyxel.frame_count + phase[t]) * 0.08) * float_a)
                draw_sprite(sx, sy, SPR_OF[t])
        if (sel is not None and self.cam_anim is None    # 摄像机跟随中不画
                and pyxel.frame_count % 30 < 20):        # 选中目标：角括号准星
            sx, sy = self.w2s(sel[1], sel[2])
            ui_corners(sx - 6, sy - 6, 12, 12, 3, C_WHITE)
        if self.jump is not None:                        # 飞行中：残影+插值船（雷达跟随）
            trail = self.jump["trail"]
            for lag, col in ((8, C_DIM), (4, C_SLATE)):  # 两级残影：越旧越暗
                if len(trail) > lag:
                    sx, sy = self.w2s(*trail[-lag - 1])
                    pyxel.pal(C_WHITE, col)              # 白色船体临时重映射=渐隐
                    draw_sprite(sx, sy, SPR_SHIP)
                    pyxel.pal()                          # 复位调色板映射
            sx, sy = self.w2s(*self.jump["pos"])
            draw_sprite(sx, sy, SPR_SHIP)                # 飞行中的船本体
        else:                                            # 待命/跟随中：锚定飞船本体
            sx, sy = self.w2s(ship.x, ship.y)
            ship.draw(self.cam_x, self.cam_y)            # 船体+尾焰
        # 冷战雷达扫描：绕船旋转的扫描线（两级尾迹）+ 距离圈（任何相位都跟随船）
        a = math.radians(pyxel.frame_count % 120 * 3)    # 120 帧一圈（4s）
        for k, col in ((0, C_TEAL), (1, C_SLATE), (2, C_DIM)):
            aa = a - k * 0.1                             # 尾迹相位滞后
            pyxel.line(sx, sy, int(sx + math.cos(aa) * 48),
                       int(sy + math.sin(aa) * 48), col)
        pyxel.circb(sx, sy, 48, C_SLATE)                 # 扫描距离圈
        for d in self.dust:                              # 落地扬尘（世界像素 -> 屏幕）
            pyxel.pset(int(d["x"] - self.cam_x), int(d["y"] - self.cam_y), C_SLATE)
        # 顶部 HUD 仪条：黑底线框 + 血量表(危险闪烁) + 盾/能/航程/引擎数值
        pyxel.rect(3, 3, WIN_W - 6, 17, C_BG)            # 黑底压住网格保证可读
        pyxel.rectb(3, 3, WIN_W - 6, 17, C_DIM)          # 线框（终端风：不铺实底）
        ui_corners(2, 2, WIN_W - 4, 19, 2, C_SLATE)      # 四角刻度
        hx = 8                                            # 光标式排布：宽度自适应不重叠
        lab = {"血": "HP", "盾": "SH", "能": "NR"}        # HUD 标签双语（两字母宽度安全）
        txt(hx, 7, lab["血"] if LANG == "en" else "血", C_SLATE)
        ui_gauge(hx + 14, 11, 16, max(0, ship.hp) / PLAYER_HP,
                 C_TEAL, crit=ship.hp <= 2)              # 低血：整条闪烁告警
        hx += 14 + 18
        vals = ([str(max(0, ship.hp)), f"{lab['盾']}{ship.shield}",
                 f"{lab['能']}{ship.energy}", f"RG{ship.max_move_dis:.1f}"]
                if LANG == "en" else
                [str(max(0, ship.hp)), f"盾{ship.shield}", f"能{ship.energy}",
                 f"航{ship.max_move_dis:.1f}"])
        for s in vals:
            txt(hx, 7, s, C_WHITE)                       # 精确数值（能量驱动技能消耗）
            hx += font().text_width(s) + 8
        txt(hx, 7, tr_name(ship.engine.name, ENGINE_EN), C_TEAL)   # 引擎名（磷光收尾）
        # 底部信息条：选中目标详情 + 跳跃提示
        if sel is not None:
            d = math.hypot(sel[1] - ship.x, sel[2] - ship.y)   # 到目标的距离(cm)
            pyxel.rect(3, WIN_H - 20, WIN_W - 6, 17, C_BG)
            pyxel.rectb(3, WIN_H - 20, WIN_W - 6, 17, C_DIM)
            ui_corners(2, WIN_H - 21, WIN_W - 4, 19, 2, C_SLATE)
            name = tr_name(sel[0], POI_EN)               # 兴趣点类型显示名
            if LANG == "en":                             # 英文更窄：去"距/cm"字样
                txt(9, WIN_H - 15, f"{name}({sel[1]},{sel[2]}) {d:.1f}", C_WHITE)
            else:
                txt(9, WIN_H - 15, f"{name}({sel[1]},{sel[2]}) 距{d:.1f}cm", C_WHITE)
            hint = tr("回车 跳跃")
            hint_col = C_WHITE if pyxel.frame_count % 30 < 20 else C_SLATE
            txt(WIN_W - 9 - font().text_width(hint), WIN_H - 15, hint, hint_col)


class FightScene:
    """战斗场景：按键翻译成 Fight 调用；附引擎函数图像、顿帧、技能横幅、红闪等表现。"""

    SND_OF_EVENT = {"ship_hit": SND_HIT,     # 事件标签 -> 音效槽位
                    "kill": SND_KILL,
                    "win": SND_WIN,
                    "lose": SND_LOSE,
                    "fault": SND_FAULT}      # 故障判定瞬间即响（时机修正）

    def __init__(self, app):
        """进入战斗：掷第 1 回合出力，并复位全部动画/juice 状态。"""
        self.app = app
        if app.fight.turn_no == 0:           # 刚建战的 Fight 还没开过回合
            app.fight.begin_turn()
        self.freeze = 0                      # 分配出力后的顿帧剩余帧数
        self.freeze_sys = None               # 顿帧期间高亮的子系统名
        self.banner = None                   # 技能名横幅 [文本, 已播帧数]
        self.red_flash = 0                   # 故障跳过的红闪剩余帧数
        self.over_t = 0                      # 战斗结束后帧计数（背景压暗渐入）
        self.trauma = 0.0                    # 震屏 trauma（game-feel 模型，见 draw）
        self.react = 0                       # 受击反应剩余帧（白闪+震屏+数字窗口）
        self.floaters = []                   # 上飘数字 [{t,x,y,age,col}]
        self.parts = []                      # 击杀粒子 [{x,y,vx,vy,age,col}]

    def update(self):
        """战斗主循环：顿帧→敌人回合→受击反应逐段锁输入；事件统一翻译成反馈。"""
        f = self.app.fight
        self.tick_fx()                               # 表现层计时（横幅/震屏/数字/粒子）
        if self.freeze > 0:                          # 分配顿帧：冻结后敌人才行动
            self.freeze -= 1
            if self.freeze == 0:
                f.enemy_turn()                       # 顿帧结束：敌人回合（over 则自空转）
            self.flush_events(f)
            return
        if self.react > 0:                           # 受击反应：把"瞬间挨打"拉长成过程
            self.react -= 1
            self.flush_events(f)
            return
        if self.red_flash > 0:                       # 故障红闪约 0.5s：锁输入
            self.red_flash -= 1
            self.flush_events(f)
            return
        if f.over:                                   # 战斗已出结果：背景渐暗 + 回车离开
            self.over_t += 1
            if pyxel.btnp(pyxel.KEY_RETURN):
                win = f.win
                # 注意：这里不再清空 app.fight——离场光圈期间本场景仍需绘制
                # （战斗对象由 start_run 开新局或 EndingScene 返回菜单时清理）
                if win:                              # 胜：光圈开合过场回地图
                    self.app.change_scene("map", "iris")
                else:                                # 败：光圈开合过场进结算
                    self.app.ending_win = False
                    self.app.change_scene("ending", "iris")
            self.flush_events(f)
            return
        self.handle_input(f)                         # 战斗中：技能/分配
        self.flush_events(f)

    def tick_fx(self):
        """推进纯表现层计时：技能横幅、trauma 衰减、数字上飘、粒子散开。"""
        if self.banner is not None:
            self.banner[1] += 1
            if self.banner[1] >= JUICE["fight"]["banner_f"]:
                self.banner = None
        self.trauma = max(0.0, self.trauma - JUICE["shake"]["decay"])   # 线性衰减必归零
        for n in self.floaters:                      # 数字：上飘 + sin 微漂（防叠字）
            n["y"] -= 0.5
            n["x"] += 0.3 * math.sin(n["age"] * 0.9)
            n["age"] += 1
        self.floaters = [n for n in self.floaters if n["age"] < JUICE["fight"]["num_f"]]
        for p in self.parts:                         # 粒子：四散 + 速度衰减
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vx"] *= 0.85
            p["vy"] *= 0.85
            p["age"] += 1
        self.parts = [p for p in self.parts if p["age"] < 6]

    def add_trauma(self, amount):
        """累加震屏 trauma（上限 1；实际位移 = trauma²，见 draw 的 sin 驱动）。"""
        self.trauma = min(1.0, self.trauma + amount)

    def spawn_num(self, text, x, y, col):
        """生成上飘数字（game-feel 配方：上升+渐隐+水平微漂）。"""
        self.floaters.append({"t": text, "x": x, "y": y, "age": 0, "col": col})

    def spawn_burst(self):
        """击杀粒子爆散：敌窗中心向各方向喷发红/橙交替粒子。"""
        n = JUICE["fight"]["kill_n"]
        for i in range(n):
            a = math.pi * 2 * i / n                  # 均匀角度分布
            sp = 1.2 + 0.5 * (i % 3)                 # 速度分档，爆散更自然
            self.parts.append({"x": 79, "y": 19, "vx": math.cos(a) * sp,
                               "vy": math.sin(a) * sp, "age": 0,
                               "col": C_RED if i % 2 else C_ORANGE})

    def handle_input(self, f):
        """战斗中的按键：Q/W/E/R 施放技能（触发横幅）；1/2/3 分配（触发顿帧+数字）。"""
        for key, name in zip((pyxel.KEY_Q, pyxel.KEY_W, pyxel.KEY_E, pyxel.KEY_R),
                             SKILL_KEYS_ORDER):      # 键位与技能一一对应
            if pyxel.btnp(key):
                f.msg = f.cast_skill(name)           # 成功 None / 失败返回原因
                if f.msg is None:
                    play_sfx(SND_ENERGY)             # 技能发动的通用音
                    self.banner = [name, 0]          # 技能名 16px 残影横幅起播
                return
        if not f.fault:                              # 正常回合：分配出力
            for key, system, snd in ((pyxel.KEY_1, "火炮", SND_CANNON),
                                     (pyxel.KEY_2, "护盾", SND_SHIELD),
                                     (pyxel.KEY_3, "能量", SND_ENERGY)):
                if pyxel.btnp(key):
                    f.msg = f.assign(system)         # 分配出力到子系统
                    if f.msg is None:
                        play_sfx(snd)
                        self.freeze = JUICE["fight"]["freeze_f"]     # 顿帧（关 juice 时仍留 1 帧
                        if not JUICE["enabled"]:                     # 推迟敌人回合，逻辑不变）
                            self.freeze = 1
                        self.freeze_sys = system
                        if system == "火炮" and f.last_dmg > 0:      # 命中数字（橙，敌窗侧）
                            self.spawn_num(f"伤{f.last_dmg}", 118, 22, C_ORANGE)
                        # 敌人回合推迟到顿帧结束（见 update 的 freeze 分支）
                    return
        else:                                        # 故障回合：1/2/3 = 跳过（防软锁）
            for key in (pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3):
                if pyxel.btnp(key):
                    f.msg = f.skip_fault_turn()      # 让过，敌人行动，进入下回合
                    if f.msg is None:
                        self.red_flash = JUICE["fight"]["red_f"]     # 红色淡入淡出约 0.5s
                        # 故障警报音效已前移到"判定瞬间"（fault 事件），此处不再播
                    return

    def flush_events(self, f):
        """事件标签 -> 音效 + juice 反馈（受击反应/震屏/数字/粒子），然后清空。"""
        for ev in f.events:
            play_sfx(self.SND_OF_EVENT[ev])          # 查表翻译成音效槽位
            if not JUICE["enabled"]:
                continue
            if ev == "ship_hit":                     # 受击：反应窗 + 震屏 + 红数字
                self.react = JUICE["fight"]["react_f"]
                self.add_trauma(JUICE["shake"]["hit"])
                self.spawn_num(f"-{f.last_hit}", 118, 44, C_RED)
            elif ev == "kill":                       # 击破：重震屏 + 敌窗粒子爆散
                self.add_trauma(JUICE["shake"]["kill"])
                self.spawn_burst()
        f.events.clear()

    # ---- 表现层绘制 ----
    def draw_banner(self):
        """技能名横幅：16px 大字从左向右横穿屏幕，身后拖两级色阶残影（随语言显示）。"""
        text, t = self.banner
        text = tr_name(text, SKILL_EN)                  # 技能逻辑名 -> 显示名
        w = font(16).text_width(text)                # 实测字宽决定行程
        span = WIN_W + 2 * w                         # 从完全进入 到 完全离场
        x = int(-w + span * t / JUICE["fight"]["banner_f"])   # 线性横穿屏幕
        for lag, col in ((10, C_DIM), (5, C_SLATE)): # 残影两级：越远越暗（先画压底）
            txt(x - lag, 70, text, col, big=True)
        txt(x, 70, text, C_CREAM, big=True)          # 本体奶油亮字

    def draw_engine_graph(self, f):
        """右上示波器窗：引擎出力 Ni 随回合 i 的曲线 + 当前回合白点标记。"""
        x0, y0, w, h = 158, 7, 78, 120               # ADV 小窗（利用右侧留白区）
        ui_window(x0, y0, w, h, tr("引擎 N-i"))
        px0, px1 = x0 + 7, x0 + w - 5                # 绘图区左右界（左侧留 0 线标注）
        py0, py1 = y0 + 12, y0 + h - 8               # 绘图区上下界
        ylo, yhi = -6.0, 14.0                        # 纵轴范围（超出截断，防爆值）
        for gx in range(px0, px1 + 1, 6):            # 示波器点阵网格（6px 步距）
            for gy in range(py0, py1 + 1, 6):
                pyxel.pset(gx, gy, C_DIM)
        zy = py1 - (0 - ylo) / (yhi - ylo) * (py1 - py0)   # N=0 零线的屏幕 y
        pyxel.dither(0.125)                          # 故障区：低密度红纱示意
        pyxel.rect(px0, int(zy) + 1, px1 - px0, int(py1 - zy), C_RED)
        pyxel.dither(1.0)
        for dx in range(px0, px1, 4):                # 零线：深灰虚线（其下即故障区）
            pyxel.rect(dx, int(zy), 2, 1, C_DIM)
        imax = max(16, f.turn_no + 2)                # 横轴至少 16 回合，随战斗延伸

        def pt(i, v):
            """(回合 i, 出力 v) -> 面板像素坐标（v 超出纵轴则截断到边）。"""
            sx = px0 + (i - 1) * (px1 - px0) / (imax - 1)
            sy = py1 - (min(max(v, ylo), yhi) - ylo) / (yhi - ylo) * (py1 - py0)
            return int(sx), int(sy)

        vals = f.player.engine.preview(imax)         # 预览序列（不推进引擎状态）
        prev = None
        for i, v in enumerate(vals, 1):              # 曲线：相邻点连线成函数图像
            cur = pt(i, v)
            if prev is not None:
                pyxel.line(prev[0], prev[1], cur[0], cur[1], C_ORANGE)
            prev = cur
        if f.turn_no >= 1:                           # 当前回合点：白点呼吸闪烁
            cx, cy = pt(f.turn_no, vals[f.turn_no - 1])
            if pyxel.frame_count % 10 < 6:
                pyxel.circb(cx, cy, 2, C_WHITE)      # 亮起相：空心圈
            else:
                pyxel.circ(cx, cy, 1, C_WHITE)       # 暗相：实心点
        txt(x0 + 5, y0 + h - 16, f"N={f.ni}", C_WHITE)   # 当前出力读数
        txt(x0 + 5, int(zy) + 2, "0", C_RED)             # 零线电平标注

    def draw(self):
        """绘制战斗界面：四窗+示波器（含 trauma 震屏），叠白闪/数字/粒子/横幅/结算。"""
        f = self.app.fight
        e = f.enemy
        ship = self.app.ship
        # ---- trauma 震屏：位移=trauma²（小伤微颤、重伤猛砸），sin 驱动非随机 ----
        amp = JUICE["shake"]["max_px"] * (0.4 if JUICE["reduce_shake"] else 1.0)
        shake = self.trauma ** 2 * amp if JUICE["enabled"] else 0.0
        pyxel.camera(round(math.sin(pyxel.frame_count * 1.9) * shake),
                     round(math.cos(pyxel.frame_count * 2.7) * shake))
        ui_backdrop()                                # 星尘背景
        ui_bezel(corners_only=True)                  # 密集场景：只画四角外框
        hi = self.freeze > 0 and pyxel.frame_count % 2 == 0   # 顿帧高亮闪烁相位
        # 敌舰窗（左列最上方，唯一带铭牌的面板）
        ui_window(4, 7, 150, 24, tr("敌舰 HOSTILE"))
        if hi and self.freeze_sys == "火炮":          # 受击闪白：白/橙快速交替
            ecol = C_WHITE if pyxel.frame_count % 4 < 2 else C_ORANGE
        else:
            ecol = C_RED
        if LANG == "en":                              # 敌行英文：HP/ATK/DEF 缩写
            etxt = f"HP{max(0, e.hp)}/{e.max_hp} ATK{e.atk} DEF{e.defence}"
        else:
            etxt = f"血{max(0, e.hp)}/{e.max_hp} 攻{e.atk} 防{e.defence}"
        txt(9, 15, etxt, ecol)                        # 铭牌已示身份
        # 本舰窗：数值行 + 内联三仪表（血量表低血闪烁）
        ui_window(4, 33, 150, 26, tr("本舰 SHIP"))
        scol = C_ORANGE if hi and self.freeze_sys in ("护盾", "能量") else C_WHITE
        if LANG == "en":                              # 本舰行英文：HP/SH/NRG 缩写
            stxt = f"HP{max(0, ship.hp)} SH{ship.shield} NR{ship.energy}"
        else:
            stxt = f"血{max(0, ship.hp)} 盾{ship.shield} 能{ship.energy}"
        txt(9, 36, stxt, scol)
        glab = ("H", "S", "E") if LANG == "en" else ("血", "盾", "能")   # 仪表单字标签
        txt(9, 48, glab[0], C_GREY)
        ui_gauge(21, 51, 21, max(0, ship.hp) / PLAYER_HP, C_WHITE, crit=ship.hp <= 2)
        txt(48, 48, glab[1], C_GREY); ui_gauge(60, 51, 21, min(ship.shield, 12) / 12, C_WHITE)
        txt(87, 48, glab[2], C_GREY); ui_gauge(99, 51, 21, min(ship.energy, 12) / 12, C_WHITE)
        txt(126, 48, "HP", C_DIM)
        # 记录窗：首行=回合状态（故障红底反白闪），其下流水（报错占末行）
        ui_window(4, 61, 150, 70)
        tl = (f"T{f.turn_no} N={f.ni}" + (" FAULT" if f.fault else "") if LANG == "en"
              else f"回合{f.turn_no} N={f.ni}" + ("【故障】" if f.fault else ""))
        if f.fault and pyxel.frame_count % 12 < 6:   # 故障警报：红底白字闪烁
            pyxel.rect(7, 64, 144, 11, C_RED)
            txt(9, 64, tl, C_WHITE)
        else:
            txt(9, 64, tl, C_RED if f.fault else C_WHITE)
        for dx in range(9, 149, 4):                  # 状态与流水的分隔虚线
            pyxel.rect(dx, 77, 2, 1, C_DIM)
        lines = f.log[-3:] if f.msg else f.log[-4:]  # 报错存在时流水让出一行
        y = 80
        for line in lines:                           # 战斗流水（tr_log 按语言重建）
            txt(9, y, tr_log(line), C_GREY)
            y += 12
        if f.msg:                                    # 最近一次非法操作的提示（红）
            txt(9, y, tr(f.msg), C_RED)
        # 操舵台窗：故障回合 1/2/3 均为"跳过"，换整幅警示条防误导；平时三指令钮
        ui_window(4, 133, WIN_W - 8, 25)
        if f.fault and not f.over:
            bw2 = WIN_W - 18                            # 整幅红色警示键帽
            pyxel.rectb(9, 137, bw2, 11, C_RED)
            s = tr("按 [1][2][3] 跳过故障回合")
            txt(9 + (bw2 - font().text_width(s)) // 2, 139, s, C_RED)
        else:
            btns = (("[1] Fire", "[2] Def", "[3] Pwr") if LANG == "en"
                    else ("[1] 火炮", "[2] 护盾", "[3] 能量"))
            for i, s in enumerate(btns):
                bx = 9 + i * 74                         # 键帽加宽到 70px 容纳英文
                pyxel.rectb(bx, 137, 70, 11, C_GREY)
                txt(bx + (70 - font().text_width(s)) // 2, 139, s, C_WHITE)
        skill_line = ("Q Over W Shield E Cal R Sup" if LANG == "en"
                      else "Q火力过载 W应急护盾 E校准 R抑制")
        txt(9, 148, skill_line, C_GREY)               # 技能行（故障时仍可用）
        self.draw_engine_graph(f)                    # 引擎示波器（右上小窗）
        pyxel.camera(0, 0)                           # 复位摄像机：遮罩/数字/粒子不抖
        # 受击白闪：反应窗前 3 帧本舰窗盖白纱（reduce_flash 减半覆盖）
        if self.react > JUICE["fight"]["react_f"] - 3:
            pyxel.dither(0.3 if JUICE["reduce_flash"] else 0.55)
            pyxel.rect(4, 33, 150, 26, C_WHITE)
            pyxel.dither(1.0)
        for n in self.floaters:                      # 伤害数字：前半原色后半灰=渐隐
            half = JUICE["fight"]["num_f"] // 2
            txt(int(n["x"]), int(n["y"]), n["t"],
                n["col"] if n["age"] < half else C_GREY)
        for p in self.parts:                         # 击杀粒子（红/橙交替）
            pyxel.pset(int(p["x"]), int(p["y"]), p["col"])
        if self.banner is not None:                  # 技能名横幅（横穿屏幕）
            self.draw_banner()
        if self.red_flash > 0:                       # 故障红闪：三角波淡入淡出
            p = self.red_flash / JUICE["fight"]["red_f"]   # 剩余比例 1 -> 0
            cover = 1.0 - abs(p - 0.5) * 2           # 三角波：0 -> 峰值 -> 0
            peak = 0.35 if JUICE["reduce_flash"] else 0.7  # 峰值覆盖（可减半）
            pyxel.dither(min(peak, cover * peak))    # 保持战报可读
            pyxel.rect(0, 0, WIN_W, WIN_H, C_RED)    # 红色抖动遮罩
            pyxel.dither(1.0)                        # 复位抖动设置
        if f.over:                                   # 结束：背景抖动压暗衬出胜负窗
            pyxel.dither(min(0.6, self.over_t * 0.05))
            pyxel.rect(0, 0, WIN_W, WIN_H, C_BG)
            pyxel.dither(1.0)
            ui_window(20, 58, 200, 42)               # 胜负小窗
            # 胜利横幅弹入：ease-out-back 过冲回弹（关 juice 时直接就位）
            pop = ease_out_back(min(1.0, self.over_t / 6)) if JUICE["enabled"] else 1.0
            yy = int(64 + (1.0 - pop) * 12)          # 从下方过头弹到目标位
            txt_center(yy, "胜利！" if f.win else "战败",
                       C_CREAM if f.win else C_RED, big=True)
            txt_center(84, "按回车继续", C_WHITE)


class LevelupScene:
    """升级场景：踩到升级点后从最多 9 个选项中挑一项（进出走淡入淡出过场）。"""

    def __init__(self, app):
        """进入升级选单：按飞船当前成长状态构建选项列表。"""
        self.app = app
        self.options = self.build_options()  # [(类别, 英文描述), ...]
        self.idx = 0                        # 一级选单光标
        self.sub = None                     # 二级子选单（None=未进入；AB/AC/BC 或三系统）
        self.sub_idx = 0                    # 二级选单光标

    def build_options(self):
        """构建当前可选列表：永久3 + 未得被动2 + 未满级主动4（上限3级）。

        每项为 (类别, 中文描述, 载荷)：载荷是直接可用的目标名/None，
        不再从显示文本反查（显示与逻辑解耦）。
        永久升级可无限叠加，因此列表永不为空；被动获得后消失、主动封顶后消失。
        """
        ship = self.app.ship
        opts = [
            ("sail", "远航升级：移动力+0.5cm", None),          # 永久：远航
            ("engine", "引擎改造：选2个参数×1.1", None),        # 永久：引擎改造（子选单）
            ("system", "强化子系统：分配时+2", None),           # 永久：子系统（子选单）
        ]
        if "半衰期循环" not in ship.passives:                   # 被动：各只能拿一次
            opts.append(("passive", "被动·半衰期：战后留一半能量", "半衰期循环"))
        if "能量回收" not in ship.passives:
            opts.append(("passive", "被动·回收：火炮伤害+2能量", "能量回收"))
        for s in SKILL_KEYS_ORDER:                             # 主动：未拥有或未满级
            lv = ship.skills.get(s, 0)
            if lv < 3:
                opts.append(("skill", f"技能·{s} → Lv{lv + 1}", s))
        return opts

    def after_apply(self):
        """应用任何升级后的统一出口：获得音 + 淡入淡出回地图（燃料耗尽由地图帧判定）。"""
        play_sfx(SND_GAIN)                           # 升级获得音（T2 反馈）
        self.app.change_scene("map", "fade")

    def update(self):
        """升级输入：一级选单上下/回车；二级子选单上下/回车/ESC 返回。"""
        if self.sub is None:                       # ---- 一级选单 ----
            n = len(self.options)
            if pyxel.btnp(pyxel.KEY_UP):
                self.idx = (self.idx - 1) % n
                play_sfx(SND_CURSOR)
            if pyxel.btnp(pyxel.KEY_DOWN):
                self.idx = (self.idx + 1) % n
                play_sfx(SND_CURSOR)
            if pyxel.btnp(pyxel.KEY_RETURN):
                kind, _, payload = self.options[self.idx]   # 载荷直接可用
                ship = self.app.ship
                if kind == "sail":                   # 远航：直接生效
                    ship.upgrade_sail()
                    self.after_apply()
                elif kind == "engine":               # 引擎改造：进子选单选参数对
                    self.sub = ["AB", "AC", "BC"]
                    self.sub_idx = 0
                elif kind == "system":               # 子系统升级：进子选单选系统
                    self.sub = list(SYS_LIST)
                    self.sub_idx = 0
                elif kind == "passive":              # 被动：载荷即技能名
                    ship.gain_passive(payload)
                    self.after_apply()
                else:                                # 主动：载荷即技能名
                    ship.gain_or_upgrade_skill(payload)
                    self.after_apply()
        else:                                       # ---- 二级子选单 ----
            n = len(self.sub)
            if pyxel.btnp(pyxel.KEY_UP):
                self.sub_idx = (self.sub_idx - 1) % n
                play_sfx(SND_CURSOR)
            if pyxel.btnp(pyxel.KEY_DOWN):
                self.sub_idx = (self.sub_idx + 1) % n
                play_sfx(SND_CURSOR)
            if pyxel.btnp(pyxel.KEY_ESCAPE):         # ESC：不升级，退回一级选单
                self.sub = None
            if pyxel.btnp(pyxel.KEY_RETURN):         # 回车：应用子选项
                chosen = self.sub[self.sub_idx]
                if chosen in ("AB", "AC", "BC"):     # 引擎参数对
                    self.app.ship.upgrade_engine(chosen)
                else:                                # 子系统名（中文键）
                    self.app.ship.upgrade_subsystem(chosen)
                self.after_apply()

    def draw(self):
        """绘制升级界面（PC-98 风，随 LANG 双语）：标题窗 + 选项窗（蓝底反白+类别色标）。"""
        ui_backdrop()                                    # 星尘背景
        ui_bezel()                                       # 屏幕外框
        ui_window(4, 6, WIN_W - 8, 16, tr("升级 UPGRADE"))   # 标题窗（铭牌嵌上边线）
        txt(11, 9, tr("升级"), C_WHITE)
        for dx in range(40, 86, 6):                      # 标题右侧短饰线
            pyxel.rect(dx, 14, 3, 1, C_DIM)
        hint = tr("上下选 回车确认")
        txt(WIN_W - 11 - font().text_width(hint), 9, hint, C_GREY)   # 操作提示靠右
        ui_window(4, 24, WIN_W - 8, 130)                 # 选项窗（占满余下高度）
        chip_of = {"sail": C_GREY, "engine": C_GREY, "system": C_GREY,   # 类别色标：
                   "passive": C_TEAL, "skill": C_ORANGE}                # 被动青/技能橙
        ship = self.app.ship
        if self.sub is None:                             # 一级选单列表
            for i, (kind, label, payload) in enumerate(self.options):
                if kind == "skill":                      # 技能项：按语言重建标签
                    lv = ship.skills.get(payload, 0) + 1
                    label = tr_skill_label(payload, lv)
                else:                                    # 其余项走通用对照表
                    label = tr(label)
                iy = 28 + i * 14                         # 9 项 × 14px 行距
                if i == self.idx:                        # 选中：蓝底反白 + 箭头
                    pyxel.rect(6, iy - 1, WIN_W - 12, 13, C_BLUE)
                    txt(12, iy, "▸ " + label, C_WHITE)
                else:
                    txt(12, iy, "  " + label, C_GREY)    # 未选：灰字
                    pyxel.rect(WIN_W - 14, iy + 3, 5, 5, chip_of[kind])
        else:                                            # 二级子选单
            is_engine = self.sub[0] in ("AB", "AC", "BC")
            title = tr("引擎改造 · 选 ×1.1 参数" if is_engine else "强化子系统 · 选择目标")
            txt(12, 28, title, C_WHITE)
            pname = (PARAM_EN if LANG == "en"             # 参数含义名按语言取表
                     else PARAM_NAME)[ship.engine.name]
            for i, chosen in enumerate(self.sub):
                iy = 46 + i * 17
                if is_engine:                            # 引擎参数对：含义标签防天书
                    label = chosen[0] + pname[chosen[0]] + "+" + chosen[1] + pname[chosen[1]]
                elif LANG == "en":                       # 子系统：英文缩写显示
                    label = SYS_EN.get(chosen, chosen)
                else:                                    # 子系统：中文名直显
                    label = chosen
                if i == self.sub_idx:
                    pyxel.rect(8, iy - 1, 120, 13, C_BLUE)
                    txt(14, iy, "▸ " + label, C_WHITE)
                else:
                    txt(14, iy, "  " + label, C_GREY)
            txt(12, 118, tr("二级选项应用后返回地图"), C_GREY)
            txt(12, 134, tr("上下选 回车确认 ESC返回"), C_GREY)


class EndingScene:
    """结算场景：展示逃离成功/游戏失败，回车返回菜单。"""

    def __init__(self, app):
        """进入结算（胜负已在 app.ending_win 上）。"""
        self.app = app

    def update(self):
        """结算输入：回车清空本局状态并淡入返回菜单。"""
        if pyxel.btnp(pyxel.KEY_RETURN):
            self.app.ship = None            # 清空对局（下次开局重建）
            self.app.world = None
            self.app.fight = None
            self.app.change_scene("menu", "fade")   # 淡入淡出回菜单

    def draw(self):
        """绘制结算画面（PC-98 风，随 LANG 双语）：中央任务铭牌窗 + 底部任务状态条。"""
        ui_backdrop()                                    # 星尘背景
        ui_bezel()                                       # 屏幕外框
        px, py, pw, ph = 22, 38, 196, 72                 # 中央铭牌窗
        ui_window(px, py, pw, ph)
        ui_corners(px + 3, py + 3, pw - 6, ph - 6, 4, C_ORANGE)   # 铭牌角饰
        if self.app.ending_win:                          # 胜：奶油亮字
            txt_center(py + 8, tr("逃离成功！"), C_CREAM, big=True)
        else:                                            # 败：红字
            txt_center(py + 8, tr("游戏结束"), C_RED, big=True)
        for dx in range(px + 32, px + pw - 32, 6):       # 标题下分隔虚线
            pyxel.rect(dx, py + 28, 3, 1, C_DIM)
        sub = (tr("能源耗尽 · 任务中止") if not self.app.ending_win
               else tr("航程 x>42 · 任务日志已归档"))     # 副题按胜负区分
        txt_center(py + 34, sub, C_GREY)
        if pyxel.frame_count % 30 < 20:                  # 返回提示呼吸闪烁
            txt_center(py + 50, tr("按回车返回菜单"), C_WHITE)
        ui_window(4, WIN_H - 19, WIN_W - 8, 15)          # 底部任务状态条
        txt(10, WIN_H - 15, "STAR VOYAGE", C_DIM)        # （中英通用）
        dl = "MISSION COMPLETE" if self.app.ending_win else "MISSION FAILED"
        txt(WIN_W - 10 - font().text_width(dl), WIN_H - 15, dl,
            C_ORANGE if self.app.ending_win else C_RED)


# ==================== 应用 ====================
# 场景名 -> 场景类（change_scene 据此实例化；App 其余时刻不关心具体场景）
SCENES = {"menu": MenuScene, "guide": GuideScene, "map": MapScene, "fight": FightScene,
          "levelup": LevelupScene, "ending": EndingScene}

# 场景名 -> 背景音乐槽（分场景 BGM；指南沿用菜单曲、升级沿用地图曲）
BGM_OF_SCENE = {"menu": MUSIC_MENU, "guide": MUSIC_MENU, "map": MUSIC_MAP,
                "fight": MUSIC_FIGHT, "levelup": MUSIC_MAP, "ending": MUSIC_END}


class App:
    """应用外壳：初始化 pyxel、加载资产、按名切换场景（可带过场动画）。

    官方示例惯例：pyxel.run(App.update, App.draw)，具体逻辑全在当前场景对象里。
    过场状态机：out 段（旧场景渐隐/光圈收/白闪）-> 场景切换 -> in 段（新场景渐显/
    光圈开），期间输入锁定；转场类型由 change_scene 的 trans 参数指定。
    """

    def __init__(self):
        """初始化窗口与调色板与资产，菜单淡入开场，交出主循环控制权。"""
        pyxel.init(WIN_W, WIN_H, title="Star Voyage")  # 240x160@30fps，ESC 可退
        apply_palette()                                # 换装 YU-NO(PC-98) 十六色板
        load_assets()                                  # 白盒=空操作；资产=载包放BGM
        self.ship = None            # 本局飞船（开局时创建）
        self.world = None           # 本局星图
        self.fight = None           # 进行中的战斗（仅战斗场景非 None）
        self.ending_win = False     # 结算画面的胜负
        self.scene = None           # 当前场景对象（鸭子类型：有 update/draw 即可）
        self._trans = None          # 进行中的过场（None=无；dict: kind/phase/t/next）
        self.change_scene("menu")   # 从菜单开始
        self._trans = {"kind": "fade", "phase": "in", "t": 0, "next": None}  # 开场淡入
        pyxel.run(self.update, self.draw)  # 阻塞主循环（逐帧回调下面两个方法）

    def change_scene(self, name, trans=None):
        """切换场景：按 SCENES 表重新实例化（每个场景进场状态自复位），并切换 BGM。

        trans=None（或 juice 总开关关闭）立即切换；否则先播过场收段，遮蔽满时换
        场景，再播放段。trans 取值："fade" / "iris" / "battle"（白闪两下+光圈开合）。
        """
        if trans is None or not JUICE["enabled"]:
            self.scene = SCENES[name](self)
            play_bgm(BGM_OF_SCENE.get(name, MUSIC_MENU))   # 分场景 BGM
            return
        self._trans = {"kind": trans, "phase": "out", "t": 0, "next": name}

    def start_run(self, seed, engine_name):
        """开新局：写全局种子、生成星图与飞船，淡入淡出进入地图。"""
        global SEED_NOW, SEED_USED
        SEED_NOW = seed              # 本局个人种子（星图由此确定）
        SEED_USED = 0                # 尚未落子（首次移动时对齐 SEED_NOW）
        self.world = StarMap(SEED_NOW)          # 种子 -> 42 个兴趣点
        self.ship = Ship(engine_name)           # 选定引擎的飞船，原点出发
        self.fight = None
        self.change_scene("guide", "fade")      # 菜单 -> 指南（玩法速览）-> 地图

    def update(self):
        """每帧逻辑更新：过场期间推进过场并锁输入，否则转发给当前场景。"""
        if self._trans is not None:
            self._step_trans()
            return
        self.scene.update()

    def _trans_len(self, kind, phase):
        """过场各阶段帧长（读 JUICE.trans）：battle 收段=白闪+光圈收；fade/iris 等长。"""
        t = JUICE["trans"]
        if kind == "fade":
            return t["fade_f"]
        if kind == "iris":
            return t["iris_f"]
        return t["flash_f"] + t["iris_f"] if phase == "out" else t["iris_f"]

    def _step_trans(self):
        """推进过场状态机：收段结束即换场景转入放段；放段结束恢复交互。"""
        tr = self._trans
        tr["t"] += 1
        if tr["t"] >= self._trans_len(tr["kind"], tr["phase"]):
            if tr["phase"] == "out":             # 遮蔽满点：真正实例化下一个场景
                self.scene = SCENES[tr["next"]](self)
                play_bgm(BGM_OF_SCENE.get(tr["next"], MUSIC_MENU))   # 分场景 BGM
                tr["phase"], tr["t"] = "in", 0
            else:                                # 放段播完：过场结束
                self._trans = None

    def draw(self):
        """每帧绘制：清屏复位摄像机后转发给当前场景，最后叠加过场遮罩。"""
        pyxel.cls(0)                 # 黑底清屏
        pyxel.camera(0, 0)           # 复位摄像机（战斗页震屏会改偏移，全局兜底）
        self.scene.draw()
        if self._trans is not None:
            self._draw_trans()

    def _draw_trans(self):
        """把过场遮罩画在画面之上：fade=抖动黑幕；iris/battle=圆外黑幕（含白闪）。"""
        tr = self._trans
        kind, phase, t = tr["kind"], tr["phase"], tr["t"]
        flash_f = JUICE["trans"]["flash_f"]
        if kind == "battle" and phase == "out" and t < flash_f:
            if (t // 2) % 2 == 0:                 # 白闪两下：亮 2 帧/灭 2 帧交替
                pyxel.rect(0, 0, WIN_W, WIN_H, C_WHITE)
            return
        if kind == "battle" and phase == "out":   # 白闪之后进入光圈收段
            t -= flash_f
        total = self._trans_len(kind, phase)
        if kind == "battle" and phase == "out":   # 分母同样要剥掉白闪段：
            total -= flash_f                      # 光圈段进度 = 段内 t / 段长
        prog = min(1.0, t / max(1, total - 1))    # 段内进度 0..1
        cover = prog if phase == "out" else 1.0 - prog   # 收段渐浓 / 放段渐散
        if kind == "fade":
            pyxel.dither(cover)                   # cover 比例像素涂黑=抖动渐变
            pyxel.rect(0, 0, WIN_W, WIN_H, 0)
            pyxel.dither(1.0)                     # 复位抖动设置
        else:                                     # iris / battle 的光圈段
            self._draw_iris(cover)

    def _draw_iris(self, cover):
        """光圈遮罩：cover=0 全开、1 全黑；圆外区域逐行涂黑（无椭圆填充图元）。"""
        r = math.hypot(WIN_W / 2, WIN_H / 2) * (1.0 - cover)  # 当前光圈半径
        cx, cy = WIN_W // 2, WIN_H // 2
        for sy in range(WIN_H):                   # 逐行求行圆交点，圆外涂黑
            dy = abs(sy - cy)
            if dy >= r:                           # 整行都在圆外
                pyxel.rect(0, sy, WIN_W, 1, 0)
                continue
            hw = int(math.sqrt(r * r - dy * dy))  # 行与圆相交的半宽
            if cx - hw > 0:                       # 行左侧圆外段
                pyxel.rect(0, sy, cx - hw, 1, 0)
            xr = cx + hw + 1
            if xr < WIN_W:                        # 行右侧圆外段
                pyxel.rect(xr, sy, WIN_W - xr, 1, 0)


if __name__ == "__main__":           # 直接运行才启动（import 时不开窗，供 pytest）
    App()
