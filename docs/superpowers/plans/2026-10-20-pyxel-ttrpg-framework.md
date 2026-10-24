# Pyxel TTRPG 实现方案 v2 —— Star Voyage（新建 star_voyage.py）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **v2 修订说明**（相对 v1）：①不修改 `demo.py`，全部实现放进**新建**的 `star_voyage.py`，demo.py 冻结为只读参考骨架；②类设计改为官方示例 10_platformer 的 **update/draw 鸭子类型惯例**；③新增 Task 7 用 pyxel 自身 **headless 生成可编辑资产包 .pyxres**；④所有运行/交互验证改为基于 **pyxel-mcp**（kitao 官方 MCP server）；⑤附录 A 新增原骨架 20 项问题清单。
>
> **v3 修订说明（2026-10-20 当日执行纪要）**：①pyxel-mcp 已**项目级**安装：`E:\Pyxel项目\.venv`（uv，pyxel 锁 2.9.9），工作区注册于 `.zcode/config.json`（服务器名 `pyxel`，指向 `.venv/Scripts/pyxel-mcp.exe`）——**需重启 ZCode 会话后工具生效**；②**git 按用户要求暂不初始化**，本方案所有"提交"步骤取消，由用户后续自行启动；③实现落地为**两个版本**：`star_voyage.py`（无资产纯白盒，唯一手写源）与 `star_voyage_assets.py`（带资产，由 `tools/sync_versions.py` 从白盒版机械生成，差异仅文件头版本行+资产层区块，diff 可核）；④注释规范：每个类/函数均有中文 docstring，公式/结算/场景切换等关键行逐行注释；⑤Task 2~8 已于本会话内联完成：`test_star_voyage.py` 双版本参数化 **72 用例全过**（含故障回合软锁回归），资产包已生成（make_assets 双自检通过），两版 ×5 场景 headless update+draw 冒烟通过；⑥**Task 9~12 MCP 交互验收已完成**，见下方"v4 验收记录"。

> **v4 验收记录（pyxel-mcp 驱动，证据在 `runs/`）**：
> - **输入语义**：`run` 的按键事件是"替换按住集合"，连续同键只算一次 btnp——时间表必须"按下(F)+释放(F+2)"成对（`tools/mcp_driver_*.py` 为驱动器范本）。
> - **胜利局**：定时按键 110 事件 / 833 帧完整通关（含一场跨敌人格战斗、9 次升级确认），`until="ending_win"` 于 832 帧精确触发；终态 `ship=(46,49) hp=7 move=9.5 ending_win=true` 与离线 DFS+战斗模拟预测逐项一致；关键帧像素断言全过（菜单/地图/战斗/ESCAPE SUCCESS 结算）。
> - **战败局**：规划"零伤害送死路"（xe=37 敌 DEF=9≥火炮上限，2 键阵亡），YOU LOSE→GAME OVER→回菜单，像素断言全过。
> - **两版一致性机器证据**：同种子同操作的白盒/资产版地图帧 `diff_frames` 仅差 427/38400 像素（1.1%），差异区域避开 HUD——坐实"唯一区别是资产层"。
> - **资产核验**：`read_image` 精灵条色量分布与四个精灵设计吻合；`read_audio` 渲染胜利音 0.75s/6 音符/非静音。
> - **发现并处置两处真实问题**：①种子 42 存在 2 处坐标碰撞（(6,9)、(16,19)：敌人与升级点四舍五入同格）——游戏按点表顺序**敌人优先占格**（升级点被吸收，同格视为敌人点），此语义为实现决定，PDF 未规定，已记录；②**故障回合软锁 bug**（故障回合无可解技能则无法结束回合）——已修复：`Fight.skip_fault_turn()` + 场景把 1/2/3 翻译为跳过，回归测试覆盖。

**目标：** 在新文件 `star_voyage.py` 中完整实现《游戏设计文档.pdf》的一局游戏：选种子/引擎 → 星图逐点移动 → 战斗/升级 → 逃离成功或失败结算；美术与音效以 `assets/star_voyage.pyxres` 资产包承载。

**架构：** 场景与实体类遵循 pyxel 官方示例惯例——每个被主循环驱动的类都有 `update()`/`draw()`，`App` 只持有当前场景对象并转发（鸭子类型）；纯计算核心（引擎公式、星图生成、战斗结算）保持不依赖 pyxel，以便 pytest 覆盖。美术/音效/音乐全部进 .pyxres 资产包，由 `tools/make_assets.py` 以 pyxel API 程序化生成（源头是脚本，可反复再生），游戏运行时 `pyxel.load()` 加载、`pyxel.blt()`/`pyxel.play()` 使用，并随时可用 `pyxel edit` 人工润色。

**技术栈：** Python 3.12.4、pyxel 2.9.9、pytest、pyxel-mcp（运行/验收）、uv 0.8.11（已装）。

---

## 0. 已验证的环境事实（执行前必读，全部实测）

