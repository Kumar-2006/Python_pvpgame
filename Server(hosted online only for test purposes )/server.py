from flask import Flask, request, jsonify
import uuid
import time
from shared_logic import Warrior, Archer, Mage, Priest, Somesh, Team, Effect, ACTION_DATA

app = Flask(__name__)

@app.route('/')
def index():
    return "God-Tier Arena Server v2.0 - Running!"

# In-memory game storage
games = {}

# Helper function to create a team from class list
def create_team(class_list):
    """Create a Team object from a list of class names."""
    members = []
    for class_name in class_list:
        if class_name == "Warrior":
            members.append(Warrior())
        elif class_name == "Archer":
            members.append(Archer())
        elif class_name == "Mage":
            members.append(Mage())
        elif class_name == "Priest":
            members.append(Priest())
        elif class_name == "Somesh":
            members.append(Somesh())
        else:
            # Default to Warrior if unknown
            members.append(Warrior())
    return Team(members)


class Game:
    """Represents a multiplayer game session."""
    
    def __init__(self):
        self.id = str(uuid.uuid4())[:6].upper()
        self.teams = {0: None, 1: None}  # Player idx -> Team
        self.turn = 0  # 0 or 1
        self.status = "WAITING"  # WAITING, ACTIVE, FINISHED
        self.winner = None  # None, 0, or 1
        self.message = ""  # Game outcome message
        self.last_action = None  # Last action for client animation
        self.weather = "Clear"  # Weather setting
        self.last_seen = {0: 0, 1: 0}  # Heartbeat tracking
        
    def to_dict(self):
        """Serialize game state for clients."""
        now = time.time()
        return {
            "id": self.id,
            "teams": {
                "0": self.teams[0].to_dict() if self.teams[0] else None,
                "1": self.teams[1].to_dict() if self.teams[1] else None
            },
            "turn": self.turn,
            "status": self.status,
            "winner": self.winner,
            "message": self.message,
            "last_action": self.last_action,
            "weather": self.weather,
            "players_online": {
                "0": (now - self.last_seen[0]) < 5,
                "1": (now - self.last_seen[1]) < 5
            }
        }
    
    def apply_action(self, player_idx, action_data):
        """
        Process a player action (attack, tag, etc.).
        Returns: {"ok": True/False, "error": "...", "state": {...}}
        """
        # Validate game is active
        if self.status != "ACTIVE":
            return {"ok": False, "error": "Game not active"}
        
        # Validate it's the player's turn
        if player_idx != self.turn:
            return {"ok": False, "error": "Not your turn"}
        
        action_type = action_data.get("type")  # "attack" or "tag"
        
        if action_type == "tag":
            return self._handle_tag(player_idx, action_data)
        elif action_type == "attack":
            return self._handle_attack(player_idx, action_data)
        else:
            return {"ok": False, "error": "Invalid action type"}
    
    def _handle_tag(self, player_idx, action_data):
        """Handle team member switch."""
        new_index = action_data.get("target_index")
        
        if new_index is None:
            return {"ok": False, "error": "No target index provided"}
        
        team = self.teams[player_idx]
        
        # Validate index
        if not (0 <= new_index < len(team.members)):
            return {"ok": False, "error": "Invalid team member index"}
        
        target_member = team.members[new_index]
        
        # Check if target is alive
        if not target_member.is_alive():
            return {"ok": False, "error": "Cannot tag to fallen ally"}
        
        # Perform switch
        team.active_index = new_index
        self.last_action = {
            "player": player_idx,
            "type": "tag",
            "target_index": new_index
        }
        
        # Advance turn
        self._next_turn()
        
        return {"ok": True, "state": self.to_dict()}
    
    def _handle_attack(self, player_idx, action_data):
        """Handle attack action."""
        move_name = action_data.get("move")
        
        if not move_name:
            return {"ok": False, "error": "No move specified"}
        
        if move_name not in ACTION_DATA:
            return {"ok": False, "error": f"Unknown move: {move_name}"}
        
        attacker_team = self.teams[player_idx]
        defender_team = self.teams[1 - player_idx]
        
        attacker = attacker_team.get_active_member()
        
        if not attacker:
            return {"ok": False, "error": "No active attacker"}
        
        # Handle Skip Turn
        if move_name == "Skip Turn":
            self.last_action = {
                "player": player_idx,
                "type": "skip",
                "move": move_name
            }
            # Advance turn
            self._next_turn()
            return {"ok": True, "state": self.to_dict()}
        
        # Determine target
        if move_name in ["Pray"]:
            target = attacker  # Self-target
        else:
            target = defender_team.get_active_member()
            
        if not target:
            return {"ok": False, "error": "No valid target"}
        
        # Check resource cost
        cost = ACTION_DATA[move_name]["cost"]
        if attacker.resource < cost:
            return {"ok": False, "error": "Not enough resource"}
        
        # Deduct resource
        attacker.resource -= cost
        
        # Calculate damage/healing
        damage = 0
        healed = 0
        effect = None
        mana_gain = 0  # Mana/Stamina to restore after attack
        
        # Damage calculations (same as before)
        if move_name == "Slash":
            damage = int(25 / target.def_mod)
            mana_gain = 3
        elif move_name == "Power Strike":
            damage = int(40 / target.def_mod)
            mana_gain = 5
        elif move_name == "Shield Bash":
            damage = int(20 / target.def_mod)
            mana_gain = 4
        elif move_name == "Spin Slash":
            damage = int(35 / target.def_mod)
            mana_gain = 6
        elif move_name == "Quick Shot":
            damage = int(20 / target.def_mod)
            mana_gain = 3
        elif move_name == "Double Arrow":
            damage = int((15 * 2 * attacker.attack_mod) / target.def_mod)
            mana_gain = 5
        elif move_name == "Piercing":
            damage = int(30 * attacker.attack_mod * 1.5)
            mana_gain = 6
        elif move_name == "Cripple":
            damage = 15
            effect = Effect("Weakness", 2, 0)
            mana_gain = 4
        elif move_name == "Fah!!!":
            damage = 999
            mana_gain = 10
        elif move_name == "Magic Bolt":
            damage = int(25 * attacker.attack_mod / target.def_mod)
            mana_gain = 3
        elif move_name == "Fireball":
            damage = int(40 * attacker.attack_mod / target.def_mod)
            effect = Effect("Burn", 2, 5)
            mana_gain = 5
        elif move_name == "Chain":
            damage = int(25 * attacker.attack_mod / target.def_mod)
            mana_gain = 6
        elif move_name == "Drain":
            damage = int(20 / target.def_mod)
            attacker.resource = min(attacker.max_resource, attacker.resource + 10)
        elif move_name == "Smite":
            damage = int(20 * attacker.attack_mod / target.def_mod)
            mana_gain = 3
        elif move_name == "Judgement":
            damage = int(35 * attacker.attack_mod / target.def_mod)
            mana_gain = 5
        elif move_name == "Holy Nova":
            damage = int(20 * attacker.attack_mod / target.def_mod)
            mana_gain = 6
        elif move_name == "Pray":
            healed = 30
            mana_gain = 0  # No gain for self-heal
        elif move_name == "Charged Spark":
            damage = int(50 * attacker.attack_mod / target.def_mod)
            mana_gain = 7
        elif move_name == "Run Man":
            damage = int(35 * attacker.attack_mod / target.def_mod)
            mana_gain = 5
        elif move_name == "Spark":
            damage = int(50 * attacker.attack_mod / target.def_mod)
            mana_gain = 7
        
        # Apply damage
        if damage > 0:
            target.hp -= damage
            if effect:
                target.apply_effect(effect)
        
        # Apply mana/stamina gain from attack
        if mana_gain > 0:
            attacker.resource = min(attacker.max_resource, attacker.resource + mana_gain)
        
        # Apply healing
        if healed > 0:
            attacker.hp = min(attacker.max_hp, attacker.hp + healed)
        
        # Record action for client
        self.last_action = {
            "player": player_idx,
            "type": "attack",
            "move": move_name,
            "damage": damage,
            "healed": healed,
            "target_hp": target.hp
        }
        
        # Check if target died and auto-switch
        if damage > 0 and not target.is_alive():
            switched = False
            for i, member in enumerate(defender_team.members):
                if member.is_alive():
                    defender_team.active_index = i
                    switched = True
                    break
        
        # Check win condition
        if defender_team.is_defeated():
            self.status = "FINISHED"
            self.winner = player_idx
            self.message = f"Player {player_idx + 1} Wins!"
            return {"ok": True, "state": self.to_dict()}
        
        if attacker_team.is_defeated():
            self.status = "FINISHED"
            self.winner = 1 - player_idx
            self.message = f"Player {2 - player_idx} Wins!"
            return {"ok": True, "state": self.to_dict()}
        
        # Advance turn
        self._next_turn()
        
        return {"ok": True, "state": self.to_dict()}
    
    def _next_turn(self):
        """Advance to next player's turn and regenerate resources."""
        self.turn = 1 - self.turn
        team = self.teams[self.turn]
        attacker = team.get_active_member()
        
        if attacker:
            # Update effects (Burn damage, duration ticks, etc.)
            attacker.update_effects()
            
            # Check if attacker died from effects (e.g. Burn)
            if not attacker.is_alive():
                # Try to switch to another living member
                switched = False
                for i, member in enumerate(team.members):
                    if member.is_alive():
                        team.active_index = i
                        switched = True
                        break
                
                # If no one left, game over
                if not switched:
                    self.status = "FINISHED"
                    self.winner = 1 - self.turn
                    self.message = f"Player {2 - self.turn} Wins!"
                    return

            # Regenerate resource for the (possibly new) active member
            new_active = team.get_active_member()
            if new_active and new_active.is_alive():
                new_active.regen_resource()


