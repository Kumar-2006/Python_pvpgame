import json
import random

# ---------- Base Classes ----------
class Effect:
    def __init__(self, name, duration, value):
        self.name = name
        self.duration = duration
        self.value = value

    def tick(self):
        self.duration -= 1
        return self.duration <= 0


class Character:
    def __init__(self, name, max_hp, resource_type, max_resource):
        self.name = name
        self.hp = max_hp
        self.max_hp = max_hp
        self.resource_type = resource_type
        self.resource = max_resource
        self.max_resource = max_resource
        self.effects = []
        self.attack_mod = 1.0
        self.def_mod = 1.0
        self.forced_target = None

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


# ---------- Specific Classes ----------
class Warrior(Character):
    def __init__(self, name):
        super().__init__(name, 120, "Stamina", 60)

    def slash(self, target):
        if self.resource >= 10:
            self.resource -= 10
            target.hp -= int(25 / target.def_mod)
            print(f"{self.name} slashes {target.name}!")
        else:
            print("Not enough stamina!")

    def power_strike(self, target):
        if self.resource >= 20:
            self.resource -= 20
            target.hp -= int(40 / target.def_mod)
            print(f"{self.name} uses Power Strike!")
        else:
            print("Not enough stamina!")

    def guard(self):
        if self.resource >= 15:
            self.resource -= 15
            self.apply_effect(Effect("Guard", 2, 0))
            print(f"{self.name} enters Guard Stance!")
        else:
            print("Not enough stamina!")

    def taunt(self, target):
        if self.resource >= 10:
            self.resource -= 10
            target.forced_target = self
            print(f"{self.name} taunts {target.name}!")
        else:
            print("Not enough stamina!")


class Archer(Character):
    def __init__(self, name):
        super().__init__(name, 100, "Stamina", 60)

    def quick_shot(self, target):
        if self.resource >= 10:
            self.resource -= 10
            target.hp -= int(20 / target.def_mod)
            print(f"{self.name} fires Quick Shot!")
        else:
            print("Not enough stamina!")

    def double_arrow(self, target):
        if self.resource >= 20:
            self.resource -= 20
            dmg = int((15 * 2 * self.attack_mod) / target.def_mod)
            target.hp -= dmg
            print(f"{self.name} uses Double Arrow!")
        else:
            print("Not enough stamina!")

    def piercing_arrow(self, target):
        if self.resource >= 25:
            self.resource -= 25
            dmg = int(30 * self.attack_mod * 1.5)
            target.hp -= dmg
            print(f"{self.name} fires Piercing Arrow!")
        else:
            print("Not enough stamina!")

    def crippling_shot(self, target):
        if self.resource >= 15:
            self.resource -= 15
            target.hp -= 15
            target.apply_effect(Effect("Weakness", 2, 0))
            print(f"{self.name} cripples {target.name}!")
        else:
            print("Not enough stamina!")


class Mage(Character):
    def __init__(self, name):
        super().__init__(name, 90, "Mana", 80)

    def magic_bolt(self, target):
        if self.resource >= 10:
            self.resource -= 10
            target.hp -= int(25 * self.attack_mod / target.def_mod)
            print(f"{self.name} casts Magic Bolt!")
        else:
            print("Not enough mana!")

    def fireball(self, target):
        if self.resource >= 20:
            self.resource -= 20
            target.hp -= int(40 * self.attack_mod / target.def_mod)
            target.apply_effect(Effect("Burn", 2, 5))
            print(f"{self.name} casts Fireball! {target.name} is burning!")
        else:
            print("Not enough mana!")

    def lightning_chain(self, enemies):
        if self.resource >= 25:
            self.resource -= 25
            for e in enemies:
                e.hp -= int(25 * self.attack_mod / e.def_mod)
            print(f"{self.name} casts Lightning Chain!")
        else:
            print("Not enough mana!")

    def arcane_drain(self, target):
        if self.resource >= 15:
            self.resource -= 15
            target.hp -= int(20 / target.def_mod)
            self.resource = min(self.max_resource, self.resource + 10)
            print(f"{self.name} drains mana from {target.name}!")
        else:
            print("Not enough mana!")