- **pyxel 自带官方示例**：`C:\Python312\Lib\site-packages\pyxel\examples\`（01~19、99，含 `assets/` 下多个 .pyxres）。惯例范本：`10_platformer.py`（实体类 + update/draw）、`02_jump_game.py`（App 类 + pyxres + playm）、`04_sound_api.py`（Sound 合成）。
- **`pyxel.text` 不支持中文**（实测渲染空白）：屏幕文案一律 ASCII；代码注释与逻辑分支用中文字符串（`"正弦波"` 等）不受影响。
- **资源包 API 实测可用**：模块级 `pyxel.load(filename, exclude_...)` / `pyxel.save(filename, exclude_...)` 专门负责 .pyxres；`pyxel.init(..., headless=True)` 可无窗口运行；`pyxel.images[n]`/`pyxel.sounds[n]`/`pyxel.musics[n]` 访问资源库，`Image.set/rect/circ/pset/cls` 均可在 headless 下绘图。**已完整跑通"绘制→save→load→回读"回路。**
- **按键常量**：`pyxel.KEY_RETURN` 存在，`KEY_ENTER` 不存在；方向键、`KEY_Q/W/E/R`、`KEY_0..9`、`KEY_BACKSPACE`、`KEY_ESCAPE` 均在。输入用 `pyxel.btnp`（按下沿），不要用无参 `pyxel.btn()`（任意键且每帧为真）。
- **`math.floor(-2.4) == -3`** 符合文档 ⌊⌋ 语义；`round()` 为银行家舍入（坐标恰 .5 概率忽略）。
- **pyxel-mcp**（pyxel 作者 kitao 出品，MIT）：PyPI 包名 `pyxel-mcp`，stdio 运行（`uvx pyxel-mcp` 或 `pip install pyxel-mcp`），要求 Python ≥3.11（本机 3.12.4 ✓）、pyxel ≥2.9.6（本机 2.9.9 ✓）。8 个工具：`validate`（静态校验）、`run`（headless 执行 + 定时按键 + 停止条件 + 截帧/状态快照）、`pyxel_info`、`read_palette`、`read_image`（读图像库/出 PNG）、`read_tilemap`、`read_audio`（渲染音效为 WAV 度量）、`diff_frames`（逐像素比较两帧）。注意：其脚本工具不沙箱化本地代码——只跑我们自己的代码，无碍。
- `python star_voyage.py` 会开窗阻塞：人工游玩用它；自动化验证一律走 pytest / py_compile / pyxel-mcp。

## 1. 设计决定（文档空白点的补全 + 用户已拍板事项，均可再推翻）

| # | 事项 | 决定 | 依据 |
|---|------|------|------|
| 1 | 文件 | **新建 `star_voyage.py`**，demo.py 一字不动 | 用户指定 |
| 2 | 交互验证 | 全部基于 pyxel-mcp（headless run + 截帧断言）；MCP 未就绪时回退 pytest + computer-use | 用户指定 |
| 3 | 资产 | `tools/make_assets.py` 程序化生成 `assets/star_voyage.pyxres`（可 `pyxel edit` 编辑）；脚本为源头，重跑会覆盖人工编辑 | 用户指定 + 官方示例资产方式 |
| 4 | 类设计 | 场景类（5 个）与飞船实体带 `update()`/`draw()`；纯计算类（Engine/StarMap/Enemy/Fight）不挂空壳 update/draw——与示例中 `get_tile/push_back` 等纯辅助一致 | 10_platformer 惯例的忠实解读 |
| 5 | 单位 | 1cm = 10px；摄像机跟随；世界 y 向上渲染翻转 | 视口 240×160 装不下 50cm+ 地图 |
| 6 | 坐标 | 按文档四舍五入为整数；敌人数值用取整后 xe | 文档"坐标可四舍五入" |
| 7 | 玩家初始 HP | 8（文档未规定；demo.py 同值） | 骨架常量 |
| 8 | 出发点 | 原点 (0,0)，计为已探索 | 三类点 x 最小≈2cm，必然有可达点 |
| 9 | 升级点 | **9 选项**：永久3 + 被动2（获得制，不可重复）+ 主动4（获得→Lv1，已得→Lv+1，上限3）；引擎改造子选项 AB/AC/BC；子系统子选项 火炮/护盾/能量；永久项可无限叠加故列表永不空 | PDF 版面"6.升级"下三个同级小节 |
| 10 | 能量漏字 | "获得 点【备用能量】"补为"获得 **Ni** 点" | 原文缺字 |
| 11 | 等比取整 | `floor(A + B·(−C)ⁱ)` 对整体取整（A 改造后非整数仍出整数） | 默认参数下与原式等价 |
| 12 | 伤害下限 | max(0, 攻击−DEF)；能量回收仅在实际伤害>0 时触发 | 文档未规定负伤害 |
| 13 | 技能限次 | 每**种**每场一次；施放后统一按 Ni≤0 重判故障（校准器可解故障；火力过载翻倍负值仍故障） | "每场限用一次"合理读法 |
| 14 | 战斗结算 | 结束能量清零；半衰期循环保留 ⌊E/2⌋；护盾每场清零（明示） | 能量子系统"战斗开始时为0" |
| 15 | 菜单 | 数字键输种子（≤5位，空则42），↑/↓ 选引擎，回车开局 | demo.py 注释"三个按钮不需要鼠标" |
| 16 | 音效映射 | 逻辑类只产出事件标签（`events`），场景类统一翻译成 `pyxel.play`——逻辑层保持无声可测 | 关注点分离 |

## 2. 文件结构与类设计

```
E:\Pyxel项目\
├── star_voyage.py                  # 全部游戏代码（新建；demo.py 不动）
├── test_star_voyage.py             # 纯逻辑层 pytest（新建，放根目录便于 import）
├── tools\make_assets.py            # 资产生成脚本（新建）
├── assets\star_voyage.pyxres       # 资产包（由脚本生成，可 pyxel edit 润色）
├── demo.py                         # 只读参考骨架（不改动）
├── 游戏设计文档.pdf                 # 权威设计文档（不改动）
└── docs\superpowers\plans\2026-10-20-pyxel-ttrpg-framework.md  # 本方案
```

star_voyage.py 内部顺序：常量/全局 → 纯逻辑层（Engine、StarMap、Enemy、Ship、Fight）→ 场景层（MenuScene、MapScene、FightScene、LevelupScene、EndingScene，均带 update/draw）→ App（初始化/资产加载/场景切换/转发）→ 入口。

资产布局：图像库 0 顶部一排 8×8 精灵——飞船 (0,0)、星球 (8,0)、敌人 (16,0)、升级方块 (24,0)；音效 0~7 = 光标/火炮/护盾/能量/受击/击破/胜利/失败，8~11 = BGM 四声部，music 0 = BGM 序列。

---

### Task 0（可选）: 初始化 git 仓库

**Files:** Create: `.gitignore`

- [ ] **Step 1: 初始化并提交基线**

```bash
cd "E:\Pyxel项目"
git init
printf "__pycache__/\n*.pyc\n" > .gitignore
git add .gitignore AGENTS.md demo.py 游戏设计文档.pdf docs
git commit -m "chore: baseline (frozen skeleton + design doc + plan v2)"
```

Expected: root-commit 成功。跳过本任务则忽略后续所有"提交"步骤。

---

### Task 1: 安装并配置 pyxel-mcp（后续所有交互验证的基础）

**Files:** 无代码文件；改 MCP 配置。

- [ ] **Step 1: 安装**

```bash
pip install pyxel-mcp        # 或免安装直接 uvx pyxel-mcp
python -m pyxel_mcp --help   # 或 uvx pyxel-mcp --help，确认可执行
```

- [ ] **Step 2: 注册到 ZCode**

先调用 `zcode-guide:zcode-configuration-guide` 技能获取本机用户级 MCP 配置方法，将 stdio server 注册为（示例）：

```json
{ "command": "uvx", "args": ["pyxel-mcp"] }
```

配置需重启 ZCode 会话生效；重启后调用 `pyxel_info` 工具验证（应报告 pyxel 2.9.9 与示例路径）。

- [ ] **Step 3: 约定回退路径**

若 MCP 暂不可用（配置失败/工具未出现），后续各任务验证回退为：`python -m py_compile` + `pytest` + computer-use MCP 操作真实窗口。**不阻塞开发主线。**

---

### Task 2: 常量 + 生成器引擎 Engine（TDD）

**Files:** Create: `star_voyage.py`、`test_star_voyage.py`

- [ ] **Step 1: 写失败测试** —— 新建 `test_star_voyage.py`：

```python
"""star_voyage.py 纯逻辑层测试：引擎公式 / 星图生成 / 敌人数值 / 飞船升级 / 战斗结算。

运行：python -m pytest test_star_voyage.py -v
"""
import math

import pytest

import star_voyage as sv


# ---------- 生成器引擎 ----------

def test_sine_engine_default_sequence():
    eng = sv.Engine("正弦波")
    assert [eng.generate() for _ in range(7)] == [8, 8, 4, 0, -1, 2, 7]


def test_geometric_engine_default_sequence():
    eng = sv.Engine("等比数列")
    assert [eng.generate() for _ in range(6)] == [-2, 3, -3, 5, -4, 6]


def test_chaos_engine_default_sequence():
    eng = sv.Engine("迭代混沌")
    assert [eng.generate() for _ in range(5)] == [-4, 7, 6, 0, 2]


def test_unknown_engine_raises():
    with pytest.raises(ValueError):
        sv.Engine("柴油发动机")


def test_engine_reset_restarts_sequence():
    eng = sv.Engine("迭代混沌")
    first = [eng.generate() for _ in range(3)]
    eng.reset()
    assert [eng.generate() for _ in range(3)] == first


def test_engine_upgrade_multiplies_two_params():
    eng = sv.Engine("正弦波")
    eng.upgrade_params("AB")
    assert (eng.A, eng.B, eng.C) == pytest.approx((5.5, 1.1, 4.0))
    eng2 = sv.Engine("等比数列")
    eng2.upgrade_params("BC")
    assert (eng2.A, eng2.B, eng2.C) == pytest.approx((1.0, 2.2, 1.32))
```

（后续任务向同一文件追加。）

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest test_star_voyage.py -v`
Expected: ERROR —— `ModuleNotFoundError: No module named 'star_voyage'`

- [ ] **Step 3: 写实现** —— 新建 `star_voyage.py`，写入常量与 Engine（demo.py 不动）：

