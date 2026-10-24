"""star_voyage 纯逻辑层测试：引擎公式 / 星图生成 / 敌人数值 / 飞船升级 / 战斗结算。

同一套测试对【白盒版】与【资产版】各跑一遍（参数化 mod）——
两版唯一的区别是资产层（绘制/发声方式），游戏逻辑必须逐字一致，由本文件强制验证。

运行：python -m pytest test_star_voyage.py -v
"""
import math

import pytest

import star_voyage as sv_white      # 白盒版（手写源）
import star_voyage_assets as sv_a   # 资产版（tools/sync_versions.py 生成）

MODULES = [sv_white, sv_a]          # 两版共用同一套用例


# ---------- 版本一致性 ----------

@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_assets_flag_differs_by_version(mod):
    """USE_ASSETS 标志：白盒 False / 资产 True（两版唯一身份差异）。"""
    assert mod.USE_ASSETS is (mod is sv_a)


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_asset_hooks_exist(mod):
    """资产层三个钩子在两版签名一致（load_assets/draw_sprite/play_sfx）。"""
    for name in ("load_assets", "draw_sprite", "play_sfx"):
        assert callable(getattr(mod, name))


# ---------- 生成器引擎 ----------

@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_sine_engine_default_sequence(mod):
    """正弦波默认参数前 7 项（含 i=4 的 0 与 i=5 的 -1 故障回合）。"""
    eng = mod.Engine("正弦波")
    assert [eng.generate() for _ in range(7)] == [8, 8, 4, 0, -1, 2, 7]


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_geometric_engine_default_sequence(mod):
    """等比数列默认参数前 6 项：奇数回合固定为负（风险与回报）。"""
    eng = mod.Engine("等比数列")
    assert [eng.generate() for _ in range(6)] == [-2, 3, -3, 5, -4, 6]


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_chaos_engine_default_sequence(mod):
    """迭代混沌默认参数前 5 项：N0=4 起步的确定混沌序列。"""
    eng = mod.Engine("迭代混沌")
    assert [eng.generate() for _ in range(5)] == [-4, 7, 6, 0, 2]


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_unknown_engine_raises(mod):
    """未知引擎名必须抛 ValueError（拼写保护，宁崩勿默跑）。"""
    with pytest.raises(ValueError):
        mod.Engine("柴油发动机")


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_engine_reset_restarts_sequence(mod):
    """reset 后序列从头开始（每场战斗重置的依据）。"""
    eng = mod.Engine("迭代混沌")
    first = [eng.generate() for _ in range(3)]
    eng.reset()
    assert [eng.generate() for _ in range(3)] == first


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_engine_upgrade_multiplies_two_params(mod):
    """引擎改造：所选两个参数各 x1.1，第三个不动。"""
    eng = mod.Engine("正弦波")
    eng.upgrade_params("AB")
    assert (eng.A, eng.B, eng.C) == pytest.approx((5.5, 1.1, 4.0))
    eng2 = mod.Engine("等比数列")
    eng2.upgrade_params("BC")
    assert (eng2.A, eng2.B, eng2.C) == pytest.approx((1.0, 2.2, 1.32))


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_engine_preview_matches_generate(mod):
    """preview 与实战 generate 逐项一致（三种引擎），且不推进自身状态。"""
    for name in ("正弦波", "等比数列", "迭代混沌"):
        eng = mod.Engine(name)
        pre = eng.preview(6)                  # 战斗界面函数图像的数据源
        live = [eng.generate() for _ in range(6)]
        assert pre == live                    # 预览必须与实战序列一致
        assert eng.turn == 6                  # preview 不能推进引擎状态
        eng.reset()                           # 每场战斗从 reset 态起算
        assert eng.preview(6) == live         # reset 后预览仍一致（战斗视角）


# ---------- 星图 ----------

@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_starmap_deterministic_per_seed(mod):
    """同种子星图完全一致（种子 S 决定一切）。"""
    assert mod.StarMap(42).points == mod.StarMap(42).points


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_starmap_point_counts(mod):
    """三类兴趣点数量：星球 12 + 敌人 15 + 升级 15。"""
    pts = mod.StarMap(815).points
    types = [t for t, _, _ in pts]
    assert types.count("星球") == 12
    assert types.count("敌人") == 15
    assert types.count("升级") == 15


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_starmap_formula_spot_check_seed42(mod):
    """S=42 手工代入公式的每类第一个点（S/10=4.2）。"""
    m = mod.StarMap(42)
    assert m.points[0] == ("星球", 2, 3)     # 3+sin(5.2), 3+cos(4.2)
    assert m.points[12] == ("敌人", 3, -2)   # 3.5+2cos(4.2), 2.5+5sin(4.2)
    assert m.points[27] == ("升级", 0, 1)    # 3+3sin(5.2), 3.2+3sin(4.2)


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_starmap_coordinates_are_integers(mod):
    """坐标一律四舍五入成整数（文档绘制建议）。"""
    for _, x, y in mod.StarMap(7).points:
        assert isinstance(x, int)
        assert isinstance(y, int)