class Priest(Character):
    def __init__(self, name):
        super().__init__(name, 100, "Mana", 80)

    def heal(self, ally):
        if self.resource >= 15:
            self.resource -= 15
            ally.hp = min(ally.max_hp, ally.hp + 30)
            print(f"{self.name} heals {ally.name}!")
        else:
            print("Not enough mana!")

    def blessing(self, ally):
        if self.resource >= 20:
            self.resource -= 20
            ally.apply_effect(Effect("Blessing", 2, 0))
            print(f"{self.name} blesses {ally.name}!")
        else:
            print("Not enough mana!")

    def weakness(self, enemy):
        if self.resource >= 20:
            self.resource -= 20
            enemy.apply_effect(Effect("Weakness", 2, 0))
            print(f"{self.name} weakens {enemy.name}!")
        else:
            print("Not enough mana!")

    def purify(self, ally):
        if self.resource >= 15:
            self.resource -= 15
            ally.effects.clear()
            print(f"{self.name} purifies {ally.name}!")
        else:
            print("Not enough mana!")


# ---------- Team and Game Logic ----------
class Team:
    def __init__(self, members):
        self.members = members

    def alive_members(self):
        return [m for m in self.members if m.is_alive()]

    def is_defeated(self):
        return all(not m.is_alive() for m in self.members)


class Game:
    def __init__(self, team1, team2):
        self.teams = [team1, team2]

    def show_status(self):
        for i, team in enumerate(self.teams, 1):
            print(f"\n--- Team {i} ---")
            for m in team.members:
                print(f"{m.name}: {m.hp}/{m.max_hp} HP | {m.resource}/{m.max_resource} {m.resource_type}")

    def turn(self, attacker, allies, enemies):
        if not attacker.is_alive():
            return
        print(f"\n{attacker.name}'s turn:")
        try:
            if isinstance(attacker, Warrior):
                choice = input("1.Slash 2.Power Strike 3.Guard 4.Taunt: ")
                if choice == "1": attacker.slash(random.choice(enemies.alive_members()))
                elif choice == "2": attacker.power_strike(random.choice(enemies.alive_members()))
                elif choice == "3": attacker.guard()
                elif choice == "4": attacker.taunt(random.choice(enemies.alive_members()))
            elif isinstance(attacker, Archer):
                choice = input("1.Quick 2.Double 3.Pierce 4.Cripple: ")
                if choice == "1": attacker.quick_shot(random.choice(enemies.alive_members()))
                elif choice == "2": attacker.double_arrow(random.choice(enemies.alive_members()))
                elif choice == "3": attacker.piercing_arrow(random.choice(enemies.alive_members()))
                elif choice == "4": attacker.crippling_shot(random.choice(enemies.alive_members()))
            elif isinstance(attacker, Mage):
                choice = input("1.Bolt 2.Fireball 3.Chain 4.Drain: ")
                if choice == "1": attacker.magic_bolt(random.choice(enemies.alive_members()))
                elif choice == "2": attacker.fireball(random.choice(enemies.alive_members()))
                elif choice == "3": attacker.lightning_chain(enemies.alive_members())
                elif choice == "4": attacker.arcane_drain(random.choice(enemies.alive_members()))
            elif isinstance(attacker, Priest):
                choice = input("1.Heal 2.Bless 3.Weakness 4.Purify: ")
                if choice == "1": attacker.heal(random.choice(allies.alive_members()))
                elif choice == "2": attacker.blessing(random.choice(allies.alive_members()))
                elif choice == "3": attacker.weakness(random.choice(enemies.alive_members()))
                elif choice == "4": attacker.purify(random.choice(allies.alive_members()))
        except Exception as e:
            print(f"Error: {e}")

    def play(self):
        while True:
            self.show_status()
            for i in range(2):
                for attacker in self.teams[i].alive_members():
                    self.turn(attacker, self.teams[i], self.teams[1 - i])
                    for team in self.teams:
                        for member in team.alive_members():
                            member.update_effects()
                            member.regen_resource()
                    if self.teams[1 - i].is_defeated():
                        print(f"\nTeam {i+1} wins!")
                        self.save_results(f"Team {i+1}")
                        return

    def save_results(self, winner):
        try:
            data = {"winner": winner}
            with open("results.json", "w") as f:
                json.dump(data, f)
            print("Game results saved.")
        except Exception as e:
            print(f"File save error: {e}")


# ---------- Example Game ----------
if __name__ == "__main__":
    t1 = Team([Warrior("Ares"), Priest("Luna")])
    t2 = Team([Mage("Pyra"), Archer("Rin")])
    g = Game(t1, t2)
    g.play()