```python
"""Star Voyage —— 《游戏设计文档.pdf》的 Pyxel 实现。

demo.py 为只读参考骨架；本文件是完整实现。
类设计遵循官方示例 10_platformer 惯例：场景/实体类带 update()/draw()，
纯计算核心不依赖 pyxel（可被 pytest 覆盖）。
"""
import math
import os

import pyxel

# ==================== 常量 ====================
PLAYER_HP = 8              # 飞船初始HP（文档未规定，沿用骨架取值）
PLAYER_MAX_MOVE_DIS = 5.0  # 初始最大移动距离（cm）
CM_TO_PX = 10              # 换算：1cm = 10px
Y_OFFSET_PX = 30           # 世界y=0线相对世界像素原点的偏移（敌人y可为负）
WIN_W, WIN_H = 240, 160
ESCAPE_X = 42              # 抵达 x>42 的兴趣点即逃离成功
WORLD_W_CM, WORLD_H_CM = 56, 52  # 世界范围（cm），仅用于摄像机夹取

ASSET_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "assets", "star_voyage.pyxres"))

# 引擎分支名（PDF 权威命名，勿改——字符串是分支依据）
ENG_SIN, ENG_GEO, ENG_CHAOS = "正弦波", "等比数列", "迭代混沌"
ENGINES = (ENG_SIN, ENG_GEO, ENG_CHAOS)
ENGINE_TAG = {ENG_SIN: "SIN", ENG_GEO: "GEO", ENG_CHAOS: "CHAOS"}
ENGINE_BRIEF = {
    ENG_SIN: "stable cycle  A5 B1 C4",
    ENG_GEO: "risk & reward A1 B2 C1.2",
    ENG_CHAOS: "deterministic A4 B7 C2",
}

# UI 只能显示 ASCII（pyxel.text 不支持中文，已实测）——中文键 -> 屏显名
DISPLAY = {
    "星球": "PLANET", "敌人": "ENEMY", "升级": "UPGRADE",
    "火炮": "CANNON", "护盾": "SHIELD", "能量": "ENERGY",
    "火力过载": "OVERLOAD", "应急护盾": "E-SHIELD",
    "输出校准器": "CALIBR", "故障抑制器": "F-SUPP",
}

SYS_LIST = ("火炮", "护盾", "能量")
SKILL_KEYS_ORDER = ("火力过载", "应急护盾", "输出校准器", "故障抑制器")
SKILL_COST = {  # 每级消耗：Lv1/Lv2/Lv3
    "火力过载": (3, 2, 1),
    "应急护盾": (4, 4, 4),
    "输出校准器": (2, 2, 2),
    "故障抑制器": (3, 2, 1),
}
SKILL_HOTKEY = {"火力过载": "Q", "应急护盾": "W", "输出校准器": "E", "故障抑制器": "R"}

# ---- 资产槽位 ----
SPR_SHIP = (0, 0)      # bank0 内 8x8 精灵：飞船/星球/敌人/升级
SPR_PLANET = (8, 0)
SPR_ENEMY = (16, 0)
SPR_UPGRADE = (24, 0)
SND_CURSOR, SND_CANNON, SND_SHIELD, SND_ENERGY = 0, 1, 2, 3
SND_HIT, SND_KILL, SND_WIN, SND_LOSE = 4, 5, 6, 7
MUSIC_BGM = 0

# ==================== 全局状态（沿用骨架约定） ====================
SEED_NOW = 42
SEED_USED = 0
CURRENT_DISTANCE_X = 0.0


# ==================== 生成器引擎（纯逻辑） ====================
class Engine:
    """生成器引擎：战斗中每回合生成出力 N，驱动子系统。"""

    def __init__(self, name):
        self.name = name
        if name == ENG_SIN:
            self.A, self.B, self.C = 5.0, 1.0, 4.0
        elif name == ENG_GEO:
            self.A, self.B, self.C = 1.0, 2.0, 1.2
        elif name == ENG_CHAOS:
            self.A, self.B, self.C = 4.0, 7.0, 2.0
        else:
            raise ValueError(f"未知引擎: {name}")
        self.reset()

    def reset(self):
        """每场战斗重置回合数（迭代混沌 N0=A）。"""
        self.turn = 0
        self.prev = self.A

    def generate(self):
        self.turn += 1
        i = self.turn
        if self.name == ENG_SIN:
            return math.floor(self.A * math.sin(self.B * i) + self.C)
        if self.name == ENG_GEO:
            return math.floor(self.A + self.B * (-self.C) ** i)
        # 迭代混沌
        self.prev = math.floor(self.B * math.sin(self.prev) + self.C)
        return self.prev

    def upgrade_params(self, pair):
        """引擎改造：pair 取 'AB'/'AC'/'BC'，所选两个参数各 ×1.1。"""
        for k in pair:
            setattr(self, k, getattr(self, k) * 1.1)
        self.reset()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest test_star_voyage.py -v`
Expected: 6 passed

- [ ] **Step 5: 提交**（若已 git init）

```bash
git add star_voyage.py test_star_voyage.py
git commit -m "feat: engine subsystem (3 deterministic engines + param tune)"
```

---

### Task 3: 星图 StarMap（TDD）

**Files:** Modify: `star_voyage.py`（追加类）、`test_star_voyage.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
# ---------- 星图 ----------

def test_starmap_deterministic_per_seed():
    assert sv.StarMap(42).points == sv.StarMap(42).points


def test_starmap_point_counts():
    pts = sv.StarMap(815).points
    types = [t for t, _, _ in pts]
    assert types.count("星球") == 12
    assert types.count("敌人") == 15
    assert types.count("升级") == 15


def test_starmap_formula_spot_check_seed42():
    """手工代入 S=42 计算的每类第一个点（S/10=4.2）。"""
    m = sv.StarMap(42)
    assert m.points[0] == ("星球", 2, 3)     # 3+sin(5.2), 3+cos(4.2)
    assert m.points[12] == ("敌人", 3, -2)   # 3.5+2cos(4.2), 2.5+5sin(4.2)
    assert m.points[27] == ("升级", 0, 1)    # 3+3sin(5.2), 3.2+3sin(4.2)


def test_starmap_coordinates_are_integers():
    for _, x, y in sv.StarMap(7).points:
        assert isinstance(x, int)
        assert isinstance(y, int)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest test_star_voyage.py -v`
Expected: 新增 4 条 ERROR（`no attribute 'StarMap'`）

- [ ] **Step 3: 在 Engine 类后追加**

```python
# ==================== 星图（纯逻辑） ====================
class StarMap:
    """星图：按文档公式用种子 S 生成三类兴趣点，坐标四舍五入为整数。"""

    def __init__(self, seed):
        self.seed = seed
        self.points = []                         # [(类型, x, y), ...]
        self.generate()

    def generate(self):
        s10 = self.seed / 10.0                   # 公式中的 S/10
        self.points = []
        for i in range(1, 13):                   # 普通星球 i∈[1,12]
            x = round(3 * i + math.sin(i + s10))
            y = round(3 * i + math.cos(i * s10))
            self.points.append(("星球", x, y))
        for i in range(1, 16):                   # 敌人 i∈[1,15]
            x = round(3.5 * i + 2 * math.cos(i * s10))
            y = round(2.5 * i + 5 * math.sin(i * s10))
            self.points.append(("敌人", x, y))
        for i in range(1, 16):                   # 升级点 i∈[1,15]
            x = round(3 * i + 3 * math.sin(i + s10))
            y = round(3.2 * i + 3 * math.sin(i * s10))
            self.points.append(("升级", x, y))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest test_star_voyage.py -v`
Expected: 10 passed

- [ ] **Step 5: 提交**（若已 git init）

```bash
git add star_voyage.py test_star_voyage.py
git commit -m "feat: seeded starmap generation per design doc formulas"
```

---

### Task 4: 敌人 Enemy（TDD）

**Files:** Modify: `star_voyage.py`、`test_star_voyage.py`

- [ ] **Step 1: 追加失败测试**

```python
# ---------- 敌人 ----------

def test_enemy_stats_from_x():
    e = sv.Enemy(10)
    assert (e.max_hp, e.atk, e.defence) == (13, 2, 2)
    e2 = sv.Enemy(42)
    assert (e2.max_hp, e2.atk, e2.defence) == (29, 5, 10)


def test_enemy_sets_current_distance_x():
    sv.Enemy(30)
    assert sv.CURRENT_DISTANCE_X == 30
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest test_star_voyage.py -v`
Expected: 新增 2 条 ERROR

- [ ] **Step 3: 追加类**（demo.py 中"attack 属性遮蔽 attack 方法 / ATK 用 /2 / DEF 未取整 / 数值取自全局距离"四个问题在此一并纠正）

```python
# ==================== 敌人（纯逻辑） ====================
class Enemy:
    """敌人：数值由其自身坐标 xe 按文档公式计算。"""

    def __init__(self, xe):
        global CURRENT_DISTANCE_X
        CURRENT_DISTANCE_X = xe
        self.xe = xe
        self.max_hp = 8 + xe // 2                # HP = 8 + ⌊xe/2⌋
        self.hp = self.max_hp
        self.atk = 1 + xe // 10                  # ATK = 1 + ⌊xe/10⌋（骨架误用 /2）
        self.defence = abs(xe) // 4              # DEF = ⌊|xe|/4⌋（骨架未取整）
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest test_star_voyage.py -v`
Expected: 12 passed

- [ ] **Step 5: 提交**（若已 git init）

```bash
git add star_voyage.py test_star_voyage.py
git commit -m "fix: enemy stats per PDF (ATK/10, floor) + own-coordinate semantics"
```

---

### Task 5: 飞船 Ship（TDD）

**Files:** Modify: `star_voyage.py`、`test_star_voyage.py`

- [ ] **Step 1: 追加失败测试**

```python
# ---------- 飞船 ----------

def test_ship_initial_state():
    p = sv.Ship("正弦波")
    assert p.hp == 8
    assert p.max_move_dis == 5.0
    assert p.shield == 0 and p.energy == 0
    assert p.visited == {(0, 0)}


def test_reachable_excludes_visited_and_far():
    p = sv.Ship("正弦波")
    pts = [("星球", 3, 3), ("敌人", 20, 0), ("升级", 3, -3)]
    p.visited.add((3, 3))
    r = p.reachable(pts)
    assert ("敌人", 20, 0) not in r
    assert ("升级", 3, -3) in r


def test_move_to_marks_visited():
    p = sv.Ship("正弦波")
    p.move_to(3, 3)
    assert p.x == 3 and p.y == 3
    assert (3, 3) in p.visited


def test_ship_upgrades():
    p = sv.Ship("正弦波")
    p.upgrade_sail()
    assert p.max_move_dis == 5.5
    p.upgrade_subsystem("火炮")
    assert p.bonus["火炮"] == 2
    for _ in range(5):
        p.gain_or_upgrade_skill("火力过载")
    assert p.skills["火力过载"] == 3         # 上限 Lv3
    p.gain_passive("能量回收")
    assert "能量回收" in p.passives
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest test_star_voyage.py -v`
Expected: 新增 4 条 ERROR