# ---------- 敌人 ----------

@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_enemy_stats_from_x(mod):
    """敌人数值公式：HP=8+⌊x/2⌋，ATK=1+⌊x/10⌋，DEF=⌊|x|/4⌋。"""
    e = mod.Enemy(10)
    assert (e.max_hp, e.atk, e.defence) == (13, 2, 2)
    e2 = mod.Enemy(42)
    assert (e2.max_hp, e2.atk, e2.defence) == (29, 5, 10)


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_enemy_sets_current_distance_x(mod):
    """Enemy 构造会把自身坐标同步到全局 CURRENT_DISTANCE_X（骨架约定）。"""
    mod.Enemy(30)
    assert mod.CURRENT_DISTANCE_X == 30


# ---------- 飞船 ----------

@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_ship_initial_state(mod):
    """开局飞船：HP8 / 移动 5cm / 无护盾能量 / 位于已探索的原点。"""
    p = mod.Ship("正弦波")
    assert p.hp == 8
    assert p.max_move_dis == 5.0
    assert p.shield == 0 and p.energy == 0
    assert p.visited == {(0, 0)}


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_reachable_excludes_visited_and_far(mod):
    """可达筛选：排除已探索点与超出移动力的点。"""
    p = mod.Ship("正弦波")
    pts = [("星球", 3, 3), ("敌人", 20, 0), ("升级", 3, -3)]
    p.visited.add((3, 3))
    r = p.reachable(pts)
    assert ("星球", 3, 3) not in r          # 已探索不可重访
    assert ("敌人", 20, 0) not in r         # 20cm 超出 5cm 移动力
    assert ("升级", 3, -3) in r


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_move_to_marks_visited(mod):
    """移动即落点入已探索集合。"""
    p = mod.Ship("正弦波")
    p.move_to(3, 3)
    assert p.x == 3 and p.y == 3
    assert (3, 3) in p.visited


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_ship_upgrades(mod):
    """五种升级入口：远航/子系统/主动技能（封顶 Lv3）/被动。"""
    p = mod.Ship("正弦波")
    p.upgrade_sail()
    assert p.max_move_dis == 5.5
    p.upgrade_subsystem("火炮")
    assert p.bonus["火炮"] == 2
    for _ in range(5):
        p.gain_or_upgrade_skill("火力过载")
    assert p.skills["火力过载"] == 3         # 反复升级封顶 Lv3
    p.gain_passive("能量回收")
    assert "能量回收" in p.passives


# ---------- 战斗 ----------

