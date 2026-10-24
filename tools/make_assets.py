"""程序化生成 assets/star_voyage.pyxres —— 本脚本是资产的"源头"。

产出内容（与 star_voyage_assets.py 常量节的槽位约定一一对应）：
  图像库0 顶部一排 8x8 精灵：(0,0)飞船 (8,0)星球 (16,0)敌人 (24,0)升级
  音效槽 0-7：光标/火炮/护盾/能量/受击/击破/胜利/失败
  音效槽 8-11：菜单 BGM 四个乐句（音乐0 = 单通道按 8->9->10->11 顺序循环）
  音效槽 12：故障警报（判定瞬间即响，见 Fight.begin_turn 的 fault 事件）
  音效槽 13-18：反馈补齐（输入滴答/确认/跳迁/落地/升级获得/战斗警报）
  音效槽 19-27：分场景 BGM 乐句（音乐1=地图 音乐2=战斗 音乐3=结算）
  音乐槽 0-3：菜单/地图/战斗/结算 BGM（App.change_scene 经 play_bgm 切换）

运行（无窗口）: python tools/make_assets.py
人工润色: pyxel edit assets/star_voyage.pyxres
注意：重跑本脚本会覆盖 .pyxres 中的人工编辑；
润色后请把结果反向誊回本脚本的 SPRITES/SOUNDS 表，或以编辑稿为准不再重跑。
"""
import os

import pyxel

# 输出路径：随本脚本定位 <项目>/assets/star_voyage.pyxres
OUT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "star_voyage.pyxres"))

# ---- 8x8 精灵表：每字符一个调色板色号(0-f)，'0' 在 blt 色键 0 下视为透明 ----
# 常用色号：0透明/黑 3墨绿 7白 8红 9橙 10黄 11亮绿
SPRITES = {
    # 飞船：白色箭形机身，右上一格 6 号浅灰当驾驶舱高光
    "ship": (0, ["00070000",
                 "00777700",
                 "07777776",
                 "00777700",
                 "00070000",
                 "00000000",
                 "00000000",
                 "00000000"]),
    # 星球：墨绿圆面 + 亮绿高光（对应白盒版的绿圆）
    "planet": (8, ["00333300",
                   "0333b330",
                   "333bb333",
                   "3b333333",
                   "33333333",
                   "33333333",
                   "03333330",
                   "00333300"]),
    # 敌人：红色箭头/三角造型，中带一条白色"眼"
    "enemy": (16, ["00008000",
                   "00088000",
                   "00877800",
                   "08777780",
                   "88888888",
                   "00000000",
                   "00000000",
                   "00000000"]),
    # 升级点：橙框黄芯的方块（对应白盒版的黄方块）
    "upgrade": (24, ["99999999",
                     "9aaaaaa9",
                     "9aa99aa9",
                     "9aa99aa9",
                     "9aaaaaa9",
                     "99999999",
                     "00000000",
                     "00000000"]),
}

# ---- 音效表：槽位 -> (音名序列, 音色, 音量, 效果, 速度) ----
# 音色 t三角 s方波 p脉冲 n噪声；效果 n无 f淡出；速度越大越慢（120 时一音=1秒）
SOUNDS = {
    0: ("c4", "s", "3", "n", 5),                 # 光标：短促滴答
    1: ("c3g3", "n", "5", "f", 8),               # 火炮：噪声下坠
    2: ("c3e3", "t", "4", "n", 10),              # 护盾：三角双音上扬
    3: ("e4b4", "p", "3", "n", 8),               # 能量：脉冲高音
    4: ("c2", "n", "6", "f", 12),                # 受击：低噪声闷响
    5: ("c4e4g4", "s", "4", "f", 12),            # 击破：上行三连音
    # 注意：音符域上限 b4（编号59），勿写 c5/d5
    6: ("c4e4g4b4g4b4", "s", "4", "n", 15),      # 胜利：欢快琶音
    7: ("c3g2c2", "t", "4", "f", 20),            # 失败：下行低音
    8: ("c2c2g2c2", "t", "3", "n", 30),          # BGM 乐句1：低音铺底
    9: ("e4g4a4g4", "s", "2", "n", 30),          # BGM 乐句2：主旋律a
    10: ("f4a4c4a4", "s", "2", "n", 30),         # BGM 乐句3：主旋律b
    11: ("g4b4d4b4", "s", "2", "n", 30),         # BGM 乐句4：主旋律c
    12: ("d2b1d2b1", "s", "6", "n", 9),          # 故障警报：方波低音两声鸣响
    # ---- 反馈音效补齐（13-18；见 docs/juice_reference.md 阶段二） ----
    13: ("b4", "p", "3", "n", 4),                # 菜单输入滴答（T1）
    14: ("c4e4", "t", "4", "n", 10),             # 开局/启航确认（T3）
    15: ("g3b4", "p", "4", "f", 8),              # 跳迁起跳引擎（T2）
    16: ("c2", "n", "5", "f", 9),                # 落地闷响（T2）
    17: ("e4g4b4", "s", "4", "n", 10),           # 升级获得（T2）
    18: ("b4b4e4b4", "s", "6", "n", 7),          # 战斗开场警报（T3）
    # ---- 分场景 BGM 乐句（19-27；音乐1=地图 2=战斗 3=结算，音符上限 b4） ----
    19: ("c3g3e3g3", "t", "2", "n", 28),         # 地图：低音铺底（舒缓探索）
    20: ("c4e4g4e4", "s", "2", "n", 28),         # 地图：旋律a
    21: ("f4a4g4e4", "s", "2", "n", 28),         # 地图：旋律b
    22: ("a2a2e2a2", "s", "3", "n", 14),         # 战斗：低音驱动（紧凑小调）
    23: ("a3c4e4c4", "s", "3", "n", 14),         # 战斗：紧迫旋律a
    24: ("d4f4a4f4", "s", "3", "n", 14),         # 战斗：紧迫旋律b
    25: ("c3e3g3", "t", "2", "n", 30),           # 结算：和弦长音（安宁尾奏）
    26: ("g3b3d4", "t", "2", "n", 30),           # 结算：尾声
    27: ("c4g3", "t", "2", "n", 30),             # 结算：回落收束
}


