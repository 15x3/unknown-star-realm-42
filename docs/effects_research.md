# 像素游戏 Juicy 效果调研 + 效果实验室说明

> 配套演示：`python effects_lab.py`（←→ 或数字键 1-6 翻页；本脚本是**调研演示**，未接入游戏本体）。
> 逐页快照证据：`runs/lab_p1_*.png` ~ `lab_p6_*.png`。

## 0. 调研结论摘要（先看这个）

- "Juice"的核心不是加动画，而是**对玩家每一个输入给出多层即时反馈**：位移反馈（震屏/击退）、时间反馈（顿帧）、色彩反馈（白闪/闪红）、数字反馈（伤害数字）。业界共识参数：震屏持续 **80~300ms**、白闪**要快要淡**、避免长闪光与频闪。
- CRT 后处理的经典四件套 = **扫描线 + 荫罩(aperture grille/slotmask) + 桶形弯曲 + 暗角**（RetroArch 的 crt-geom / crt-royale 系是标杆实现）；亮度变暗是最大痛点，参数要克制。
- pyxel 2.9.9 的硬约束决定了实现风格：
  - **无透明度** → 半透明用"棋盘抖动"（隔点绘制）模拟，这是像素游戏的标准做法；
  - **无 shader** → CRT 用**预生成叠加层 + 每帧 1 次 blt**（启动时算一次，运行零成本）；
  - **有 `pyxel.camera()`** → 震屏一行代码搞定，用完记得复位；
  - **无椭圆图元**（没有 oval/ellip）→ 用 3 行矩形拼像素椭圆。

## 1. 六类效果 · 技法清单 · 实验室页 · 接入候选

### ① 过场转场（实验室页1：淡入淡出/光圈开合/条带擦除/白闪）
- 常用技法：fade（色阶阶梯渐变，非连续渐变——保持像素感）、iris/circle wipe（星球大战式）、
  条带擦除（竖条错峰翻面）、push/slide、白闪。
- 接入候选：**场景切换时**（菜单→地图、战斗胜利回地图、结算）。地图跳迁"起跳/落地"各一次小 flash 也常见。
- 成本：低。给 `App.change_scene` 挂一个 20~30 帧的转场状态即可（转场期间冻结输入）。
- 风险：回合制游戏节奏慢，转场别超过 0.5s，否则烦。

### ② 攻击表现（页2：斩击弧线/枪口闪光/弹道拖尾）
- 常用技法：3~5 帧的斩击弧（残迹渐隐）、muzzle flash（2 帧高亮）、弹道拖尾（历史位置渐变色阶）。
- 接入候选：**战斗场景按 [1] 火炮时**——出力 Ni 越大弧线越长/颜色越亮，是"引擎出力可视化"的免费载体；
  敌人被击破时放小型粒子爆散。
- 成本：中低。Fight 已有 `events` 事件总线（ship_hit/kill/win/lose），表现层挂事件即可，逻辑零改动。

### ③ 受击表现（页3：白闪/击退/伤害数字/顿帧/震屏）
- 常用技法：白闪（整体换白色剪影 2~3 帧）、击退（ease-out-back 过冲回弹）、伤害数字（上飘+色序渐变）、
  **hitstop 顿帧**（冻结 2~4 帧，重击感的最廉价来源）、震屏（半径 1~3px、8 帧内衰减）。
- 接入候选：**敌人回合敌人攻击我方**（ FightScene 的 ship_hit 事件）——飞船侧白闪+震屏；
  我方火炮命中时敌人白闪+伤害数字（数字就用 Ni 实际伤害，UI 已有数据）。
- 成本：低~中。顿帧实现=事件后跳过若干帧 update（注意：pyxel-mcp 验收脚本要容忍冻结帧）。
- 风险：顿帧+震屏叠加过量会晕，先各用最轻参数。

### ④ 悬浮表现（页4：正弦浮动/影子缩放/待机呼吸）
- 常用技法：`y += sin(t)·A` 浮动、地面影子随高度反向缩放（廉价的高度/重量感）、尺寸 ±1 待机呼吸。
- 接入候选：**地图场景的兴趣点**（星球/敌人/升级方块各自不同相位浮动）、选中目标的呼吸光环已有雏形
  （`circb` 闪烁），可升级为"选中点悬浮+影子"。
- 成本：低。纯 draw 层改动。

### ⑤ 移动残影（页5：色阶渐隐 + 棋盘抖动透明）
- 常用技法：历史位置环形缓冲（最近 N 帧），旧的用更暗色阶 + 更稀疏抖动（50%/25% 密度）模拟透明。
- 接入候选：**地图跳迁动画**——目前飞船是瞬移，可改为 8~12 帧的"跃迁线"（起点到终点直线插值+残影），
  落点小闪光。这是当前游戏"最不 juicy"的环节，优先级最高。
