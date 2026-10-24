import pyxel

PLAYER_HP = 8
PLAYER_MAX_MOVE_DIS = 5.0
SEED_NOW = 12345
SEED_USED = 67890
CURRENT_DISTANCE_X = 0.0

class Player:
    def __init__(self):
        current_engine = "sin" # sin cos 正弦波 等比数列 迭代混沌
        hp = PLAYER_HP
        max_move_dis = PLAYER_MAX_MOVE_DIS
        pass

    def update(self):
        pass

    def draw(self):
        pass

    def generate(self):
        result = 0
        if self.current_engine == "正弦波":
            # 算法：$$N_i = \lfloor A \cdot \sin(B \cdot i) + C \rfloor$$ 默认参数： $A=5, B=1, C=4$
            return result
        
        elif self.current_engine == "等比数列":
            # 算法：$$N_i = A + \lfloor B \cdot (-C)^i \rfloor$$ 默认参数：$A = 1, B = 2, C = 1.2$
            return result
        
        elif self.current_engine == "迭代混沌":
            # 算法：$$N_0 = AN_i = \lfloor B \cdot \sin(N_{i-1}) + C \rfloor$$ 默认参数：$A=4,B=7,C=2$
            return result
        
        else:
            return None

    def subsystem(text):
        if text == "ATT":
            # 对敌人造成generate()点伤害
            pass
        elif text == "DEF":
            # 对自己生成generate()点护盾
            pass
        elif text == "ENG":
            # 获得generate()点备用能量，但不会超过上限
            pass
        else:
            return None

    def upgrade(text):
        pass

class Enemy:
    def __init__(self):
        self.hp = 8 + (CURRENT_DISTANCE_X / 2)
        self.attack = 1 + (CURRENT_DISTANCE_X / 2)
        self.defence = abs( CURRENT_DISTANCE_X / 4)

    def update(self):
        pass

    def draw(self):
        pass

    def attack(self):
        pass

class Map:
    def __init__(self):
        seed = SEED_NOW
        normalPlanet = []
        enemyPlanet = []
        upgradePlanet = []
        self.generate()
        pass

    def generate(self):
        # 生成地图:
        # 设置好种子后
        # 首先，绘制一个至少50单位长的x轴
        # 然后，在地图上分别绘制三类兴趣点：

        # 普通星球：$(i \in [1,12], i \in N_+)$ $$x_i = 3 \cdot i + \sin(i + \frac{S}{10}), y_i = 3 \cdot i + \cos(\frac{i \cdot S}{10})$

        # 敌人：$(i \in [1,15], i \in N_+)$ $$x_i = 3.5 \cdot i + 2\cos(i \cdot \frac{S}{10}), y_i = 2.5 \cdot i + 5 \cdot \sin(i \cdot \frac{S}{10})$$

        # 升级点：$(i \in [1,15], i \in N_+)$ $$x_i = 3 \cdot i + 3\sin(i + \frac{S}{10}),y_i = 3.2 \cdot i + 3\sin(i \cdot \frac{S}{10})$$
        pass

class App:
    current_scene = "menu"

    def __init__(self):
        pyxel.init(240,160,title="demo")
        self.current_scene = "menu"
        pyxel.run(self.update,self.draw)

    def update(self):
        if self.current_scene == "menu":
            # 菜单更新帧
            # 需要三个按钮，不需要鼠标定位，只需要

            if pyxel.btn():
                self.current_scene == "map"
            elif pyxel.btn():
                self.current_scene == "ending"

            pass
        elif self.current_scene == "map":
            # 地图更新帧
            pass
        elif self.current_scene == "fight":
            # 战斗更新帧
            pass
        elif self.current_scene == "ending":
            # 游戏结算更新帧
            pass

    def draw(self):
        if self.current_scene == "menu":
            # 菜单更新帧
            pass
        elif self.current_scene == "map":
            # 地图更新帧
            pass
        elif self.current_scene == "fight":
            # 战斗更新帧
            pass
        elif self.current_scene == "ending":
            # 游戏结算更新帧
            pass