# 像素动画 · 库与教程调研

> 背景：`effects_lab.py` 五页效果获用户认可；CRT 外部管线（`crt_shader_lab.py`）验收通过但**暂不接入，留作技术储备**（2026-10-22）。
> 本调研回答用户问题："这种像素化的动画本身，有没有更好用的库？或者教程集合？"
> 调研日期：2026-10-22。

## 0. 结论速览

| 层面 | 有没有"更好用的库"？ | 建议 |
|------|---------------------|------|
| 动画**逻辑**（缓动/震屏/残影/转场） | **没有**。pyxel 生态无专用动画/tween 库（GitHub topics、PyPI 均查无）；Python 通用库只有 PyTweening（纯函数集）可引 | 维持 effects_lab 的手写做法——这就是 pyxel 社区的标准答案；缺缓动曲线从 [easings.net](https://easings.net) 抄一行公式即可 |
| 动画**资产**（逐帧精灵） | **有**。Aseprite / Pixelorama 是专门的像素动画制作工具，帧动画、洋葱皮、实时预览、精灵表导出一条龙 | 需要帧动画时：Pixelorama（免费）画 → 导出 PNG 精灵表 → pyxel `Image.from_image` 载入（**已实测可行，无需转 .pyxres**）→ `blt` 逐帧播放 |
| **教程集合** | 有几处公认的"集大成"资源 | 三大 juice 演讲（原理）+ Lospec 动画专区（最大像素画教程库）+ Saint11 系列（Celeste 美术，特效/角色动画最对口）+ B站中文入门系列 |

## 1. 库的生态调查

### 1.1 pyxel 生态：确认无专用动画库

- [GitHub `topics/pyxel`](https://github.com/topics/pyxel) 与 PyPI 检索：社区仓库集中在**游戏成品**与外围工具（转换器、编辑器、VS Code 插件），没有任何 tween/补间/精灵动画辅助库；pyxel 官方 API（[kitao/pyxel](https://github.com/kitao/pyxel)）也只有 Image/blt/camera 等图元，无动画模块。
- 所以"帧计数 + 缓动函数 + `pyxel.camera` 震屏 + 棋盘抖动伪透明"这套手写法**就是**社区通行做法——`effects_lab.py` 的路线没有落后，也没有现成轮子可换。

### 1.2 Python 通用 tween 库：可引，但收益小

- **[PyTweening](https://pypi.org/project/pytweening)**（Al Sweigart，2024 仍在维护）：30+ 缓动函数的纯函数集合，零依赖、不绑任何引擎，作者有[配套博客教程](https://inventwithpython.com/blog/make-lively-movement-animation-with-pytweenings-tweening-functions.html)。pyxa 里可直接 `pip install pytweening` 用。
- **[Arcade 4.0](https://api.arcade.academy/en/latest/programming_guide/gui/animations.html)**：内建 GUI tween 动画系统（第一个 tween 到交错入场菜单都有），但绑定 Arcade 框架本身，**无法用于 pyxel**，仅供概念参考。
- 结论：effects_lab 已实现 ease_out_cubic / ease_out_back 等核心曲线；偶缺一条曲线时从 [easings.net](https://easings.net) 抄公式（每条=一行数学，站点直接给多语言代码）比引库更轻。**不建议为此加依赖。**

### 1.3 资产制作工具链：真正"更好用"的部分

| 工具 | 价格 | 特点 | 脚本/扩展 |
|------|------|------|-----------|
| [Aseprite](https://www.aseprite.org) | $20（付费） | 像素动画**业界标准**（Celeste、无数独立游戏用它）；帧动画、洋葱皮、实时预览、GIF/精灵表导出 | [Lua 脚本 API](https://www.aseprite.org/api) 很强，社区脚本生态大（如 [mrbrownjeremy/aseprite-scripts](https://github.com/mrbrownjeremy/aseprite-scripts)） |
| [Pixelorama](https://www.oramainteractive.com) | 免费开源（Godot 系） | 最活跃的免费替代品：非破坏性图层效果、图层组混合、裁剪蒙版，动画功能齐全 | GDScript 扩展 |
| [LibreSprite](https://libresprite.github.io) | 免费开源 | Aseprite 2018 年最后一次 GPL 提交的 fork；功能≈老版 Aseprite，维护节奏慢 | 无 |
| Piskel | 免费浏览器 | 轻量在线替代，够用但功能最少 | 无 |

2026 年社区共识：预算允许首选 Aseprite；免费里 Pixelorama 比 LibreSprite 更活跃、功能更多。

### 1.4 桥接实测（本机 pyxel 2.9.9，2026-10-22）

外部 PNG **可以直接**进 pyxel，不需要手工转 .pyxres：

```python
im = pyxel.Image.from_image("sprites.png")   # 整图载入独立 Image
im2 = pyxel.Image(64, 8); im2.load(0, 0, "sprites.png")  # 或载入已有 Image 的指定区域
pyxel.blt(x, y, im, sx, sy, w, h, colkey)    # blt 直传 Image 实例（本项目已验证过的特性）
```

实测证据（`runs/_test_png.png`）：4×2 PNG，上排四个像素分别用 pyxel 默认调色板的精确 RGB（白/红/黄/绿）画，`from_image` 后 `pget` 得索引 `[7, 8, 10, 11]`，与 `pyxel.colors` 完全对应。

**注意**：映射是"最近色匹配"——作画时必须在 Aseprite/Pixelorama 里**锁定同一套 16 色调色板**（两者都支持导入/导出调色板，可从 `palette_lab.py` 选定方案后导出 .hex/.gpl 给画图工具），才能保证像素 1:1 映射不串色。

对本项目的接入点：资产版 `draw_sprite` 钩子从"单帧 blt pyxres 精灵"换成"按帧号 blt 精灵表切片"即可，白盒版继续几何图元，两版逻辑一致不受影响；`make_assets.py` 之后可退居音效生成。

## 2. 教程集合

### 2.1 三大 juice 演讲（动画手法的"原理课"，看这三个就够）

1. **[Juice it or lose it](https://www.youtube.com/watch?v=Fy0aCDmgnxg)**（Martin Jonasson & Petri Purho，2012 Nordic Game Jam）——公认经典：现场把一个光秃秃的 Breakout 逐步加粒子/震屏/动画/音效变成"手感极好"的游戏。effects_lab 六类效果的思路源头基本就是它。
2. **[The Art of Screenshake](https://www.youtube.com/watch?v=AJdEqssNZ-U)**（Jan Willem Nijman，Vlambeer，2013）——用约 30 个渐进改造演示"为什么一个游戏好玩另一个无聊"；有 [GitHub 代码复刻](https://github.com/colinbellino/screenshake)和 [gamedesign.gg 笔记](https://www.gamedesign.gg/knowledge-base/game-design/game-feel-feedback/the-art-of-screenshake-jan-willem-nijman-vlambeer)。
3. **Math for Game Programmers: Juicing Your Games**（GDC）——与前两个并称三件套，偏数学（缓动/弹簧/粒子运动公式）。
   - 三讲合集播放列表：[Fave Game Talks (Juice and Game Feel)](https://www.youtube.com/playlist?list=PL2gEO25pE6dqsPxgajrZSuqutgzZSjnk5)。
   - 反方观点（防过度 juice）：[Indies, resist the urge to 'juice it or lose it'](https://www.gamedeveloper.com/design/video-indies-resist-the-urge-to-juice-it-or-lose-it-)。

### 2.2 Lospec 教程库（像素画最大教程合集）

- 总库：[lospec.com/pixel-art-tutorials](https://lospec.com/pixel-art-tutorials)——数百篇，可按主题/工具/难度筛选。
- 动画专区：[标签页 animation](https://lospec.com/pixel-art-tutorials/tags/animation)、[精灵动画](https://lospec.com/pixel-art-tutorials/sprite-animation)、[跑步循环](https://lospec.com/pixel-art-tutorials/tags/runcycle)。

### 2.3 Saint11 教程系列（与本需求最对口）

[Pedro Medeiros（@saint11）](https://saint11.art/blog/pixel-art-tutorials)——**Celeste 美术**，Studio MiniBoss 成员；每篇是一张 512×512 图解，覆盖角色动画、跑步/走路循环、爆炸、烟雾、光效等，CC 授权。indienova 有授权中文搬运（含"次级像素动画"等进阶篇）。入门系列（Aseprite 基础）见 [saint11.art/pixel_articles](https://saint11.art/pixel_articles)。

### 2.4 缓动速查

**[easings.net](https://easings.net)**——选曲线看动效、直接抄各语言公式（[开源仓库](https://github.com/ai/easings.net)）。写任何 tween 前先来这里挑曲线。

### 2.5 中文资源（B站 / indienova）

- B站**"独立游戏像素画入门教程"系列**：从软件上手到《角色空闲动画》《简单攻击动画》《黑魔法与光魔法特效》《明暗基础》等，与本项目的悬浮/攻击/受击表现直接对口。
- B站[日系像素动画 13 集合集（中文字幕）](https://www.bilibili.com/video/BV1U8LbzJEYb)（2025）。
- [indienova 像素画标签页](https://indienova.com/tag/pixel-art)：saint11 中文授权系列、"一粒像素"教学系列等。

### 2.6 工具大清单

**[magictools](https://github.com/ellisonleao/magictools)**——免费游戏开发工具大全（像素美术、动画、音效、引擎分类），找任何外围工具先翻它。

## 3. 对本项目的落地建议（未实施，供决策）

1. **逻辑层不动**：effects_lab 六类效果已覆盖需求，无库可引也无须引；后续接效果按 `docs/effects_research.md` 的优先级表（1 跳迁残影 → 2 战斗反馈 → 3 转场 → 4 悬浮）。
2. **资产层留一条升级路径**：若某天想给飞船跃迁喷焰、敌人 idle 加"真逐帧动画"，走 Pixelorama（免费）→ PNG 精灵表 → `Image.from_image` → 资产版 `draw_sprite` 逐帧 blt；调色板先用 `palette_lab.py` 定方案再导出给画图工具锁定。
3. **教程对号入座**：跳迁/残影 → Saint11 的光效/拖尾篇；敌人 idle/受击白闪 → B站空闲动画篇 + The Art of Screenshake；缓动手感调参 → easings.net。