# ============ API ENDPOINTS ============

@app.route('/create', methods=['POST'])
def create_game():
    """Create a new game."""
    data = request.json
    team_classes = data.get("team", [])
    weather = data.get("weather", "Clear")
    
    if not team_classes:
        return jsonify({"ok": False, "error": "No team provided"}), 400
    
    game = Game()
    game.teams[0] = create_team(team_classes)
    game.weather = weather
    games[game.id] = game
    
    return jsonify({"ok": True, "game_id": game.id})


@app.route('/join', methods=['POST'])
def join_game():
    """Join an existing game."""
    data = request.json
    game_id = data.get("game_id")
    team_classes = data.get("team", [])
    
    if not game_id or game_id not in games:
        return jsonify({"ok": False, "error": "Game not found"}), 404
    
    if not team_classes:
        return jsonify({"ok": False, "error": "No team provided"}), 400
    
    game = games[game_id]
    
    if game.status != "WAITING":
        return jsonify({"ok": False, "error": "Game already started"}), 400
    
    game.teams[1] = create_team(team_classes)
    game.status = "ACTIVE"
    
    return jsonify({"ok": True, "game_id": game.id})


@app.route('/state/<game_id>', methods=['GET'])
def get_state(game_id):
    """Get current game state."""
    if game_id not in games:
        return jsonify({"ok": False, "error": "Game not found"}), 404
    
    # Update heartbeat
    player_idx = request.args.get('player_idx')
    if player_idx is not None:
        try:
            pid = int(player_idx)
            games[game_id].last_seen[pid] = time.time()
        except:
            pass
    
    return jsonify({"ok": True, "state": games[game_id].to_dict()})


@app.route('/action', methods=['POST'])
def submit_action():
    """Submit a game action (attack or tag)."""
    data = request.json
    game_id = data.get("game_id")
    player_idx = data.get("player_idx")
    action_data = data.get("action")
    
    if game_id not in games:
        return jsonify({"ok": False, "error": "Game not found"}), 404
    
    if player_idx not in [0, 1]:
        return jsonify({"ok": False, "error": "Invalid player index"}), 400
    
    if not action_data:
        return jsonify({"ok": False, "error": "No action data"}), 400
    
    game = games[game_id]
    result = game.apply_action(player_idx, action_data)
    
    return jsonify(result)


if __name__ == '__main__':
    print("Starting Freak Server")
    print("Listening on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