def fight_with(mod, xe=10, engine="正弦波"):
    """便捷构造：一艘指定引擎的飞船迎战 xe 处敌人。"""
    p = mod.Ship(engine)
    return p, mod.Fight(p, xe)


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_fight_initializes_battle_state(mod):
    """开战初始化：敌人数值就绪、护盾/限用清空、回合号 0。"""
    p, f = fight_with(mod, 10)
    assert f.enemy.max_hp == 13
    assert p.shield == 0
    assert p.used_skills == set()
    assert f.turn_no == 0


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_first_turn_detects_fault(mod):
    """首回合出力与故障判定：正弦 N1=8 正常；等比 N1=-2 故障。"""
    _, f = fight_with(mod, 10, "正弦波")
    f.begin_turn()
    assert f.ni == 8 and not f.fault
    p2, f2 = fight_with(mod, 10, "等比数列")
    f2.begin_turn()
    assert f2.ni == -2 and f2.fault


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_assign_blocked_on_fault(mod):
    """故障回合分配出力被拒绝（返回错误原因）。"""
    _, f = fight_with(mod, 10, "等比数列")
    f.begin_turn()                            # N=-2 -> 故障
    assert f.assign("火炮") is not None


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_cannon_battle_to_victory(mod):
    """全火炮速胜：伤害=攻击-DEF，敌人 HP 归零即胜，能量清零。"""
    p, f = fight_with(mod, 10)                # 敌 HP13 DEF2 ATK2
    f.begin_turn()                            # N=8
    f.assign("火炮")                          # dmg 6 -> 敌 7
    assert f.enemy.hp == 7
    f.enemy_turn()                            # 玩家 8->6，自动开回合2
    assert p.hp == 6
    f.assign("火炮")                          # dmg 6 -> 敌 1
    assert f.enemy.hp == 1 and not f.over
    f.enemy_turn()                            # 自动开回合3
    f.assign("火炮")                          # N=4, dmg 2 -> 敌死
    assert f.over and f.win
    assert p.energy == 0                      # 无半衰期循环 -> 清零


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_shield_absorbs_before_hp(mod):
    """敌人伤害优先由护盾承受，耗尽才扣 HP。"""
    p, f = fight_with(mod, 42, "正弦波")      # xe=42: ATK 5
    f.begin_turn()                            # N=8
    f.assign("护盾")                          # 护盾 8
    f.enemy_turn()
    assert p.shield == 3 and p.hp == 8


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_energy_assignment_with_system_bonus(mod):
    """能量分配吃子系统升级加成（+2/级）。"""
    p, f = fight_with(mod, 10)
    p.upgrade_subsystem("能量")
    f.begin_turn()
    f.assign("能量")
    assert p.energy == 10                     # 8 + 2


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_recycle_passive_triggers_on_damage(mod):
    """被动·能量回收：火炮造成伤害立刻 +2 能量。"""
    p, f = fight_with(mod, 10)
    p.gain_passive("能量回收")
    f.begin_turn()
    f.assign("火炮")
    assert p.energy == 2


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_half_life_keeps_half_energy(mod):
    """被动·半衰期循环：战斗结束保留一半能量（向下取整）。"""
    p, f = fight_with(mod, 10)
    p.gain_passive("半衰期循环")
    p.energy = 5
    f._finish(True)
    assert p.energy == 2                      # ⌊5/2⌋


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_events_recorded_for_scene(mod):
    """事件标签：受击发 ship_hit、胜利发 win（场景据此播音效）。"""
    p, f = fight_with(mod, 10)
    f.begin_turn()
    f.assign("护盾")
    f.enemy_turn()
    assert f.events == ["ship_hit"]
    f.events.clear()
    f._finish(True)
    assert f.events == ["win"]


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_overload_doubles_ni(mod):
    """火力过载 Lv1：耗 3 能量，本回合 Ni 翻倍。"""
    p, f = fight_with(mod, 10, "正弦波")
    p.energy = 3
    p.skills["火力过载"] = 1
    f.begin_turn()
    assert f.cast_skill("火力过载") is None
    assert f.ni == 16 and p.energy == 0


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_skill_once_per_fight(mod):
    """每种主动技能每场战斗限用一次。"""
    p, f = fight_with(mod, 10, "正弦波")
    p.energy = 99
    p.skills["应急护盾"] = 1
    f.begin_turn()
    f.cast_skill("应急护盾")
    assert f.cast_skill("应急护盾") is not None   # 第二次被拒


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_skill_cost_scales_with_level(mod):
    """火力过载 Lv2 消耗降为 2。"""
    p, f = fight_with(mod, 10, "正弦波")
    p.skills["火力过载"] = 2
    p.energy = 5
    f.begin_turn()
    f.cast_skill("火力过载")
    assert p.energy == 3 and f.ni == 16


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_emergency_shield_clears_then_grants(mod):
    """应急护盾 Lv3：先清零再 +6（不是叠加）。"""
    p, f = fight_with(mod, 10, "正弦波")
    p.shield = 9
    p.energy = 4
    p.skills["应急护盾"] = 3
    f.begin_turn()
    f.cast_skill("应急护盾")
    assert p.shield == 6


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_calibrator_sets_ni_and_clears_fault(mod):
    """输出校准器 Lv2：Ni 强制 6 并解除故障。"""
    p, f = fight_with(mod, 10, "等比数列")
    p.energy = 2
    p.skills["输出校准器"] = 2
    f.begin_turn()                            # N=-2 故障
    assert f.fault
    assert f.cast_skill("输出校准器") is None
    assert f.ni == 6 and not f.fault


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_suppressor_only_usable_on_fault(mod):
    """故障抑制器仅在故障回合可用。"""
    p, f = fight_with(mod, 10, "正弦波")
    p.energy = 3
    p.skills["故障抑制器"] = 1
    f.begin_turn()                            # N=8 非故障
    assert f.cast_skill("故障抑制器") is not None


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_suppressor_converts_fault_to_positive(mod):
    """故障抑制器：|Ni| 作为最终结果，故障解除后可正常分配。"""
    p, f = fight_with(mod, 10, "等比数列")
    p.energy = 3
    p.skills["故障抑制器"] = 1
    f.begin_turn()                            # N=-2
    assert f.cast_skill("故障抑制器") is None
    assert f.ni == 2 and not f.fault
    assert f.assign("火炮") is None


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_fault_turn_can_be_skipped(mod):
    """故障回合可跳过：skip 后敌人行动并开启下一回合（防软锁回归）。"""
    p, f = fight_with(mod, 10, "等比数列")
    f.begin_turn()                            # N=-2 故障
    assert f.skip_fault_turn() is None        # 跳过成功
    assert p.hp == 6                          # 敌 ATK2 已落下
    assert f.turn_no == 2 and not f.fault     # 自动开回合2（N=3 非故障）
    assert f.skip_fault_turn() is not None    # 非故障回合不允许跳过


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_fault_event_and_damage_records(mod):
    """juice 数据源回归：故障判定即发 fault 事件；火炮/敌击记录 last_dmg/last_hit。"""
    _, f = fight_with(mod, 10, "等比数列")
    f.begin_turn()                            # N=-2 故障
    assert f.events == ["fault"]              # 判定瞬间即发（时机修正）
    p2, f2 = fight_with(mod, 10)
    f2.begin_turn()                           # N=8
    f2.assign("火炮")                         # dmg = 8-2 = 6
    assert f2.last_dmg == 6
    f2.enemy_turn()                           # 敌 ATK2，盾 0 -> HP 落 2
    assert f2.last_hit == 2


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_i18n_tables_complete(mod):
    """多语言回归：指南行/报错文案全部有英文对照；各显示名对照表与逻辑键一一对应。"""
    for line, _ in mod.GUIDE_LINES:           # 指南十行必须全部有英文
        assert line in mod.T, f"缺英文对照: {line}"
    for m in ("未拥有该技能", "本场已用过", "引擎未故障", "能量不足",
              "战斗已结束", "非故障回合", "故障：无法分配"):
        assert m in mod.T, f"缺英文对照: {m}"
    assert set(mod.ENGINE_ABC_EN) == set(mod.ENGINE_ABC)   # 图例三引擎齐
    assert set(mod.SKILL_EN) == set(mod.SKILL_COST)        # 技能显示名齐
    assert set(mod.SYS_EN) == set(mod.SYS_LIST)            # 子系统显示名齐
    assert set(mod.POI_EN) == {"星球", "敌人", "升级"}       # 兴趣点显示名齐


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_tr_log_rebuilds_english(mod):
    """战斗流水的显示翻译：中文原文不变，英文按行格式重建（缺格式原样返回）。"""
    mod.LANG = "en"
    try:
        assert mod.tr_log("回合12 N=8") == "T12 N=8"
        assert mod.tr_log("回合3 N=-2【故障】") == "T3 N=-2 FAULT"
        assert mod.tr_log("  火炮 8 → 伤害6") == "  Cannon 8 d6"
        assert mod.tr_log("  敌击2 盾抵0") == "  Hit2 blk0"
        assert mod.tr_log("  Q·火力过载 耗3能") == "  Q·Overload c3"
        assert mod.tr_log("  故障·跳过") == "  Fault skip"
        assert mod.tr_log("胜利！") == "VICTORY!"
        assert mod.tr_log("  未知行") == "  未知行"        # 缺格式：原样返回
    finally:
        mod.LANG = "zh"                       # 复位，避免影响其它用例


@pytest.mark.parametrize("mod", MODULES, ids=["whitebox", "assets"])
def test_player_death_loses(mod):
    """玩家 HP 归零判负：故障回合只能挨打，直至战败。"""
    p, f = fight_with(mod, 2, "迭代混沌")     # xe=2: HP9 ATK1 DEF0
    p.hp = 2
    f.begin_turn()                            # 混沌 N1=-4 故障
    assert f.fault
    f.enemy_turn()                            # 玩家 2->1，自动开回合2 (N=7)
    assert p.hp == 1 and not f.over
    f.assign("火炮")                          # dmg7 -> 敌 HP2
    assert not f.over
    f.enemy_turn()                            # 玩家归零
    assert f.over and not f.win