- [ ] **Step 3: 追加类**（`draw()` 由场景传入摄像机调用——实体类带 draw 的鸭子类型惯例）

```python
# ==================== 飞船（逻辑 + 实体绘制） ====================
class Ship:
    """飞船：引擎 + 攻击/护盾/能量三子系统 + 升级成长。"""

    def __init__(self, engine_name):
        self.engine = Engine(engine_name)
        self.hp = PLAYER_HP
        self.max_move_dis = PLAYER_MAX_MOVE_DIS  # cm
        self.shield = 0
        self.energy = 0
        self.bonus = dict.fromkeys(SYS_LIST, 0)  # 子系统升级 +2/次
        self.passives = set()                    # 已获被动技能
        self.skills = {}                         # 主动技能 -> Lv(1..3)
        self.used_skills = set()                 # 本场战斗已用主动技能
        self.x, self.y = 0, 0                    # 当前坐标（原点出发）
        self.visited = {(0, 0)}

    def start_battle(self):
        """战斗开始：护盾清零、技能限用重置、引擎回合重置（能量按被动结算保留）。"""
        self.shield = 0
        self.used_skills.clear()
        self.engine.reset()

    def reachable(self, points):
        """最大移动距离内、未探索过的兴趣点 [(类型, x, y), ...]。"""
        out = []
        for t, x, y in points:
            if (x, y) in self.visited:
                continue
            if math.hypot(x - self.x, y - self.y) <= self.max_move_dis + 1e-9:
                out.append((t, x, y))
        return out

    def move_to(self, x, y):
        self.x, self.y = x, y
        self.visited.add((x, y))

    # ---- 升级 ----
    def upgrade_sail(self):
        self.max_move_dis += 0.5                 # 远航升级

    def upgrade_engine(self, pair):
        self.engine.upgrade_params(pair)         # 引擎改造（pair: AB/AC/BC）

    def upgrade_subsystem(self, system):
        self.bonus[system] += 2                  # 子系统升级

    def gain_passive(self, name):
        self.passives.add(name)

    def gain_or_upgrade_skill(self, name):
        self.skills[name] = min(3, self.skills.get(name, 0) + 1)

    # ---- 绘制（由 MapScene 传入摄像机） ----
    def draw(self, cam_x, cam_y):
        sx = int(self.x * CM_TO_PX - cam_x)
        sy = int(self.y * CM_TO_PX + Y_OFFSET_PX - cam_y)
        pyxel.blt(sx - 4, sy - 4, 0, SPR_SHIP[0], SPR_SHIP[1], 8, 8, 0)
        pyxel.circb(sx, sy, 3 + pyxel.frame_count % 4, 7)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest test_star_voyage.py -v`
Expected: 16 passed

- [ ] **Step 5: 提交**（若已 git init）

```bash
git add star_voyage.py test_star_voyage.py
git commit -m "feat: ship state, movement reachability, upgrades, sprite draw"
```

---

### Task 6: 战斗 Fight（TDD）

**Files:** Modify: `star_voyage.py`、`test_star_voyage.py`

- [ ] **Step 1: 追加失败测试**

```python
# ---------- 战斗 ----------

def fight_with(xe=10, engine="正弦波"):
    p = sv.Ship(engine)
    return p, sv.Fight(p, xe)


def test_fight_initializes_battle_state():
    p, f = fight_with(10)
    assert f.enemy.max_hp == 13
    assert p.shield == 0
    assert p.used_skills == set()
    assert f.turn_no == 0


def test_first_turn_detects_fault():
    _, f = fight_with(10, "正弦波")
    f.begin_turn()                            # N1 = 8
    assert f.ni == 8 and not f.fault
    p2 = sv.Ship("等比数列")
    f2 = sv.Fight(p2, 10)
    f2.begin_turn()                           # 等比 i=1 -> -2
    assert f2.ni == -2 and f2.fault


def test_assign_blocked_on_fault():
    _, f = fight_with(10, "等比数列")
    f.begin_turn()
    assert f.assign("火炮") is not None       # 返回错误原因


def test_cannon_battle_to_victory():
    p, f = fight_with(10)                     # 敌 HP13 DEF2 ATK2
    f.begin_turn()                            # N=8
    f.assign("火炮")                          # dmg 6
    assert f.enemy.hp == 7
    f.enemy_turn()                            # 玩家 8->6，并自动开回合2
    assert p.hp == 6
    f.assign("火炮")                          # dmg 6 -> 敌 HP1
    assert f.enemy.hp == 1 and not f.over
    f.enemy_turn()                            # 自动开回合3
    f.assign("火炮")                          # N=4, dmg 2 -> 敌死
    assert f.over and f.win
    assert p.energy == 0                      # 无半衰期循环 -> 清零


def test_shield_absorbs_before_hp():
    p, f = fight_with(42, "正弦波")           # xe=42: ATK 5
    f.begin_turn()                            # N=8
    f.assign("护盾")                          # 护盾 8
    f.enemy_turn()
    assert p.shield == 3 and p.hp == 8


def test_energy_assignment_with_system_bonus():
    p, f = fight_with(10)
    p.upgrade_subsystem("能量")               # +2
    f.begin_turn()
    f.assign("能量")
    assert p.energy == 10                     # 8 + 2


def test_recycle_passive_triggers_on_damage():
    p, f = fight_with(10)
    p.gain_passive("能量回收")
    f.begin_turn()
    f.assign("火炮")
    assert p.energy == 2


def test_half_life_keeps_half_energy():
    p, f = fight_with(10)
    p.gain_passive("半衰期循环")
    p.energy = 5
    f._finish(True)
    assert p.energy == 2                      # ⌊5/2⌋


def test_events_recorded_for_scene():
    p, f = fight_with(10)
    f.begin_turn()
    f.assign("护盾")
    f.enemy_turn()
    assert f.events == ["ship_hit"]           # 逻辑只发事件，场景负责发声
    f.events.clear()
    f._finish(True)
    assert f.events == ["win"]


def test_overload_doubles_ni():
    p, f = fight_with(10, "正弦波")
    p.energy = 3
    p.skills["火力过载"] = 1
    f.begin_turn()
    assert f.cast_skill("火力过载") is None
    assert f.ni == 16 and p.energy == 0


def test_skill_once_per_fight():
    p, f = fight_with(10, "正弦波")
    p.energy = 99
    p.skills["应急护盾"] = 1
    f.begin_turn()
    f.cast_skill("应急护盾")
    assert f.cast_skill("应急护盾") is not None


def test_skill_cost_scales_with_level():
    p, f = fight_with(10, "正弦波")
    p.skills["火力过载"] = 2
    p.energy = 5
    f.begin_turn()
    f.cast_skill("火力过载")                  # Lv2 消耗 2
    assert p.energy == 3 and f.ni == 16


def test_emergency_shield_clears_then_grants():
    p, f = fight_with(10, "正弦波")
    p.shield = 9
    p.energy = 4
    p.skills["应急护盾"] = 3
    f.begin_turn()
    f.cast_skill("应急护盾")
    assert p.shield == 6                      # 清零后 +6


def test_calibrator_sets_ni_and_clears_fault():
    p, f = fight_with(10, "等比数列")
    p.energy = 2
    p.skills["输出校准器"] = 2
    f.begin_turn()                            # N=-2 故障
    assert f.fault
    assert f.cast_skill("输出校准器") is None
    assert f.ni == 6 and not f.fault


def test_suppressor_only_usable_on_fault():
    p, f = fight_with(10, "正弦波")
    p.energy = 3
    p.skills["故障抑制器"] = 1
    f.begin_turn()                            # N=8 非故障
    assert f.cast_skill("故障抑制器") is not None


def test_suppressor_converts_fault_to_positive():
    p, f = fight_with(10, "等比数列")
    p.energy = 3
    p.skills["故障抑制器"] = 1
    f.begin_turn()                            # N=-2
    assert f.cast_skill("故障抑制器") is None
    assert f.ni == 2 and not f.fault
    assert f.assign("火炮") is None


def test_player_death_loses():
    p, f = fight_with(2, "迭代混沌")          # xe=2: HP9 ATK1 DEF0
    p.hp = 2
    f.begin_turn()                            # 混沌 N1=-4 故障
    assert f.fault
    f.enemy_turn()                            # 玩家 2->1，自动开回合2 (N=7)
    assert p.hp == 1 and not f.over
    f.assign("火炮")                          # dmg7 -> 敌 HP2
    assert not f.over
    f.enemy_turn()                            # 玩家归零
    assert f.over and not f.win
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest test_star_voyage.py -v`
Expected: 新增 17 条 ERROR（`no attribute 'Fight'`）