- 成本：中。需要在 MapScene 加一个 jump 动画状态（期间锁输入），残影直接复用页5代码。

### ⑥ CRT 后处理 —— 第四期：外部管线方案（`crt_shader_lab.py`，**验收通过·暂不接入·技术储备**）
- **用户结论（2026-10-22）**：观感过关，但暂不接入游戏，作为技术储备保存。
- **架构（用户提出）**：pyxel 渲染 → 后处理 shader（OpenCV）→ 用户实际看到的画面。
  pyxel headless 渲染 + `screen.data_ptr` 零拷贝抓帧 → OpenCV 在显示分辨率(3x)做
  全浮点链：桶形失真 → 色差 → 子像素荫栅(RGB 列 1.0/0.5) → 亮度自适应扫描线 →
  高斯泛光 → 圆角暗角；键盘 waitKey → set_btn 回注。实测 17.5ms/帧（30fps 预算内）。
- **为什么这版成了**：荫栅/泛光需要"每游戏像素覆盖多显示像素"的余量——3x 放大
  下的浮点运算给了这个物理空间，且不受 16 色量化约束（扫描线暗区 -33%/亮区 -8%
  连续可变；荫栅逐列精确 (238,119,119)；泛光太阳外圈 230→253，全部实测值）。
- 第三期（crt_lab.py，pyxel 原生 LUT）与更早叠加层方案均被否决，仅存档。
- 若接入游戏：架构与具体游戏无关（外部驱动 update/draw + set_btn），包一层
  star_voyage 即可；代价是游戏窗口换成 OpenCV 窗口（截图/录屏方式随之改变）。

## 2. 接入优先级与状态（2026-10-22 更新：用户白盒标注 13 处需求已实现）

| 优先 | 效果 | 状态 |
|------|------|------|
| 1 | 地图跳迁动画+残影（⑤+①微量） | **已接入**：两段动画（飞船 ease-out 飞行+pal 残影 → 摄像机平滑跟随） |
| 2 | 战斗反馈（③+②） | **已接入**：分配 5 帧顿帧+行高亮、技能名 16px 横穿横幅、故障跳过红闪≈0.5s+音效12、结束背景压暗；白闪/震屏/伤害数字未接（用户未标注） |
| 3 | 场景转场（①） | **已接入**：fade（菜单/地图/升级）+ iris（战斗离场）+ 白闪两下+光圈（进战斗），`App._trans` 状态机 |
| — | 引擎函数图像（用户新增标注） | **已接入**：战斗右上 Ni-i 曲线+当前回合白点（`Engine.preview()`） |
| 4 | 悬浮（④） | 未接（用户标注未要求，保留候选） |
| ~~5~~ | ~~CRT（⑥）~~ | **四期调研完结**：观感过关但暂不接入，`crt_shader_lab.py` 留作技术储备 |

## 3. 主要参考来源

- Game feel/juice 技法：[Egmatic: How to Make Your Game Feel Good](https://egmatic.com/blog/how-to-make-your-game-feel-good)、
  [Anton Slashcev 的 juice tips](https://www.linkedin.com/posts/aslashcev_game-juice-tips-together-with-mykola-we-activity-7438539466798989312-WKGt)、
  [Resprawn (Medium)](https://resprawn.medium.com/when-you-play-a-great-game-it-feels-good-d23761b6eccf)、
  [GameAnalytics: Squeezing More Juice](https://gameanalytics.com/blog/squeezing-more-juice-out-of-your-game-design)、
  [Dawnosaur: 7 Game Feel Tricks](https://dawnosaur.substack.com/p/7-game-feel-tricks-to-improve-your)
- CRT shader：[Libretro 论坛 CRT 展示帖](https://forums.libretro.com/t/19193)、
  [things i play: RetroArch CRT shader showcase](https://thingsiplay.game.blog/2022/03/08/crt-shader-showcase-for-retroarch)、
  [Babylon.js: Retro CRT Shader 研究](https://babylonjs.medium.com/retro-crt-shader-a-post-processing-effect-study-1cb3f783afbc)、
  [Godot Shaders: CRT Lite](https://godotshaders.com/shader/crt-lite-scanlines-curved-glass-and-vignette)、
  [r/emulation：CRT 滤镜亮度问题讨论](https://www.reddit.com/r/emulation/comments/af9low/an_observation_about_crt_shaders_and_color)