def build_images():
    """把精灵表逐行写入图像库0（set 直接接受字符串行列表）。"""
    img = pyxel.images[0]
    img.cls(0)                       # 先清成全 0（透明/黑）
    for _, (x, rows) in SPRITES.items():   # 表内已带各自的目标 x 偏移
        img.set(x, 0, rows)          # 8 行字符串 = 8x8 像素


def build_sounds():
    """把音效表逐槽写入 sounds，并组装四首音乐（0=菜单 1=地图 2=战斗 3=结算）。"""
    for n, (notes, tone, vol, eff, speed) in SOUNDS.items():
        pyxel.sounds[n].set(notes, tone, vol, eff, speed)
    pyxel.musics[0].set([8, 9, 10, 11])      # 通道0 依次播放四个乐句后循环
    pyxel.musics[1].set([19, 20, 21])        # 地图 BGM
    pyxel.musics[2].set([22, 23, 24])        # 战斗 BGM
    pyxel.musics[3].set([25, 26, 27])        # 结算 BGM


def self_check():
    """断言资产内容与槽位约定一致（保存前后各跑一次）。"""
    assert pyxel.images[0].pget(0, 0) == 0    # 飞船左上角应为透明
    assert pyxel.images[0].pget(3, 2) == 7    # 飞船机身应为白
    assert pyxel.images[0].pget(19, 3) == 7   # 敌机白色"眼"带
    assert pyxel.images[0].pget(28, 1) == 10  # 升级方块黄色芯（第2行中段）
    assert pyxel.sounds[0].notes[0] > 0       # 音效0 已有音符
    assert pyxel.sounds[12].notes[0] > 0      # 故障警报（音效12）已有音符
    assert pyxel.sounds[13].notes[0] > 0      # 反馈音效补齐（13-18 起点）
    assert pyxel.sounds[18].notes[0] > 0
    assert pyxel.sounds[19].notes[0] > 0      # 分场景 BGM 乐句（19-27 起点）
    assert pyxel.sounds[27].notes[0] > 0
    assert pyxel.musics[0].seqs[0] == [8, 9, 10, 11]  # BGM 序列正确
    assert pyxel.musics[1].seqs[0] == [19, 20, 21]    # 地图 BGM
    assert pyxel.musics[2].seqs[0] == [22, 23, 24]    # 战斗 BGM
    assert pyxel.musics[3].seqs[0] == [25, 26, 27]    # 结算 BGM
    print("self-check ok")


def main():
    """无窗口构建全部资产 -> 存 .pyxres -> 重载回读二次自检。"""
    pyxel.init(240, 160, title="make_assets", headless=True)  # 无窗口初始化
    build_images()
    build_sounds()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)  # 确保 assets/ 存在
    pyxel.save(OUT)                    # 写出 .pyxres（官方资源包格式）
    self_check()
    pyxel.load(OUT)                    # 重新加载：验证保存-加载回路
    self_check()
    print("written:", OUT)


if __name__ == "__main__":
    main()