- [ ] **Step 3: 在 Ship 类后追加**

```python
# ==================== 战斗（纯逻辑，事件交场景发声） ====================
class Fight:
    """一场战斗：玩家先动的回合制。"""

    def __init__(self, player, enemy_x):
        self.player = player
        self.enemy = Enemy(enemy_x)
        player.start_battle()
        self.turn_no = 0
        self.ni = 0
        self.fault = False
        self.msg = None          # 最近一次非法操作的提示（屏显）
        self.log = []
        self.events = []         # 事件标签：ship_hit / win / lose（场景翻译成音效）
        self.over = False
        self.win = False

    def begin_turn(self):
        self.turn_no += 1
        self.ni = self.player.engine.generate()
        self.fault = self.ni <= 0
        self.msg = None
        self.log.append(f"turn{self.turn_no} N={self.ni}"
                        + (" [FAULT]" if self.fault else ""))

    def cast_skill(self, name):
        """主动技能。成功返回 None，失败返回英文原因（供屏显）。"""
        lv = self.player.skills.get(name, 0)
        if lv == 0:
            return "skill not owned"
        if name in self.player.used_skills:
            return "already used this fight"
        if name == "故障抑制器" and not self.fault:
            return "engine not faulted"
        cost = SKILL_COST[name][lv - 1]
        if self.player.energy < cost:
            return "not enough energy"
        self.player.energy -= cost
        self.player.used_skills.add(name)
        if name == "火力过载":
            self.ni *= 2
        elif name == "应急护盾":
            self.player.shield = 3 + lv          # 清零后获得 4/5/6
        elif name == "输出校准器":
            self.ni = 4 + lv                     # 强制 5/6/7
        elif name == "故障抑制器":
            self.ni = abs(self.ni)
        self.fault = self.ni <= 0                # 统一重判故障
        self.log.append(f"  {SKILL_HOTKEY[name]}:{DISPLAY[name]} Lv{lv} -{cost}E")
        return None

    def assign(self, system):
        """把 N(+子系统加成) 分配给子系统。成功返回 None。"""
        if self.fault:
            return "fault: cannot assign"
        val = self.ni + self.player.bonus[system]
        if system == "火炮":
            dmg = max(0, val - self.enemy.defence)
            self.enemy.hp -= dmg
            self.log.append(f"  CANNON {val} -> dmg{dmg}")
            if dmg > 0 and "能量回收" in self.player.passives:
                self.player.energy += 2
                self.log.append("  RECYCLE +2E")
            if self.enemy.hp <= 0:
                self._finish(True)
        elif system == "护盾":
            self.player.shield += val
            self.log.append(f"  SHIELD +{val}")
        else:
            self.player.energy += val
            self.log.append(f"  ENERGY +{val}")
        return None

    def enemy_turn(self):
        """敌人回合：伤害优先由护盾承受；结束后自动开启下一玩家回合。"""
        if self.over:
            return
        absorbed = min(self.player.shield, self.enemy.atk)
        self.player.shield -= absorbed
        self.player.hp -= self.enemy.atk - absorbed
        self.log.append(f"  enemy hit{self.enemy.atk} shield-{absorbed}")
        self.events.append("ship_hit")
        if self.player.hp <= 0:
            self._finish(False)
        else:
            self.begin_turn()

    def _finish(self, win):
        """战斗结算：能量清零；半衰期循环保留一半（向下取整）。"""
        self.over = True
        self.win = win
        if "半衰期循环" in self.player.passives:
            self.player.energy //= 2
        else:
            self.player.energy = 0
        self.log.append("YOU WIN" if win else "YOU LOSE")
        self.events.append("win" if win else "lose")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest test_star_voyage.py -v`
Expected: 33 passed

- [ ] **Step 5: 提交**（若已 git init）

```bash
git add star_voyage.py test_star_voyage.py
git commit -m "feat: turn-based combat with skills, passives, event bus"
```

---

### Task 7: 资产包生成 tools/make_assets.py（美术 + 音效 + 音乐，可编辑）

**Files:** Create: `tools/make_assets.py`；生成: `assets/star_voyage.pyxres`

- [ ] **Step 1: 写生成脚本**（脚本即资产源头；重跑会覆盖人工编辑，文件头注明）

```python
"""程序化生成 assets/star_voyage.pyxres —— 本脚本是资产的"源头"。

运行（无窗口）: python tools/make_assets.py
人工润色: pyxel edit assets/star_voyage.pyxres
注意：重跑本脚本会覆盖 .pyxres 中的人工编辑；
请把润色结果反向誊回本脚本，或以编辑稿为准不再重跑。
"""
import os

import pyxel

OUT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "star_voyage.pyxres"))

# ---- 8x8 精灵；每字符=一个调色板号(0-f)，'0'=透明（blt 色键 0） ----
SPRITES = {
    "ship": (0, ["00070000",
                 "00777700",
                 "07777776",
                 "00777700",
                 "00070000",
                 "00000000",
                 "00000000",
                 "00000000"]),
    "planet": (8, ["00333300",
                   "0333b330",
                   "333bb333",
                   "3b333333",
                   "33333333",
                   "33333333",
                   "03333330",
                   "00333300"]),
    "enemy": (16, ["00008000",
                   "00088000",
                   "00877800",
                   "08777780",
                   "88888888",
                   "00000000",
                   "00000000",
                   "00000000"]),
    "upgrade": (24, ["99999999",
                     "9aaaaaa9",
                     "9aa99aa9",
                     "9aa99aa9",
                     "9aaaaaa9",
                     "99999999",
                     "00000000",
                     "00000000"]),
}

# ---- 音效：Sound.set(音名序列, 音色, 音量, 效果, 速度) ----
# 音色 t三角 s方波 p脉冲 n噪声；效果 n无 s滑音 v颤音 f淡出
SOUNDS = {
    0: ("c4", "s", "2", "n", 1),            # 光标移动
    1: ("c3g3", "n", "5", "f", 1),          # 火炮
    2: ("c3e3", "t", "4", "n", 2),          # 护盾
    3: ("e4b4", "p", "3", "n", 1),          # 能量
    4: ("c2", "n", "6", "f", 1),            # 飞船受击
    5: ("c4e4g4", "s", "4", "f", 2),        # 击破
    6: ("c4e4g4c5g4c5", "s", "4", "n", 3),  # 胜利
    7: ("c3g2c2", "t", "4", "f", 4),        # 失败
    # 8~11: BGM 四声部
    8: ("c2c2g2c2", "t", "3", "n", 4),
    9: ("e4g4a4g4", "s", "2", "n", 4),
    10: ("f4a4c5a4", "s", "2", "n", 4),
    11: ("g4b4d5b4", "s", "2", "n", 4),
}


def build_images():
    img = pyxel.images[0]
    img.cls(0)
    for _, (x, rows) in SPRITES.items():
        img.set(x, 0, rows)


def build_sounds():
    for n, (notes, tone, vol, eff, speed) in SOUNDS.items():
        pyxel.sounds[n].set(notes, tone, vol, eff, speed)
    pyxel.musics[0].set([8, 9, 10, 11])      # BGM：单通道顺序循环四个声部


def self_check():
    assert pyxel.images[0].pget(0, 0) == 0   # 船左上透明
    assert pyxel.images[0].pget(3, 2) == 7   # 船身白
    assert pyxel.images[0].pget(19, 3) == 7  # 敌机眼白
    assert pyxel.sounds[0].notes[0] > 0
    assert len(pyxel.musics[0].seqs[0]) == 4
    print("self-check ok")


def main():
    pyxel.init(240, 160, title="make_assets", headless=True)
    build_images()
    build_sounds()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pyxel.save(OUT)
    self_check()
    pyxel.load(OUT)                          # 保存-加载回路再验一次
    self_check()
    print("written:", OUT)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行生成并自检**

Run: `python tools/make_assets.py`
Expected: 输出两行 `self-check ok` 与 `written: ...\assets\star_voyage.pyxres`

- [ ] **Step 3: 验证资产包**

优先用 pyxel-mcp：`read_image`（bank0 出 PNG 核对四个精灵）、`read_audio`（渲染 sound 6 为 WAV，确认非静音）。
回退（无 MCP）：`python -c "import pyxel; pyxel.init(64,32,headless=True); pyxel.load('assets/star_voyage.pyxres'); print(pyxel.images[0].pget(3,2))"` 应输出 7。

- [ ] **Step 4: 人工编辑入口确认**

`pyxel edit assets/star_voyage.pyxres`（可选，人工润色；完成后按编辑稿维护脚本或停跑脚本）。

- [ ] **Step 5: 提交**（若已 git init）

```bash
git add tools/make_assets.py assets/star_voyage.pyxres
git commit -m "feat: procedural asset pack (sprites, sfx, bgm) -> editable pyxres"
```

---

### Task 8: App 场景机 + MenuScene（鸭子类型）

**Files:** Modify: `star_voyage.py`（文件尾追加场景类与 App + 入口）

- [ ] **Step 1: 追加场景层与 App**

```python
# ==================== 场景层（每个场景都有 update/draw） ====================
class MenuScene:
    """菜单：输入种子 + 三选一引擎。"""

    def __init__(self, app):
        self.app = app
        self.seed_input = ""
        self.engine_idx = 0

    def update(self):
        for k in range(pyxel.KEY_0, pyxel.KEY_9 + 1):
            if pyxel.btnp(k) and len(self.seed_input) < 5:
                self.seed_input += str(k - pyxel.KEY_0)
        if pyxel.btnp(pyxel.KEY_BACKSPACE):
            self.seed_input = self.seed_input[:-1]
        if pyxel.btnp(pyxel.KEY_UP):
            self.engine_idx = (self.engine_idx - 1) % len(ENGINES)
            pyxel.play(3, SND_CURSOR)
        if pyxel.btnp(pyxel.KEY_DOWN):
            self.engine_idx = (self.engine_idx + 1) % len(ENGINES)
            pyxel.play(3, SND_CURSOR)
        if pyxel.btnp(pyxel.KEY_RETURN):
            seed = int(self.seed_input) if self.seed_input else 42
            self.app.start_run(seed, ENGINES[self.engine_idx])

    def draw(self):
        pyxel.text(78, 14, "== STAR VOYAGE ==", 10)
        pyxel.blt(112, 24, 0, SPR_SHIP[0], SPR_SHIP[1], 8, 8, 0)
        seed_show = self.seed_input if self.seed_input else "42"
        pyxel.text(24, 40, f"SEED: {seed_show}   (digits type, BKSP del)", 7)
        pyxel.text(24, 56, "PICK ENGINE: [UP/DOWN]", 6)
        for i, name in enumerate(ENGINES):
            col = 7 if i == self.engine_idx else 5
            mark = ">" if i == self.engine_idx else " "
            pyxel.text(32, 68 + i * 12,
                       f"{mark} {ENGINE_TAG[name]}  {ENGINE_BRIEF[name]}", col)
        pyxel.text(24, 112, "[RETURN] START (empty seed = 42)", 6)


