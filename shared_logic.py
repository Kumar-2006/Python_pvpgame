import random

# ---------- Base Logic Classes ----------
class Effect:
    def __init__(self, name, duration, value):
        self.name = name
        self.duration = duration
        self.value = value

    def tick(self):
        self.duration -= 1
        return self.duration <= 0

    def to_dict(self):
        return {"name": self.name, "duration": self.duration, "value": self.value}

    @staticmethod
    def from_dict(data):
        return Effect(data["name"], data["duration"], data["value"])

class Character:
    def __init__(self, name, max_hp, resource_type, max_resource, sprite_key):
        self.name = name
        self.hp = max_hp
        self.max_hp = max_hp
        self.resource_type = resource_type
        self.resource = max_resource
        self.max_resource = max_resource
        self.effects = []
        self.attack_mod = 1.0
        self.def_mod = 1.0
        self.sprite_name = sprite_key
        
        # Visual/Client-side attributes (ignored by server logic but kept for compatibility)
        self.animation_offset = 0
        self.animation_speed = 0.1
        self.hover_y = 0
        self.x = 0
        self.y = 0
        self.target_x = 0
        self.shake_timer = 0
        self.float_amp = 5
        self.y_offset = 0
        self.current_sprite_override = None
        self.hit_pause_timer = 0
        self.pending_bash_target = None
        self.hit_animation_timer = 0
        self.is_taking_hit = False

    def is_alive(self):
        return self.hp > 0

    def apply_effect(self, effect):
        self.effects.append(effect)

    def update_effects(self):
        expired = []
        for eff in self.effects:
            if eff.name == "Burn":
                self.hp -= eff.value
            elif eff.name == "Blessing":
                self.attack_mod = 1.2
            elif eff.name == "Weakness":
                self.attack_mod = 0.8
            elif eff.name == "Guard":
                self.def_mod = 1.3
            if eff.tick():
                expired.append(eff)
        for eff in expired:
            self.effects.remove(eff)
            if eff.name in ["Blessing", "Weakness"]:
                self.attack_mod = 1.0
            elif eff.name == "Guard":
                self.def_mod = 1.0

    def regen_resource(self):
        self.resource = min(self.max_resource, self.resource + 5)

    def to_dict(self):
        return {
            "type": self.__class__.__name__,
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "resource": self.resource,
            "max_resource": self.max_resource,
            "effects": [e.to_dict() for e in self.effects],
            "attack_mod": self.attack_mod,
            "def_mod": self.def_mod,
            "sprite_name": self.sprite_name
        }

    @staticmethod
    def from_dict(data):
        cls = globals()[data["type"]]
        char = cls()
        char.name = data["name"]
        char.hp = data["hp"]
        char.max_hp = data["max_hp"]
        char.resource = data["resource"]
        char.max_resource = data["max_resource"]
        char.effects = [Effect.from_dict(e) for e in data["effects"]]
        char.attack_mod = data["attack_mod"]
        char.def_mod = data["def_mod"]
        char.sprite_name = data["sprite_name"]
        return char

class Warrior(Character):
    def __init__(self):
        super().__init__("Warrior", 120, "Stamina", 60, "warrior")
    def get_actions(self): return ["Slash", "Power Strike", "Shield Bash", "Spin Slash"]

class Archer(Character):
    def __init__(self):
        super().__init__("Archer", 100, "Stamina", 60, "archer")
    def get_actions(self): return ["Quick Shot", "Double Arrow", "Piercing", "Cripple"]

class Mage(Character):
    def __init__(self):
        super().__init__("Mage", 90, "Mana", 80, "mage")
    def get_actions(self): return ["Magic Bolt", "Fireball", "Chain", "Drain"]

class Priest(Character):
    def __init__(self):
        super().__init__("Priest", 100, "Mana", 80, "priest")
    def get_actions(self): return ["Smite", "Judgement", "Holy Nova", "Pray"]

class Somesh(Character):
    def __init__(self):
        super().__init__("Somesh", 110, "Stamina", 70, "somesh")
    def get_actions(self): return ["Dixon Myers", "Fah!!!", "Backsplash", "Diddler"]

class Team:
    def __init__(self, members):
        self.members = members
        self.active_index = 0
    
    def get_active_member(self):
        if 0 <= self.active_index < len(self.members):
            return self.members[self.active_index]
        return None

    def alive_members(self): return [m for m in self.members if m.is_alive()]
    def is_defeated(self): return all(not m.is_alive() for m in self.members)

    def to_dict(self):
        return {
            "members": [m.to_dict() for m in self.members],
            "active_index": self.active_index
        }

    @staticmethod
    def from_dict(data):
        members = [Character.from_dict(m) for m in data["members"]]
        team = Team(members)
        team.active_index = data["active_index"]
        return team

# Action Data
ACTION_DATA = {
    "Slash": {"cost": 10, "info": "25 Dmg"},
    "Power Strike": {"cost": 20, "info": "40 Dmg"},
    "Shield Bash": {"cost": 15, "info": "20 Dmg"},
    "Spin Slash": {"cost": 25, "info": "35 Dmg"},
    "Quick Shot": {"cost": 10, "info": "20 Dmg"},
    "Double Arrow": {"cost": 20, "info": "30 Dmg"},
    "Piercing": {"cost": 25, "info": "45 Dmg"},
    "Cripple": {"cost": 15, "info": "15+Weak"},
    "Fah!!!": {"cost": 50, "info": "DEATH"},
    "Magic Bolt": {"cost": 10, "info": "25 Dmg"},
    "Fireball": {"cost": 20, "info": "40+Burn"},
    "Chain": {"cost": 25, "info": "25 AoE"},
    "Drain": {"cost": 15, "info": "20+Drain"},
    "Smite": {"cost": 10, "info": "20 Dmg"},
    "Judgement": {"cost": 20, "info": "35 Dmg"},
    "Holy Nova": {"cost": 25, "info": "20 AoE"},
    "Pray": {"cost": 15, "info": "Self Heal"},
    "Dixon Myers": {"cost": 0, "info": "50 Dmg"},
    "Backsplash": {"cost": 0, "info": "32 Dmg"},
    "Diddler": {"cost": 0, "info": "50 AoE"}
}
