from flask import Flask, request, jsonify
import uuid
import random
from shared_logic import Warrior, Archer, Mage, Priest, Somesh, Team, Effect, ACTION_DATA

app = Flask(__name__)

@app.route('/')
def index():
    return "God-Tier Arena Server is Running!"

games = {}

class Game:
    def __init__(self):
        self.id = str(uuid.uuid4())[:6].upper()
        self.t1 = None
        self.t2 = None
        self.turn = 0 # 0 for t1, 1 for t2
        self.status = "WAITING" # WAITING, ACTIVE, FINISHED
        self.last_action = None
        self.log = []

    def to_dict(self):
        return {
            "id": self.id,
            "t1": self.t1.to_dict() if self.t1 else None,
            "t2": self.t2.to_dict() if self.t2 else None,
            "turn": self.turn,
            "status": self.status,
            "last_action": self.last_action,
            "log": self.log[-5:]
        }

    def apply_move(self, player_idx, move_name, target_idx=0):
        if self.status != "ACTIVE": return {"error": "Game not active"}
        if player_idx != self.turn: return {"error": "Not your turn"}

        attacker_team = self.t1 if player_idx == 0 else self.t2
        target_team = self.t2 if player_idx == 0 else self.t1
        
        attacker = attacker_team.get_active_member()
        
        # Determine target
        if move_name in ["Heal", "Blessing", "Purify", "Pray"]:
            target = attacker # Self target
        else:
            # Target active member of opponent
            target = target_team.get_active_member()

        # Resource Check
        cost = ACTION_DATA.get(move_name, {}).get("cost", 0)
        if attacker.resource < cost:
            return {"error": "Not enough resource"}
        
        attacker.resource -= cost
        
        # Calculate Damage/Effect
        damage = 0
        healed = 0
        effect = None
        
        # Logic copied/adapted from game.py
        if move_name == "Slash": damage = int(25 / target.def_mod)
        elif move_name == "Power Strike": damage = int(40 / target.def_mod)
        elif move_name == "Shield Bash": damage = int(20 / target.def_mod)
        elif move_name == "Spin Slash": damage = int(35 / target.def_mod)
        elif move_name == "Quick Shot": damage = int(20 / target.def_mod)
        elif move_name == "Double Arrow": damage = int((15 * 2 * attacker.attack_mod) / target.def_mod)
        elif move_name == "Piercing": damage = int(30 * attacker.attack_mod * 1.5)
        elif move_name == "Cripple": 
            damage = 15
            effect = Effect("Weakness", 2, 0)
        elif move_name == "Fah!!!": damage = 999
        elif move_name == "Magic Bolt": damage = int(25 * attacker.attack_mod / target.def_mod)
        elif move_name == "Fireball": 
            damage = int(40 * attacker.attack_mod / target.def_mod)
            effect = Effect("Burn", 2, 5)
        elif move_name == "Chain": damage = int(25 * attacker.attack_mod / target.def_mod)
        elif move_name == "Drain": 
            damage = int(20 / target.def_mod)
            attacker.resource = min(attacker.max_resource, attacker.resource + 10)
        elif move_name == "Smite": damage = int(20 * attacker.attack_mod / target.def_mod)
        elif move_name == "Judgement": damage = int(35 * attacker.attack_mod / target.def_mod)
        elif move_name == "Holy Nova": damage = int(20 * attacker.attack_mod / target.def_mod)
        elif move_name == "Pray": healed = 30
        elif move_name == "Dixon Myers": damage = int(50 * attacker.attack_mod / target.def_mod)
        elif move_name == "Backsplash": damage = int(32 * attacker.attack_mod / target.def_mod)
        elif move_name == "Diddler": damage = int(50 * attacker.attack_mod / target.def_mod)

        # Apply
        if damage > 0:
            target.hp -= damage
            if effect: target.apply_effect(effect)
        if healed > 0:
            attacker.hp = min(attacker.max_hp, attacker.hp + healed)

        # Update Turn
        self.turn = 1 - self.turn
        
        # Log
        msg = f"{attacker.name} used {move_name}!"
        self.log.append(msg)
        
        # Record Action for Client Replay
        self.last_action = {
            "player": player_idx,
            "move": move_name,
            "damage": damage,
            "healed": healed,
            "effect": effect.to_dict() if effect else None,
            "target_hp": target.hp,
            "attacker_resource": attacker.resource
        }
        
        # Check Win Condition
        if self.t1.is_defeated(): self.status = "FINISHED"; self.log.append("Player 2 Wins!")
        if self.t2.is_defeated(): self.status = "FINISHED"; self.log.append("Player 1 Wins!")

        return {"success": True, "state": self.to_dict()}

@app.route('/create', methods=['POST'])
def create_game():
    data = request.json
    # Expecting t1 selection
    # For simplicity, client sends list of class names e.g. ["Warrior", "Mage"]
    classes = data.get("team", [])
    team_objs = []
    for c in classes:
        if c == "Warrior": team_objs.append(Warrior())
        elif c == "Archer": team_objs.append(Archer())
        elif c == "Mage": team_objs.append(Mage())
        elif c == "Priest": team_objs.append(Priest())
        elif c == "Somesh": team_objs.append(Somesh())
    
    game = Game()
    game.t1 = Team(team_objs)
    games[game.id] = game
    return jsonify({"game_id": game.id})

@app.route('/join', methods=['POST'])
def join_game():
    data = request.json
    game_id = data.get("game_id")
    classes = data.get("team", [])
    
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    
    game = games[game_id]
    if game.status != "WAITING":
        return jsonify({"error": "Game already full"}), 400
        
    team_objs = []
    for c in classes:
        if c == "Warrior": team_objs.append(Warrior())
        elif c == "Archer": team_objs.append(Archer())
        elif c == "Mage": team_objs.append(Mage())
        elif c == "Priest": team_objs.append(Priest())
        elif c == "Somesh": team_objs.append(Somesh())
        
    game.t2 = Team(team_objs)
    game.status = "ACTIVE"
    return jsonify({"success": True, "game_id": game.id})

@app.route('/state/<game_id>', methods=['GET'])
def get_state(game_id):
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    return jsonify(games[game_id].to_dict())

@app.route('/move', methods=['POST'])
def submit_move():
    data = request.json
    game_id = data.get("game_id")
    player_idx = data.get("player_idx")
    move = data.get("move")
    
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
        
    result = games[game_id].apply_move(player_idx, move)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