class MapScene:
    """星图：渲染 + 选点移动 + 场景切换判定。"""

    def __init__(self, app):
        self.app = app
        self.sel_idx = 0
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.update_camera()

    # ---- 摄像机 ----
    def w2s(self, wx, wy):
        """世界cm坐标 -> 屏幕px坐标（y轴向上翻转）。"""
        return (int(wx * CM_TO_PX - self.cam_x),
                int(wy * CM_TO_PX + Y_OFFSET_PX - self.cam_y))

    def update_camera(self):
        """摄像机跟随飞船并夹取在世界范围内。"""
        ship = self.app.ship
        tx = ship.x * CM_TO_PX - WIN_W / 2
        ty = ship.y * CM_TO_PX + Y_OFFSET_PX - WIN_H / 2
        self.cam_x = max(0.0, min(tx, WORLD_W_CM * CM_TO_PX - WIN_W))
        self.cam_y = max(0.0, min(ty, WORLD_H_CM * CM_TO_PX + Y_OFFSET_PX - WIN_H))

    def reachable_targets(self):
        return self.app.ship.reachable(self.app.world.points)

    def update(self):
        self.update_camera()
        targets = self.reachable_targets()
        if not targets:
            self.app.ending_win = False      # 燃料耗尽：可达范围内无未探索点
            self.app.change_scene("ending")
            return
        self.sel_idx %= len(targets)
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_LEFT):
            self.sel_idx = (self.sel_idx - 1) % len(targets)
            pyxel.play(3, SND_CURSOR)
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_RIGHT):
            self.sel_idx = (self.sel_idx + 1) % len(targets)
            pyxel.play(3, SND_CURSOR)
        if pyxel.btnp(pyxel.KEY_RETURN):
            global SEED_USED
            t = targets[self.sel_idx]
            if SEED_USED != SEED_NOW:
                SEED_USED = SEED_NOW         # 本局种子已启用（沿用骨架全局变量）
            self.app.ship.move_to(t[1], t[2])
            if t[1] > ESCAPE_X:              # 抵达 x>42：逃离成功
                self.app.ending_win = True
                self.app.change_scene("ending")
            elif t[0] == "敌人":
                self.app.fight = Fight(self.app.ship, t[1])
                self.app.change_scene("fight")
            elif t[0] == "升级":
                self.app.change_scene("levelup")
            else:                            # 普通星球：中继跳板
                self.sel_idx = 0

    def draw(self):
        ship = self.app.ship
        # 1cm 网格
        cx0 = int(self.cam_x // CM_TO_PX)
        cx1 = int((self.cam_x + WIN_W) // CM_TO_PX) + 1
        for cx in range(cx0, cx1 + 1):
            sx = cx * CM_TO_PX - self.cam_x
            pyxel.line(sx, 0, sx, WIN_H, 1)
        cy0 = int((self.cam_y - Y_OFFSET_PX) // CM_TO_PX) - 1
        cy1 = int((self.cam_y + WIN_H - Y_OFFSET_PX) // CM_TO_PX) + 1
        for cy in range(cy0, cy1 + 1):
            sy = cy * CM_TO_PX + Y_OFFSET_PX - self.cam_y
            pyxel.line(0, sy, WIN_W, sy, 1)
        # x 轴与逃生边界 x>42
        _, sy0 = self.w2s(0, 0)
        pyxel.line(0, sy0, WIN_W, sy0, 6)
        sx42, _ = self.w2s(ESCAPE_X, 0)
        if 0 <= sx42 < WIN_W:
            pyxel.line(sx42, 0, sx42, WIN_H, 4)
            pyxel.text(min(sx42 + 2, WIN_W - 80), 4, "ESCAPE x>42", 4)
        # 兴趣点：已探索画暗点，未探索画精灵
        targets = self.reachable_targets()
        sel = targets[self.sel_idx % len(targets)] if targets else None
        for t, x, y in self.app.world.points:
            sx, sy = self.w2s(x, y)
            if (x, y) in ship.visited:
                pyxel.circ(sx, sy, 2, 5)
            else:
                spr = {"星球": SPR_PLANET, "敌人": SPR_ENEMY, "升级": SPR_UPGRADE}[t]
                pyxel.blt(sx - 4, sy - 4, 0, spr[0], spr[1], 8, 8, 0)
        if sel is not None and pyxel.frame_count % 30 < 20:
            sx, sy = self.w2s(sel[1], sel[2])
            pyxel.circb(sx, sy, 7, 7)
        ship.draw(self.cam_x, self.cam_y)
        # HUD 与选中目标信息
        pyxel.rect(0, 0, WIN_W, 8, 0)
        pyxel.text(2, 1, f"HP{max(0, ship.hp)} SH{ship.shield} E{ship.energy} "
                         f"MOVE{ship.max_move_dis:.1f} S{self.app.world.seed} "
                         f"{ENGINE_TAG[ship.engine.name]}", 7)
        if sel is not None:
            d = math.hypot(sel[1] - ship.x, sel[2] - ship.y)
            pyxel.rect(0, WIN_H - 8, WIN_W, 8, 0)
            pyxel.text(2, WIN_H - 7,
                       f"{DISPLAY[sel[0]]} ({sel[1]},{sel[2]}) d={d:.1f}cm"
                       f"  [ARROWS]pick [RETURN]go", 7)


class FightScene:
    """战斗：键盘交互驱动 Fight 纯逻辑，并把逻辑事件翻译成音效。"""

    SND_OF_EVENT = {"ship_hit": SND_HIT, "win": SND_WIN, "lose": SND_LOSE}

    def __init__(self, app):
        self.app = app
        if app.fight.turn_no == 0:
            app.fight.begin_turn()

    def update(self):
        f = self.app.fight
        if f.over:
            if pyxel.btnp(pyxel.KEY_RETURN):
                win = f.win
                self.app.fight = None
                if win:
                    self.app.change_scene("map")   # 燃料耗尽由下一帧地图接管
                else:
                    self.app.ending_win = False
                    self.app.change_scene("ending")
        else:
            self.handle_input(f)
        self.flush_events(f)

    def handle_input(self, f):
        # 主动技能 Q/W/E/R（引擎故障回合仍可用）
        for key, name in zip((pyxel.KEY_Q, pyxel.KEY_W, pyxel.KEY_E, pyxel.KEY_R),
                             SKILL_KEYS_ORDER):
            if pyxel.btnp(key):
                f.msg = f.cast_skill(name)
                if f.msg is None:
                    pyxel.play(3, SND_ENERGY)
                return
        # 分配 N：1火炮 2护盾 3能量（引擎故障回合禁用）
        if not f.fault:
            for key, system, snd in ((pyxel.KEY_1, "火炮", SND_CANNON),
                                     (pyxel.KEY_2, "护盾", SND_SHIELD),
                                     (pyxel.KEY_3, "能量", SND_ENERGY)):
                if pyxel.btnp(key):
                    f.msg = f.assign(system)
                    if f.msg is None:
                        pyxel.play(3, snd)
                        f.enemy_turn()     # 敌人回合后自动进入下一玩家回合
                    return

    def flush_events(self, f):
        for ev in f.events:
            pyxel.play(3, self.SND_OF_EVENT[ev])
        f.events.clear()

    def draw(self):
        f = self.app.fight
        e = f.enemy
        ship = self.app.ship
        pyxel.text(8, 8, f"ENEMY  HP:{max(0, e.hp)}/{e.max_hp} ATK:{e.atk} DEF:{e.defence}", 8)
        pyxel.text(8, 16, f"SHIP   HP:{max(0, ship.hp)} SHIELD:{ship.shield} ENERGY:{ship.energy}", 11)
        pyxel.text(8, 24, f"TURN{f.turn_no}  N={f.ni}" + ("  [FAULT!]" if f.fault else ""),
                   6 if f.fault else 7)
        y = 40
        for line in f.log[-7:]:
            pyxel.text(8, y, line, 5)
            y += 8
        pyxel.rect(0, WIN_H - 22, WIN_W, 22, 1)
        pyxel.text(2, WIN_H - 20, "[1]CANNON [2]SHIELD [3]ENERGY", 6)
        tips = "  ".join(f"{SKILL_HOTKEY[s]}:{DISPLAY[s]}" for s in SKILL_KEYS_ORDER)
        pyxel.text(2, WIN_H - 12, f"SKILLS: {tips}", 6)
        if f.msg:
            pyxel.text(2, WIN_H - 4, f.msg, 8)
        if f.over:
            pyxel.text(92, 66, "YOU WIN!" if f.win else "YOU LOSE", 10 if f.win else 8)
            pyxel.text(88, 76, "press [RETURN]", 7)


class LevelupScene:
    """升级：9 选项（永久3+被动2+主动4），部分带子选项。"""

    def __init__(self, app):
        self.app = app
        self.options = self.build_options()
        self.idx = 0
        self.sub = None            # None 或 子选项列表
        self.sub_idx = 0

    def build_options(self):
        ship = self.app.ship
        opts = [
            ("sail", "SAIL UP: max move +0.5cm"),
            ("engine", "TUNE ENGINE: pick 2 params x1.1"),
            ("system", "TUNE SYSTEM: pick one, +2 when assigned"),
        ]
        if "半衰期循环" not in ship.passives:
            opts.append(("passive", "PASSIVE HALF-LIFE: keep half E next fight"))
        if "能量回收" not in ship.passives:
            opts.append(("passive", "PASSIVE RECYCLE: +2E on cannon damage"))
        for s in SKILL_KEYS_ORDER:
            lv = ship.skills.get(s, 0)
            if lv < 3:
                opts.append(("skill", f"SKILL {DISPLAY[s]} -> Lv{lv + 1}"))
        return opts

    def after_apply(self):
        self.app.sel_hint_reset = True
        self.app.change_scene("map")       # 燃料耗尽由下一帧地图接管

    def update(self):
        if self.sub is None:
            n = len(self.options)
            if pyxel.btnp(pyxel.KEY_UP):
                self.idx = (self.idx - 1) % n
                pyxel.play(3, SND_CURSOR)
            if pyxel.btnp(pyxel.KEY_DOWN):
                self.idx = (self.idx + 1) % n
                pyxel.play(3, SND_CURSOR)
            if pyxel.btnp(pyxel.KEY_RETURN):
                kind, label = self.options[self.idx]
                ship = self.app.ship
                if kind == "sail":
                    ship.upgrade_sail()
                    self.after_apply()
                elif kind == "engine":
                    self.sub = ["AB", "AC", "BC"]
                    self.sub_idx = 0
                elif kind == "system":
                    self.sub = list(SYS_LIST)
                    self.sub_idx = 0
                elif kind == "passive":
                    ship.gain_passive("半衰期循环" if "HALF-LIFE" in label else "能量回收")
                    self.after_apply()
                else:                        # skill
                    name = next(s for s in SKILL_KEYS_ORDER if DISPLAY[s] in label)
                    ship.gain_or_upgrade_skill(name)
                    self.after_apply()
        else:
            n = len(self.sub)
            if pyxel.btnp(pyxel.KEY_UP):
                self.sub_idx = (self.sub_idx - 1) % n
                pyxel.play(3, SND_CURSOR)
            if pyxel.btnp(pyxel.KEY_DOWN):
                self.sub_idx = (self.sub_idx + 1) % n
                pyxel.play(3, SND_CURSOR)
            if pyxel.btnp(pyxel.KEY_ESCAPE):
                self.sub = None
            if pyxel.btnp(pyxel.KEY_RETURN):
                chosen = self.sub[self.sub_idx]
                if chosen in ("AB", "AC", "BC"):
                    self.app.ship.upgrade_engine(chosen)
                else:
                    self.app.ship.upgrade_subsystem(chosen)
                self.after_apply()

    def draw(self):
        pyxel.text(88, 8, "== UPGRADE ==", 10)
        if self.sub is None:
            for i, (_, label) in enumerate(self.options):
                col = 7 if i == self.idx else 5
                mark = ">" if i == self.idx else " "
                pyxel.text(12, 24 + i * 10, f"{mark} {label}", col)
            pyxel.text(12, WIN_H - 10, "[UP/DOWN] pick  [RETURN] confirm", 6)
        else:
            pyxel.text(12, 24, "choose:", 6)
            for i, chosen in enumerate(self.sub):
                col = 7 if i == self.sub_idx else 5
                mark = ">" if i == self.sub_idx else " "
                label = chosen if chosen in ("AB", "AC", "BC") else DISPLAY[chosen]
                pyxel.text(28, 40 + i * 10, f"{mark} {label}", col)
            pyxel.text(12, WIN_H - 10, "[UP/DOWN] pick [RETURN] ok [ESC] back", 6)


class EndingScene:
    """结算：胜/败文案 + 返回菜单。"""

    def __init__(self, app):
        self.app = app

    def update(self):
        if pyxel.btnp(pyxel.KEY_RETURN):
            self.app.ship = None
            self.app.world = None
            self.app.fight = None
            self.app.change_scene("menu")

    def draw(self):
        if self.app.ending_win:
            pyxel.text(84, 60, "ESCAPE SUCCESS!", 10)
        else:
            pyxel.text(96, 60, "GAME OVER", 8)
        pyxel.text(70, 80, "press [RETURN] to menu", 7)


# ==================== 应用 ====================
class App:
    """初始化 pyxel、加载资产、注册场景；update/draw 只向当前场景转发。"""

    def __init__(self):
        pyxel.init(WIN_W, WIN_H, title="Star Voyage")
        pyxel.load(ASSET_PATH)
        pyxel.playm(MUSIC_BGM, loop=True)
        self.ship = None
        self.world = None
        self.fight = None
        self.ending_win = False
        self.scene = None
        self.change_scene("menu")
        pyxel.run(self.update, self.draw)

    def change_scene(self, name):
        self.scene = SCENES[name](self)

    def start_run(self, seed, engine_name):
        global SEED_NOW, SEED_USED
        SEED_NOW = seed
        SEED_USED = 0
        self.world = StarMap(SEED_NOW)
        self.ship = Ship(engine_name)
        self.fight = None
        self.change_scene("map")

    def update(self):
        self.scene.update()

    def draw(self):
        pyxel.cls(0)
        self.scene.draw()


SCENES = {"menu": MenuScene, "map": MapScene, "fight": FightScene,
          "levelup": LevelupScene, "ending": EndingScene}


if __name__ == "__main__":
    App()
```

- [ ] **Step 2: 校验**

Run: `python -m py_compile star_voyage.py && python -m pytest test_star_voyage.py -v`
Expected: 编译无输出；33 passed

- [ ] **Step 3: 交互冒烟（基于 pyxel-mcp）**

用 MCP `validate` 校验脚本 → `run`（headless，定时输入：`RETURN@30` 开局）→ 对 snapshot 做 `read_image`：应看到网格与星点（替代人工看窗）。MCP 未就绪时回退 computer-use 开窗检查菜单与开局画面。

- [ ] **Step 4: 提交**（若已 git init）

```bash
git add star_voyage.py
git commit -m "feat: app scene machine + menu/map/fight/levelup/ending scenes"
```

（Task 8 一次给出全部场景：逻辑层已各自 TDD 通过，场景层是纯转发/渲染薄壳，合并提交比拆四步更不易出现中间态断裂；冒烟仍按 Task 9~11 分场景推进。）

---

### Task 9: 地图场景验收（MCP 驱动）

**Files:** 无改动；验证 MapScene。

- [ ] **Step 1: MCP run 脚本化移动**

`run` 工具 headless 执行 star_voyage.py，定时输入：`RETURN@30`（开局）→ `DOWN@90`（选中一个目标）→ `RETURN@150`（移动）。对前后两帧跑 `diff_frames`：应报告飞船位置区域像素变化，证明移动生效。

- [ ] **Step 2: 胜负判定抽查**

构造移动序列直接把飞船送到 x>42 点（种子 42 时升级点 (0,1) 起步、敌点链向右），确认 `ESCAPE SUCCESS!`；再开一局只走孤立点触发 `GAME OVER`（燃料耗尽）。

- [ ] **Step 3: 记录与提交**（若已 git init）

```bash
git add -A
git commit -m "test: map scene acceptance via pyxel-mcp"
```

---

### Task 10: 战斗场景验收（MCP 驱动）

**Files:** 无改动；验证 FightScene。

- [ ] **Step 1: MCP run 打一场**

定时输入进入战斗后：`1@+30`（火炮）×N 次间隔 60 帧，直到快照出现 `YOU WIN!`；`read_image` 断言敌方 HP 文本行递减。

- [ ] **Step 2: 技能与故障路径**

选 CHAOS 引擎复测：故障回合按 `1` 应无效果（`f.msg` 提示出现在画面），`R`（故障抑制器，需先获得）或改用已有技能路径验证。至少覆盖一次胜利与一次败北（败北进 `GAME OVER`）。

- [ ] **Step 3: 提交**（若已 git init）

```bash
git add -A
git commit -m "test: fight scene acceptance via pyxel-mcp"
```

---

### Task 11: 升级与结算场景验收（MCP 驱动）

**Files:** 无改动；验证 LevelupScene/EndingScene。

- [ ] **Step 1: 升级流**

脚本：移动到升级点 → `RETURN` 进升级 → 选 `SAIL UP` 确认 → 快照 HUD `MOVE` 由 5.0 变 5.5；再验 `TUNE ENGINE` 子菜单（AB/AC/BC）与 `ESC` 返回。

- [ ] **Step 2: 结算流**

胜利局与失败局各自到达 EndingScene，`read_image` 断言对应文案，`RETURN` 回菜单。

- [ ] **Step 3: 提交**（若已 git init）

```bash
git add -A
git commit -m "test: levelup & ending acceptance via pyxel-mcp"
```

---

### Task 12: 全流程验收（MCP 一局通关 + 人工游玩）

**Files:** 无改动。

- [ ] **Step 1: MCP 全局冒烟**

`pyxel_info` 确认环境 → `run` 完整脚本（输种子 815 / 选 GEO / 数次移动 / 一场战斗 / 一次升级 / 逃至 x>42），收集关键帧快照留档。

- [ ] **Step 2: 人工游玩（可选但建议）**

`python star_voyage.py`，按剧本：种子 815 + GEO 开局 → 踩升级点选远航/改造/子系统各一次 → 打一场用 Q 翻倍 → 越红线逃离 → 失败局两路径（战斗败北 / 燃料耗尽）。

- [ ] **Step 3: 收尾提交**（若已 git init）

```bash
git add -A
git commit -m "chore: full-game acceptance passed"
```

---

## 附录 A：原 demo.py 骨架问题清单（20 项）与改进映射

### A1 致命错误（运行即崩 / 功能失效）
| # | 位置 | 问题 | v2 修复处 |
|---|------|------|-----------|
| 1 | Player.__init__ (L10-13) | `current_engine/hp/max_move_dis` 赋给局部变量未绑 self → `generate()` 访问 `self.current_engine` 直接 AttributeError | Task 5 Ship |
| 2 | Player.__init__ L11 | `current_engine = "sin"` 与分支键 `"正弦波"` 等不匹配 → 即便绑了 self 也永远落入 else 返回 None | Task 2 Engine 分支键 + Task 5 |
| 3 | Map.__init__ (L71-77) | `seed/normalPlanet/enemyPlanet/upgradePlanet` 同样是局部变量；`generate()` 空实现 | Task 3 StarMap |
| 4 | L39/L52 | `subsystem(text)`、`upgrade(text)` 缺 `self` → 实例调用 TypeError | Task 5/6 按职责拆分（升级归 Ship/场景，分配归 Fight） |
| 5 | L106/L108 | `self.current_scene == "map"` 是**比较**不是赋值 → 场景永远切不过去 | Task 8 change_scene() |
| 6 | 文件尾 | 无 `App()` 入口 → `python demo.py` 静默退出 | Task 8 `__main__` |

### A2 逻辑与设计文档不符
| # | 位置 | 问题 | v2 修复处 |
|---|------|------|-----------|
| 7 | L58 | ATK = 1 + x**/2**，PDF 为 1 + ⌊x**/10**⌋ | Task 4 |
| 8 | L59 | DEF 未按 PDF 取整（⌊\|x\|/4⌋），产生小数防御 | Task 4 |
| 9 | L56-59 | 敌人数值取自全局 `CURRENT_DISTANCE_X` 而非**该敌人自身坐标 xe**——语义耦合错误 | Task 4（构造参数 xe；全局仅同步记录） |
| 10 | L22-37 | `generate()` 三分支 `return result`（恒 0），公式只活在注释里；迭代混沌注释 `N_0 = AN_i = ...` 断行丢失，照抄会实现错 | Task 2 Engine 完整实现 |

### A3 结构 / 惯例问题（对照官方示例）
| # | 位置 | 问题 | v2 修复处 |
|---|------|------|-----------|
| 11 | 全文件 | Player/Enemy/Map 从未被 App 实例化，update/draw 空壳没接入 `pyxel.run`——违背官方"实体类 update/draw + 顶层转发"惯例 | Task 8 五场景 + App 转发 |
| 12 | L93 | `current_scene` 是**类属性**（应仅实例属性；类属性会被所有实例共享） | Task 8 |
| 13 | L105-108 | `pyxel.btn()` 无参 = 任意键且按住每帧为真 → 菜单会被瞬间打穿；应使用 `btnp`（按下沿）+ 具体键位 | Task 8 全部改 btnp |
| 14 | L107-108 | 两个 `elif pyxel.btn()` 条件完全相同 → 第二分支死代码 | Task 8 按键方案重写 |
| 15 | L114-119 | `fight` 场景无任何进入路径，ending 只能从菜单进——场景机不完整 | Task 8 完整状态流转 |
| 16 | L73-75 | 命名混用驼峰 `normalPlanet` 与 snake_case（PEP8 应后者） | Task 3 统一 snake_case |
| 17 | L96 等 | 魔法数散落（240/160、8、5.0、"fight" 等字面量） | Task 2 常量节集中 |
| 18 | L102/L123 | draw() 里注释写"菜单更新帧"（复制粘贴错）；菜单注释"只需要"半句截断——占位注释传递错误信息 | 全重写，注释与实现一致 |
| 19 | L5-7 | 三个全局变量中 `SEED_USED` 无任何写点、`CURRENT_DISTANCE_X` 无读取点——状态传递约定名存实亡 | 沿用三变量并赋予真实读写点（Task 4/8） |
| 20 | 全文件 | 无美术/音效体系、无退出提示、无单位换算约定 | Task 7 资产包 + Task 2 常量 |

## 附录 B：方案自查记录（writing-plans Self-Review）

- **规格覆盖**：星图生成✓(T3/T9)、移动规则与不可重访✓(T5/T8)、x>42 胜利✓(T8/T9)、燃料耗尽失败✓(T8)、引擎三选一✓(T2/T8)、引擎故障✓(T6/T10)、三子系统✓(T6)、战斗流程✓(T6/T10)、升级三永久✓(T5/T11)、被动2✓(T5/T6/T11)、主动4+限次+等级✓(T6/T10/T11)、结算✓(T8/T11)、资产包✓(T7)、MCP 验收✓(T1/T9-12)。PDF 四页无遗漏。
- **占位符扫描**：无 TBD/TODO/"略"；所有代码步骤均为完整可粘贴代码。
- **类型一致性**：`Engine.upgrade_params(pair)`↔`Ship.upgrade_engine(pair)`；`Ship.reachable(points)` 返回 `(类型,x,y)`↔场景 `t[1],t[2]` 取用；`Fight.begin_turn/cast_skill/assign/enemy_turn/_finish` 与场景/测试一致；`events` 标签（ship_hit/win/lose）与 `FightScene.SND_OF_EVENT` 键一致；资产槽位常量（SPR_*/SND_*/MUSIC_BGM）与 make_assets.py 槽位一一对应；测试内 `import star_voyage as sv` 全文件统一。
