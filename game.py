import pygame
import json
import random
import math
import os
import requests
import threading
from screen_effects import *

THEME = {
    "background": "#1a1a2e",
    "grid_primary": "#16213e",
    "grid_secondary": "#0f3460",
    "panel_bg_rgba": (22, 33, 62, 230),
    "panel_border": "#e94560",
    "accent": "#00d9ff",
    "text_primary": "#ffffff",
    "text_secondary": "#a8dadc",
    "ui_overlay_rgba": (15, 20, 35, 200),
    "button_border": "#00d9ff",
    "banner_highlight": "#e94560",
    "gradient_top": "#16213e",
    "gradient_bottom": "#1a1a2e"
}

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# ---------- Utilities ----------
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def tint_image(image, color):
    image = image.copy()
    image.fill((0, 0, 0, 255), None, pygame.BLEND_RGBA_MULT)
    image.fill(color[0:3] + (0,), None, pygame.BLEND_RGBA_ADD)
    return image

# ---------- Base Logic Classes ----------
class Effect:
    def __init__(self, name, duration, value):
        self.name = name
        self.duration = duration
        self.value = value

    def tick(self):
        self.duration -= 1
        return self.duration <= 0

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
        self.forced_target = None
        
        # GUI specific
        self.sprite_name = sprite_key
        self.animation_offset = 0
        self.animation_speed = random.uniform(0.05, 0.1)
        self.hover_y = 0
        self.x = 0
        self.y = 0
        self.target_x = 0 # For lunge
        self.shake_timer = 0
        self.float_amp = 5
        self.y_offset = 0
        self.current_sprite_override = None
        self.hit_pause_timer = 0  # For pausing at impact
        self.pending_bash_target = None  # For delayed Shield Bash damage
        self.hit_animation_timer = 0  # For hit sprite revert
        self.is_taking_hit = False  # Flag to prevent clearing hit animation
        
        # Enhanced Visual State
        self.breathing_phase = random.uniform(0, 6.28)  # Random start phase
        self.breathing_scale = 1.0  # Current scale multiplier
        self.death_fade_alpha = 255  # Opacity for death fade
        self.attack_windup_timer = 0  # Frames before attack executes
        self.aura_color = None  # Current status effect glow color
        self.aura_intensity = 0  # Aura brightness (0-255)
        self.is_dying = False  # Flag for death animation
        self.death_particles_spawned = False  # Track if death particles created
        
        # Dynamic Animation Properties
        self.base_scale = 1.0
        self.current_scale = 1.0
        self.rotation = 0
        self.lunge_offset_x = 0
        self.lunge_offset_y = 0
        self.hit_shake_x = 0
        self.hit_shake_y = 0
        self.hit_flash_timer = 0
        
        # Running Animation State (for Somesh Run Man attack)
        self.run_animation_frame = -1  # Current running frame (0-3), -1 when not running
        self.run_animation_timer = 0  # Frame timer for animation cycling
        
        # Bash Animation State (for Warrior Shield Bash)
        self.bash_animation_frame = -1  # Current bash frame (0-3), -1 when not bashing
        self.bash_animation_timer = 0  # Frame timer for bash animation
        
        self.trail = []  # For motion blur (image, x, y, alpha)

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
        self.resource = min(self.max_resource, self.resource + 15)

    def update_idle_particles(self, scene):
        # Add class-specific idle particles
        if self.sprite_name in ["mage", "priest"]:
            if random.random() < 0.3:
                color = (100, 200, 255) if self.sprite_name == "mage" else (255, 255, 100)
                scene.spawn_particle(self.x + 100 + random.randint(-30, 30), self.y + 150, color, (0, -1), 40, size=3)
        elif self.sprite_name in ["warrior", "archer", "somesh"]:
             if random.random() < 0.1:
                color = (150, 150, 150) if self.sprite_name != "somesh" else (150, 0, 150)
                scene.spawn_particle(self.x + 100 + random.randint(-40, 40), self.y + 190, color, (random.uniform(-0.5, 0.5), -0.5), 30, size=2)

                scene.spawn_particle(self.x + 100 + random.randint(-40, 40), self.y + 190, color, (random.uniform(-0.5, 0.5), -0.5), 30, size=2)

class NetworkClient:
    def __init__(self, base_url="https://jonathansamson.pythonanywhere.com/"):
        self.base_url = base_url
        self.session = requests.Session()  # Use a session for connection pooling (Keep-Alive)

    def create_game(self, team_classes, weather="Clear"):
        try:
            url = f"{self.base_url.rstrip('/')}/create"
            resp = self.session.post(url, json={"team": team_classes, "weather": weather})
            data = resp.json()
            return data if data.get("ok") else None
        except Exception as e:
            print(f"Create Game Error: {e}")
            return None

    def join_game(self, game_id, team_classes):
        try:
            resp = self.session.post(f"{self.base_url}/join", json={"game_id": game_id, "team": team_classes})
            data = resp.json()
            return data if data.get("ok") else None
        except:
            return None

    def get_state(self, game_id, player_idx=None):
        try:
            url = f"{self.base_url}/state/{game_id}"
            if player_idx is not None:
                url += f"?player_idx={player_idx}"
            resp = self.session.get(url)
            data = resp.json()
            if data.get("ok"):
                return data.get("state")
            return None
        except:
            return None

    def submit_action(self, game_id, player_idx, action_data):
        """Submit an action (attack or tag) to the server."""
        try:
            url = f"{self.base_url.rstrip('/')}/action"
            data = {
                "game_id": game_id, 
                "player_idx": player_idx,
                "action": action_data
            }
            resp = self.session.post(url, json=data)
            return resp.json()
        except Exception as e:
            print(f"Submit Action Error: {e}")
            return {"ok": False, "error": str(e)}
class Warrior(Character):
    def __init__(self):
        super().__init__("Warrior", 120, "Stamina", 60, "warrior")
    
    def get_actions(self):
        return ["Slash", "Power Strike", "Shield Bash", "Spin Slash"]


class Archer(Character):
    def __init__(self):
        super().__init__("Archer", 100, "Stamina", 60, "archer")
        self.float_amp = 2
        self.y_offset = 0
    
    def get_actions(self):
        return ["Quick Shot", "Double Arrow", "Piercing", "Cripple"]

class Mage(Character):
    def __init__(self):
        super().__init__("Mage", 90, "Mana", 80, "mage")
    
    def get_actions(self):
        return ["Magic Bolt", "Fireball", "Chain", "Drain"]

class Priest(Character):
    def __init__(self):
        super().__init__("Priest", 100, "Mana", 80, "priest")
    
    def get_actions(self):
        return ["Smite", "Judgement", "Holy Nova", "Pray"]

class Somesh(Character):
    def __init__(self):
        super().__init__("Somesh", 110, "Stamina", 70, "somesh")
    
    def get_actions(self):
        return ["Charged Spark", "Fah!!!", "Run Man", "Spark"]

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

# ---------- Visual Classes ----------
class Projectile:
    def __init__(self, start_x, start_y, end_x, end_y, image, speed=15, trail_color=None, fade_in=False, vibrate=False, source_char=None, target_char=None, damage_amount=0):
        self.x = start_x
        self.y = start_y
        self.end_x = end_x
        self.end_y = end_y
        self.image = image
        self.speed = speed
        self.active = True
        self.trail_color = trail_color
        self.fade_in = fade_in
        self.vibrate = vibrate
        self.alpha = 0 if fade_in else 255  # Start transparent if fade_in
        self.fade_speed = 15  # How fast to fade in
        self.vibrate_offset_x = 0
        self.vibrate_offset_y = 0
        self.source_char = source_char  # Track who fired this projectile
        self.target_char = target_char  # Track who should take damage
        self.damage_amount = damage_amount  # Damage to apply on impact
        
        dx = end_x - start_x
        dy = end_y - start_y
        dist = math.hypot(dx, dy)
        self.vx = (dx / dist) * speed
        self.vy = (dy / dist) * speed
        
        angle = math.degrees(math.atan2(-dy, dx))
        self.image = pygame.transform.rotate(self.image, angle)

    def update(self, scene):
        self.x += self.vx
        self.y += self.vy
        if math.hypot(self.end_x - self.x, self.end_y - self.y) < self.speed:
            self.active = False
        
        # Fade-in animation
        if self.fade_in and self.alpha < 255:
            self.alpha = min(255, self.alpha + self.fade_speed)
        
        # Vibration effect
        if self.vibrate:
            self.vibrate_offset_x = random.uniform(-3, 3)
            self.vibrate_offset_y = random.uniform(-3, 3)
        
        # Trail
        if self.trail_color:
            scene.spawn_particle(self.x, self.y, self.trail_color, (random.uniform(-1, 1), random.uniform(-1, 1)), 20, size=4)

    def draw(self, surface):
        if self.active:
            # Apply vibration offset
            draw_x = int(self.x + self.vibrate_offset_x)
            draw_y = int(self.y + self.vibrate_offset_y)
            
            # Apply alpha if fading in
            if self.fade_in and self.alpha < 255:
                # Create a copy with alpha
                img_copy = self.image.copy()
                img_copy.set_alpha(int(self.alpha))
                rect = img_copy.get_rect(center=(draw_x, draw_y))
                surface.blit(img_copy, rect)
            else:
                rect = self.image.get_rect(center=(draw_x, draw_y))
                surface.blit(self.image, rect)

class Particle:
    def __init__(self, x, y, color, velocity, life, size=5, shape="circle", gravity=0.0, bounce=False, color_shift=None):
        self.x = x
        self.y = y
        self.color = color
        self.vx, self.vy = velocity
        self.life = life
        self.max_life = life
        self.size = size
        self.initial_size = size
        self.shape = shape
        self.gravity = gravity  # Pixels per frame to add to vy
        self.bounce = bounce  # Whether to bounce off ground
        self.color_shift = color_shift  # Target color to shift towards
        self.ground_y = 720 - 50  # Ground level for bouncing
        self.rotation = random.uniform(0, 360)
        self.rot_speed = random.uniform(-5, 5)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.rotation += self.rot_speed
        
        # Apply gravity
        if self.gravity != 0:
            self.vy += self.gravity
        
        # Bounce off ground
        if self.bounce and self.y >= self.ground_y:
            self.y = self.ground_y
            self.vy = -self.vy * 0.6  # Energy loss on bounce
            self.vx *= 0.8  # Friction
        
        # Color shifting
        if self.color_shift:
            # Interpolate towards target color
            age_ratio = 1 - (self.life / self.max_life)
            self.color = tuple(
                int(self.color[i] + (self.color_shift[i] - self.color[i]) * age_ratio)
                for i in range(3)
            )
        
        self.life -= 1
        self.size = max(0, self.initial_size * (self.life / self.max_life))

    def draw(self, surface):
        if self.life > 0:
            alpha = int((self.life / self.max_life) * 255)
            s = pygame.Surface((int(self.initial_size)*4, int(self.initial_size)*4), pygame.SRCALPHA)
            center = (int(self.initial_size)*2, int(self.initial_size)*2)
            
            if self.shape == "circle":
                pygame.draw.circle(s, (*self.color, alpha), center, int(self.size))
            elif self.shape == "square":
                rect = pygame.Rect(center[0]-self.size, center[1]-self.size, self.size*2, self.size*2)
                pygame.draw.rect(s, (*self.color, alpha), rect)
            elif self.shape == "plus":
                # Draw a plus sign
                rect_h = pygame.Rect(center[0]-self.size, center[1]-self.size/3, self.size*2, self.size/1.5)
                rect_v = pygame.Rect(center[0]-self.size/3, center[1]-self.size, self.size/1.5, self.size*2)
                pygame.draw.rect(s, (*self.color, alpha), rect_h)
                pygame.draw.rect(s, (*self.color, alpha), rect_v)
            elif self.shape == "exclamation":
                # Draw an exclamation mark
                rect_body = pygame.Rect(center[0]-self.size/3, center[1]-self.size, self.size/1.5, self.size*1.5)
                rect_dot = pygame.Rect(center[0]-self.size/3, center[1]+self.size*0.8, self.size/1.5, self.size/1.5)
                pygame.draw.rect(s, (*self.color, alpha), rect_body)
                pygame.draw.rect(s, (*self.color, alpha), rect_dot)
            elif self.shape == "ember":
                # Flickering ember (small glowing circle with bright center)
                pygame.draw.circle(s, (*self.color, alpha // 2), center, int(self.size))
                pygame.draw.circle(s, (255, 255, 200, alpha), center, max(1, int(self.size * 0.4)))
            elif self.shape == "spark":
                # Sharp spark (line)
                start = (center[0], center[1] - int(self.size))
                end = (center[0], center[1] + int(self.size))
                pygame.draw.line(s, (*self.color, alpha), start, end, max(1, int(self.size * 0.3)))
            elif self.shape == "blood":
                # Droplet shape (irregular splat)
                points = [
                    (center[0], center[1] - int(self.size)),
                    (center[0] + int(self.size * 0.6), center[1]),
                    (center[0], center[1] + int(self.size)),
                    (center[0] - int(self.size * 0.6), center[1])
                ]
                pygame.draw.polygon(s, (*self.color, alpha), points)
            elif self.shape == "energy":
                # Glowing energy orb (bright center, fading edge)
                pygame.draw.circle(s, (*self.color, alpha // 3), center, int(self.size))
                pygame.draw.circle(s, (*self.color, alpha), center, int(self.size * 0.6))
                pygame.draw.circle(s, (255, 255, 255, alpha), center, max(1, int(self.size * 0.3)))
            elif self.shape == "star":
                # 4-point star
                points = [
                    (center[0], center[1] - self.size),
                    (center[0] + self.size * 0.3, center[1] - self.size * 0.3),
                    (center[0] + self.size, center[1]),
                    (center[0] + self.size * 0.3, center[1] + self.size * 0.3),
                    (center[0], center[1] + self.size),
                    (center[0] - self.size * 0.3, center[1] + self.size * 0.3),
                    (center[0] - self.size, center[1]),
                    (center[0] - self.size * 0.3, center[1] - self.size * 0.3)
                ]
                pygame.draw.polygon(s, (*self.color, alpha), points)
            
            # Rotate surface if needed
            if self.rotation != 0:
                s = pygame.transform.rotate(s, self.rotation)
            
            surface.blit(s, (self.x - s.get_width()//2, self.y - s.get_height()//2))

class LightningEffect:
    def __init__(self, target_x, target_y):
        self.x = int(target_x)
        self.y = int(target_y)
        self.life = 20
        self.segments = []
        self.generate()

    def generate(self):
        self.segments = []
        # Main bolt from sky (larger area)
        start_x = self.x + random.randint(-20, 20)
        start_y = -50 # Always start from top
        curr_x, curr_y = start_x, start_y
        
        while curr_y < self.y + 30:
            next_x = curr_x + random.randint(-30, 30)
            next_y = curr_y + random.randint(30, 60)
            self.segments.append(((int(curr_x), int(curr_y)), (int(next_x), int(next_y))))
            curr_x, curr_y = next_x, next_y
            
            # Branching (more frequent)
            if random.random() < 0.3:
                branch_x, branch_y = curr_x, curr_y
                for _ in range(3):
                    b_next_x = branch_x + random.randint(-50, 50)
                    b_next_y = branch_y + random.randint(15, 50)
                    self.segments.append(((int(branch_x), int(branch_y)), (int(b_next_x), int(b_next_y))))
                    branch_x, branch_y = b_next_x, b_next_y

    def update(self):
        self.life -= 1
        if self.life % 4 == 0: self.generate() # Flicker

    def draw(self, surface):
        for start, end in self.segments:
            pygame.draw.line(surface, (100, 200, 255), start, end, 12) # Blue glow (thicker)
            pygame.draw.line(surface, (200, 220, 255), start, end, 8) # Mid-blue layer
            pygame.draw.line(surface, (255, 255, 255), start, end, 4) # White core (thicker)

class RippleEffect:
    def __init__(self, x, y, color_theme='blue'):
        self.x = x
        self.y = y
        self.ripples = []
        self.theme = color_theme
        # Create multiple expanding ripples with varied properties per theme
        for i in range(10):
            if color_theme == 'blue':
                color = (0, 100 + i * 10, 255 - i * 15)
                max_radius = 500
                speed = 10
                ring_width = 12
            elif color_theme == 'silver':
                # Sharp, metallic ripples - faster, smaller radius
                color = (180 + i * 7, 180 + i * 7, 200 + i * 5)
                max_radius = 350
                speed = 14
                ring_width = 8
            elif color_theme == 'cyan':
                # Fast, piercing ripples - thin and quick
                color = (50 + i * 15, 220 + i * 3, 255)
                max_radius = 600
                speed = 18
                ring_width = 6
            elif color_theme == 'purple':
                # Electric crackling ripples - erratic expansion
                color = (120 + i * 13, 80 + i * 10, 255 - i * 8)
                max_radius = 450
                speed = 12 + (i % 3) * 2  # Varied speed
                ring_width = 15
            elif color_theme == 'gold':
                # Divine, slow expanding ripples - thick and grand
                color = (255, 200 - i * 8, 30 + i * 15)
                max_radius = 550
                speed = 8
                ring_width = 18
            else:
                color = (0, 100 + i * 10, 255 - i * 15)
                max_radius = 500
                speed = 10
                ring_width = 12
            
            self.ripples.append({
                'radius': i * 15,
                'max_radius': max_radius,
                'speed': speed,
                'alpha': 255,
                'color': color,
                'ring_width': ring_width,
                'rotation': i * 36  # For visual variety
            })
        self.life = 150

    def update(self):
        self.life -= 1
        for ripple in self.ripples:
            ripple['radius'] += ripple['speed']
            ripple['alpha'] = max(0, 255 - (ripple['radius'] / ripple['max_radius']) * 255)
            ripple['rotation'] = (ripple['rotation'] + 2) % 360

    def draw(self, surface):
        for ripple in self.ripples:
            if ripple['radius'] < ripple['max_radius']:
                s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                alpha = int(ripple['alpha'])
                color = ripple['color'] + (alpha,)
                ring_width = ripple['ring_width']
                
                # Theme-specific rendering
                if self.theme == 'silver':
                    # Metallic with sharp edges
                    pygame.draw.circle(s, color, (int(self.x), int(self.y)), int(ripple['radius']), ring_width)
                    edge_color = ripple['color'] + (alpha // 2,)
                    pygame.draw.circle(s, edge_color, (int(self.x), int(self.y)), int(ripple['radius']) + 5, 3)
                elif self.theme == 'cyan':
                    # Thin, piercing rings
                    pygame.draw.circle(s, color, (int(self.x), int(self.y)), int(ripple['radius']), ring_width)
                    glow_color = (100, 255, 255, alpha // 4)
                    pygame.draw.circle(s, glow_color, (int(self.x), int(self.y)), int(ripple['radius']), ring_width * 3)
                elif self.theme == 'purple':
                    # Electric crackling with jagged inner ring
                    pygame.draw.circle(s, color, (int(self.x), int(self.y)), int(ripple['radius']), ring_width)
                    # Add electric crackle effect
                    for angle_deg in range(0, 360, 45):
                        angle_rad = math.radians(angle_deg + ripple['rotation'])
                        offset_x = int(math.cos(angle_rad) * ripple['radius'])
                        offset_y = int(math.sin(angle_rad) * ripple['radius'])
                        pygame.draw.circle(s, (200, 150, 255, alpha), (int(self.x) + offset_x, int(self.y) + offset_y), 4)
                elif self.theme == 'gold':
                    # Divine thick rings with holy glow
                    glow_color = (255, 255, 150, alpha // 3)
                    pygame.draw.circle(s, glow_color, (int(self.x), int(self.y)), int(ripple['radius']), ring_width * 2)
                    pygame.draw.circle(s, color, (int(self.x), int(self.y)), int(ripple['radius']), ring_width)
                    inner_color = (255, 255, 200, alpha)
                    pygame.draw.circle(s, inner_color, (int(self.x), int(self.y)), int(ripple['radius']), ring_width // 2)
                else:
                    # Blue default with triple layers
                    glow_color = ripple['color'] + (alpha // 3,)
                    pygame.draw.circle(s, glow_color, (int(self.x), int(self.y)), int(ripple['radius']), 20)
                    pygame.draw.circle(s, color, (int(self.x), int(self.y)), int(ripple['radius']), 12)
                    bright_color = (min(255, ripple['color'][0] + 100), min(255, ripple['color'][1] + 100), 255, alpha)
                    pygame.draw.circle(s, bright_color, (int(self.x), int(self.y)), int(ripple['radius']), 6)
                
                surface.blit(s, (0, 0))

class FloatingImage:
    def __init__(self, x, y, image, duration=60):
        self.x = x
        self.y = y
        self.image = image
        self.duration = duration
        self.timer = 0
        self.scale = 0.5  # Start small
        self.max_scale = 1.2
        self.target_scale = 1.0

    def update(self):
        self.y -= 0.8  # Float up
        self.timer += 1
        
        # Pop effect
        if self.timer < 10:
            self.scale = min(self.max_scale, self.scale + 0.2)
        elif self.timer < 20:
            self.scale = max(self.target_scale, self.scale - 0.05)

    def draw(self, surface):
        if self.timer < self.duration:
            img = self.image.copy()
            
            # Scale
            if self.scale != 1.0:
                w = int(img.get_width() * self.scale)
                h = int(img.get_height() * self.scale)
                img = pygame.transform.scale(img, (w, h))
            
            # Fade
            alpha = max(0, 255 - int((self.timer / self.duration) * 255))
            img.set_alpha(alpha)
            
            rect = img.get_rect(center=(int(self.x), int(self.y)))
            surface.blit(img, rect)

class FloatingText:
    def __init__(self, x, y, text, color, duration=60, size=48):
        self.x = x
        self.y = y
        self.text = str(text)
        self.color = color
        self.duration = duration
        self.timer = 0
        self.font = pygame.font.Font(None, size)
        self.scale = 0.5 # Start small
        self.max_scale = 1.5 # Pop larger
        self.target_scale = 1.0
        self.vx = random.uniform(-2, 2) # Horizontal drift
        self.vy = -5 # Initial upward velocity
        self.gravity = 0.2 # Gravity

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity # Apply gravity
        self.vx *= 0.95 # Friction
        
        self.timer += 1
        
        # Pop effect
        if self.timer < 10:
            self.scale = min(self.max_scale, self.scale + 0.2)
        elif self.timer < 20:
            self.scale = max(self.target_scale, self.scale - 0.1)

    def draw(self, surface):
        if self.timer < self.duration:
            # Render text
            text_surf = self.font.render(self.text, True, self.color)
            
            # Scale
            if self.scale != 1.0:
                w = int(text_surf.get_width() * self.scale)
                h = int(text_surf.get_height() * self.scale)
                text_surf = pygame.transform.scale(text_surf, (w, h))
            
            # Fade
            alpha = max(0, 255 - int((self.timer / self.duration) * 255))
            text_surf.set_alpha(alpha)
            
            # Draw with shadow
            shadow_surf = self.font.render(self.text, True, (0, 0, 0))
            if self.scale != 1.0:
                sw = int(shadow_surf.get_width() * self.scale)
                sh = int(shadow_surf.get_height() * self.scale)
                shadow_surf = pygame.transform.scale(shadow_surf, (sw, sh))
            shadow_surf.set_alpha(alpha)
            
            rect = text_surf.get_rect(center=(int(self.x), int(self.y)))
            shadow_rect = rect.copy()
            shadow_rect.x += 2
            shadow_rect.y += 2
            
            surface.blit(shadow_surf, shadow_rect)
            surface.blit(text_surf, rect)

class Button:
    def __init__(self, x, y, width, height, text, callback, subtext="", color=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.subtext = subtext
        self.callback = callback
        self.hovered = False
        self.color = color if color else hex_to_rgb(THEME["grid_secondary"])
        self.border_color = hex_to_rgb(THEME["button_border"])
        self.font = pygame.font.Font(None, 28)
        self.sub_font = pygame.font.Font(None, 20)
        self.disabled = False

    def update(self, mouse_pos, mouse_click):
        if self.disabled: return False
        self.hovered = self.rect.collidepoint(mouse_pos)
        if self.hovered and mouse_click:
            return True
        return False

    def draw(self, surface):
        if self.disabled:
            color = (60, 60, 60)
            border_color = (100, 100, 100)
            text_color = (150, 150, 150)
        else:
            color = [min(255, c + 30) for c in self.color] if self.hovered else self.color
            border_color = self.border_color
            text_color = (255, 255, 255)
        
        # RPG-style pixelated border effect
        # Outer dark border
        pygame.draw.rect(surface, (20, 20, 20), self.rect, 0)
        # Main button color (inset)
        inner_rect = pygame.Rect(self.rect.x + 4, self.rect.y + 4, self.rect.width - 8, self.rect.height - 8)
        pygame.draw.rect(surface, color, inner_rect, 0)
        # Bright border for 3D effect
        pygame.draw.rect(surface, border_color, self.rect, 4)
        # Inner shadow
        shadow_rect = pygame.Rect(self.rect.x + 6, self.rect.y + 6, self.rect.width - 12, self.rect.height - 12)
        pygame.draw.rect(surface, (0, 0, 0, 80), shadow_rect, 2)
        
        if self.text:
            text_surf = self.font.render(self.text, True, text_color)
            # Text shadow for pixelated RPG look
            text_shadow = self.font.render(self.text, True, (0, 0, 0))
            text_rect = text_surf.get_rect(center=(self.rect.centerx, self.rect.centery - 10 if self.subtext else self.rect.centery))
            shadow_rect = text_rect.copy()
            shadow_rect.x += 2
            shadow_rect.y += 2
            surface.blit(text_shadow, shadow_rect)
            surface.blit(text_surf, text_rect)
        
        if self.subtext:
            sub_color = (220, 220, 180) if not self.disabled else (120, 120, 120)
            sub_surf = self.sub_font.render(self.subtext, True, sub_color)
            sub_rect = sub_surf.get_rect(center=(self.rect.centerx, self.rect.centery + 12))
            surface.blit(sub_surf, sub_rect)

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
    "Charged Spark": {"cost": 12, "info": "50 Dmg"},
    "Run Man": {"cost": 15, "info": "35 Dmg"},
    "Spark": {"cost": 25, "info": "50 AoE"},
    "Skip Turn": {"cost": 0, "info": "Pass"},
}

# ---------- Scenes ----------
class Scene:
    def __init__(self, manager):
        self.manager = manager
    def handle_input(self, events): pass
    def update(self): pass
    def draw(self, screen): pass

class TextInput:
    def __init__(self, x, y, w, h, placeholder=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = ""
        self.placeholder = placeholder
        self.active = False
        self.font = pygame.font.Font(None, 32)
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                return True
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                self.text += event.unicode
        return False

    def draw(self, screen):
        color = (255, 255, 255) if self.active else (150, 150, 150)
        pygame.draw.rect(screen, (30, 30, 30), self.rect)
        pygame.draw.rect(screen, color, self.rect, 2)
        
        txt = self.text if self.text else self.placeholder
        col = (255, 255, 255) if self.text else (100, 100, 100)
        surf = self.font.render(txt, True, col)
        screen.blit(surf, (self.rect.x + 10, self.rect.y + 10))

class MultiplayerScene(Scene):
    def __init__(self, manager):
        super().__init__(manager)
        self.font = pygame.font.Font(None, 64)
        self.small_font = pygame.font.Font(None, 32)
        
        # Better spacing - no overlap
        btn_y_start = SCREEN_HEIGHT//2 - 40
        btn_spacing = 85
        self.create_btn = Button(SCREEN_WIDTH//2 - 120, btn_y_start, 240, 65, "CREATE GAME", self.go_create, color=(60, 120, 60))
        self.join_btn = Button(SCREEN_WIDTH//2 - 120, btn_y_start + btn_spacing, 240, 65, "JOIN GAME", self.go_join, color=(60, 80, 140))
        self.back_btn = Button(SCREEN_WIDTH//2 - 120, btn_y_start + btn_spacing*2, 240, 65, "BACK", self.go_back, color=(120, 40, 40))
        self.input = TextInput(SCREEN_WIDTH//2 - 150, SCREEN_HEIGHT//2 - 150, 300, 50, "Enter Game ID to Join")
        self.show_input = False

    def go_create(self):
        self.manager.mode = "CREATE"
        self.manager.change_scene("SELECT")

    def go_join(self):
        if not self.show_input:
            self.show_input = True
            self.join_btn.text = "CONNECT"
            return
        
        if len(self.input.text) > 0:
            self.manager.game_id = self.input.text
            self.manager.mode = "JOIN"
            self.manager.change_scene("SELECT")

    def go_back(self):
        self.manager.change_scene("START")

    def handle_input(self, events):
        mouse_pos = pygame.mouse.get_pos()
        mouse_click = False
        for event in events:
            if self.show_input: self.input.handle_event(event)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_click = True
        
        if not self.show_input:
            if self.create_btn.update(mouse_pos, mouse_click): self.create_btn.callback()
        
        if self.join_btn.update(mouse_pos, mouse_click): self.join_btn.callback()
        if self.back_btn.update(mouse_pos, mouse_click): self.back_btn.callback()

    def draw(self, screen):
        screen.blit(self.manager.assets["bg"], (0,0))
        
        # RPG-style title panel
        title_panel = pygame.Surface((600, 100), pygame.SRCALPHA)
        pygame.draw.rect(title_panel, (40, 30, 20), (0, 0, 600, 100), 0)
        pygame.draw.rect(title_panel, (200, 180, 120), (0, 0, 600, 100), 5)
        pygame.draw.rect(title_panel, (80, 60, 40), (5, 5, 590, 90), 3)
        screen.blit(title_panel, (SCREEN_WIDTH//2 - 300, 80))
        
        title = self.font.render("MULTIPLAYER", True, (255, 220, 100))
        title_shadow = self.font.render("MULTIPLAYER", True, (50, 30, 10))
        screen.blit(title_shadow, title_shadow.get_rect(center=(SCREEN_WIDTH//2 + 2, 132)))
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, 130)))
        
        subtitle = self.small_font.render("Connect with other players", True, (240, 220, 180))
        screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH//2, 220)))
        
        if self.show_input:
            self.input.draw(screen)
        else:
            self.create_btn.draw(screen)
        self.join_btn.draw(screen)
        self.back_btn.draw(screen)

class LobbyScene(Scene):
    def __init__(self, manager, game_id):
        super().__init__(manager)
        self.game_id = game_id
        self.font = pygame.font.Font(None, 64)
        self.small_font = pygame.font.Font(None, 32)
        self.timer = 0
        self.client = NetworkClient()
        self.back_btn = Button(50, SCREEN_HEIGHT - 80, 200, 60, "CANCEL", self.go_back, color=(120, 40, 40))
    
    def go_back(self):
        self.manager.change_scene("MULTIPLAYER")

    def update(self):
        self.timer += 1
        if self.timer % 30 == 0: # Poll every 0.5 seconds
            # Determine player_idx based on mode
            player_idx = 0 if self.manager.mode == "CREATE" else 1
            state = self.client.get_state(self.game_id, player_idx)
            if state and state.get("status") == "ACTIVE":
                # Store weather from state for display and battle
                if "weather" in state:
                    self.manager.selected_weather = state["weather"]
                self.manager.start_multiplayer_battle(state, player_idx)
    
    def handle_input(self, events):
        mouse_pos = pygame.mouse.get_pos()
        mouse_click = False
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_click = True
        
        if self.back_btn.update(mouse_pos, mouse_click):
            self.back_btn.callback()

    def draw(self, screen):
        screen.blit(self.manager.assets["bg"], (0,0))
        
        # RPG-style panel
        panel = pygame.Surface((650, 220), pygame.SRCALPHA)
        pygame.draw.rect(panel, (40, 30, 20), (0, 0, 650, 220), 0)
        pygame.draw.rect(panel, (200, 180, 120), (0, 0, 650, 220), 6)
        pygame.draw.rect(panel, (80, 60, 40), (6, 6, 638, 208), 3)
        screen.blit(panel, (SCREEN_WIDTH//2 - 325, SCREEN_HEIGHT//2 - 110))
        
        text = self.font.render(f"GAME ID: {self.game_id}", True, (255, 220, 100))
        text_shadow = self.font.render(f"GAME ID: {self.game_id}", True, (50, 30, 10))
        screen.blit(text_shadow, text_shadow.get_rect(center=(SCREEN_WIDTH//2 + 2, SCREEN_HEIGHT//2 - 62)))
        screen.blit(text, text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 60)))
        
        sub = self.small_font.render("Waiting for opponent...", True, (240, 220, 180))
        screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2)))
        
        # Display weather setting
        weather_text = self.small_font.render(f"Weather: {self.manager.selected_weather}", True, (180, 220, 255))
        screen.blit(weather_text, weather_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 40)))
        
        # Animated dots
        dots = "." * ((self.timer // 20) % 4)
        loading = self.small_font.render(dots, True, (200, 180, 140))
        screen.blit(loading, (SCREEN_WIDTH//2 + 120, SCREEN_HEIGHT//2))
        
        self.back_btn.draw(screen)

class StartScene(Scene):
    def __init__(self, manager):
        super().__init__(manager)
        self.title_font = pygame.font.Font(None, 96)
        self.font = pygame.font.Font(None, 48)
        self.small_font = pygame.font.Font(None, 28)
        
        # Play menu music
        if "menu_theme" in self.manager.sounds:
            if not pygame.mixer.music.get_busy():
                pygame.mixer.music.load(self.manager.sounds["menu_theme"])
                pygame.mixer.music.play(-1)

        # Better spacing - moved buttons down
        btn_y_start = SCREEN_HEIGHT//2 + 20
        btn_spacing = 70
        self.start_btn = Button(SCREEN_WIDTH//2 - 120, btn_y_start, 240, 60, "LOCAL GAME", self.go_select, color=(60, 100, 60))
        self.multi_btn = Button(SCREEN_WIDTH//2 - 120, btn_y_start + btn_spacing, 240, 60, "MULTIPLAYER", self.go_multi, color=(60, 60, 120))
        self.settings_btn = Button(SCREEN_WIDTH//2 - 120, btn_y_start + btn_spacing*2, 240, 60, "SETTINGS", self.go_settings, color=(100, 100, 40))
        self.exit_btn = Button(SCREEN_WIDTH//2 - 120, btn_y_start + btn_spacing*3, 240, 60, "EXIT", self.exit_game, color=(120, 40, 40))

    def go_settings(self):
        self.manager.change_scene("SETTINGS")

    def go_multi(self):
        self.manager.change_scene("MULTIPLAYER")

    def go_select(self):
        self.manager.mode = "LOCAL"
        self.manager.change_scene("SELECT")

    def exit_game(self):
        pygame.quit()
        exit()

    def handle_input(self, events):
        mouse_pos = pygame.mouse.get_pos()
        mouse_click = False
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_click = True
        
        if self.start_btn.update(mouse_pos, mouse_click): self.start_btn.callback()
        if self.multi_btn.update(mouse_pos, mouse_click): self.multi_btn.callback()
        if self.settings_btn.update(mouse_pos, mouse_click): self.settings_btn.callback()
        if self.exit_btn.update(mouse_pos, mouse_click): self.exit_btn.callback()

    def draw(self, screen):
        screen.blit(self.manager.assets["bg"], (0,0))
        
        # RPG-style title with pixelated border
        title_panel = pygame.Surface((700, 120), pygame.SRCALPHA)
        # Draw pixelated border
        pygame.draw.rect(title_panel, (40, 30, 20), (0, 0, 700, 120), 0)
        pygame.draw.rect(title_panel, (200, 180, 120), (0, 0, 700, 120), 6)
        pygame.draw.rect(title_panel, (80, 60, 40), (6, 6, 688, 108), 3)
        screen.blit(title_panel, (SCREEN_WIDTH//2 - 350, 80))
        
        title = self.title_font.render("FREAKY ARENA", True, (255, 220, 100))
        title_shadow = self.title_font.render("FREAKY ARENA", True, (50, 30, 10))
        screen.blit(title_shadow, title_shadow.get_rect(center=(SCREEN_WIDTH//2 + 3, 143)))
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, 140)))
        
        subtitle = self.font.render("Match their freak :]", True, (240, 220, 180))
        screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH//2, 240)))
        
        self.start_btn.draw(screen)
        self.multi_btn.draw(screen)
        self.settings_btn.draw(screen)
        self.exit_btn.draw(screen)

class SettingsScene(Scene):
    def __init__(self, manager):
        super().__init__(manager)
        self.font = pygame.font.Font(None, 64)
        self.label_font = pygame.font.Font(None, 48)
        
        self.back_btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT - 100, 200, 60, "BACK", self.go_back, color=(120, 40, 40))
        
        # Slider Rects
        self.music_slider_rect = pygame.Rect(SCREEN_WIDTH//2 - 150, 265, 300, 30)
        self.sfx_slider_rect = pygame.Rect(SCREEN_WIDTH//2 - 150, 415, 300, 30)
        self.dragging_music = False
        self.dragging_sfx = False

    def go_back(self):
        self.manager.change_scene("START")

    def handle_input(self, events):
        mouse_pos = pygame.mouse.get_pos()
        mouse_click = False
        mouse_held = pygame.mouse.get_pressed()[0]
        
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_click = True
                if self.music_slider_rect.collidepoint(mouse_pos):
                    self.dragging_music = True
                if self.sfx_slider_rect.collidepoint(mouse_pos):
                    self.dragging_sfx = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.dragging_music = False
                self.dragging_sfx = False
        
        if self.dragging_music:
            # Calculate volume based on x position
            rel_x = mouse_pos[0] - self.music_slider_rect.x
            vol = max(0.0, min(1.0, rel_x / self.music_slider_rect.width))
            self.manager.set_music_volume(vol)
            
        if self.dragging_sfx:
            rel_x = mouse_pos[0] - self.sfx_slider_rect.x
            vol = max(0.0, min(1.0, rel_x / self.sfx_slider_rect.width))
            self.manager.set_sfx_volume(vol)
        
        if self.back_btn.update(mouse_pos, mouse_click): self.back_btn.callback()

    def draw(self, screen):
        screen.blit(self.manager.assets["bg"], (0,0))
        
        # Title
        title = self.font.render("SETTINGS", True, (255, 220, 100))
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, 100)))
        
        # Music
        mus_label = self.label_font.render("MUSIC VOLUME", True, (200, 200, 200))
        screen.blit(mus_label, mus_label.get_rect(center=(SCREEN_WIDTH//2, 200)))
        
        # Slider Bar Background
        pygame.draw.rect(screen, (50, 50, 50), self.music_slider_rect)
        # Slider Fill
        fill_width = int(self.music_slider_rect.width * self.manager.music_volume)
        pygame.draw.rect(screen, (0, 200, 100), (self.music_slider_rect.x, self.music_slider_rect.y, fill_width, self.music_slider_rect.height))
        # Slider Handle
        handle_x = self.music_slider_rect.x + fill_width
        pygame.draw.circle(screen, (255, 255, 255), (handle_x, self.music_slider_rect.centery), 20)
        
        vol_txt = self.manager.font.render(f"{int(self.manager.music_volume*100)}%", True, (255, 255, 255))
        screen.blit(vol_txt, vol_txt.get_rect(center=(SCREEN_WIDTH//2, 310)))
        
        # SFX
        sfx_label = self.label_font.render("SFX VOLUME", True, (200, 200, 200))
        screen.blit(sfx_label, sfx_label.get_rect(center=(SCREEN_WIDTH//2, 360)))
        
        # Slider Bar Background
        pygame.draw.rect(screen, (50, 50, 50), self.sfx_slider_rect)
        # Slider Fill
        fill_width = int(self.sfx_slider_rect.width * self.manager.sfx_volume)
        pygame.draw.rect(screen, (0, 100, 200), (self.sfx_slider_rect.x, self.sfx_slider_rect.y, fill_width, self.sfx_slider_rect.height))
        # Slider Handle
        handle_x = self.sfx_slider_rect.x + fill_width
        pygame.draw.circle(screen, (255, 255, 255), (handle_x, self.sfx_slider_rect.centery), 20)
        
        vol_txt = self.manager.font.render(f"{int(self.manager.sfx_volume*100)}%", True, (255, 255, 255))
        screen.blit(vol_txt, vol_txt.get_rect(center=(SCREEN_WIDTH//2, 460)))
        
        self.back_btn.draw(screen)

class SelectScene(Scene):
    def __init__(self, manager):
        super().__init__(manager)
        self.font = pygame.font.Font(None, 56)
        self.small_font = pygame.font.Font(None, 28)
        self.options = [Warrior(), Archer(), Mage(), Priest(), Somesh()]
        self.selected = []
        self.buttons = []
        
        start_x = SCREEN_WIDTH//2 - 450
        for i, char in enumerate(self.options):
            # Pass empty text to avoid overlap
            btn = Button(start_x + i*180, SCREEN_HEIGHT//2, 160, 200, "", lambda idx=i: self.toggle_select(idx))
            self.buttons.append(btn)
            
        self.confirm_btn = Button(SCREEN_WIDTH//2 - 120, SCREEN_HEIGHT - 90, 240, 65, "CONFIRM", self.confirm_selection, color=(60, 120, 60))
        self.back_btn = Button(SCREEN_WIDTH//2 - 360, SCREEN_HEIGHT - 90, 200, 65, "BACK", self.go_back, color=(120, 40, 40))
        
        # Weather Toggle
        self.weather = "Clear"
        self.weather_btn = Button(SCREEN_WIDTH//2 + 160, SCREEN_HEIGHT - 90, 200, 65, f"Weather: {self.weather}", self.toggle_weather, color=(60, 80, 100))
        
        # Disable weather button for joiners in multiplayer
        if self.manager.mode == "JOIN":
            self.weather_btn.disabled = True
            self.weather_btn.text = "Weather: (Host)"

    def toggle_weather(self):
        if self.weather == "Clear":
            self.weather = "Rainy"
        else:
            self.weather = "Clear"
        self.weather_btn.text = f"Weather: {self.weather}"

    def go_back(self):
        # Reset mode and go back to appropriate menu
        if self.manager.mode in ["CREATE", "JOIN"]:
            self.manager.change_scene("MULTIPLAYER")
        else:
            self.manager.change_scene("START")

    def toggle_select(self, idx):
        char = self.options[idx]
        if char in self.selected:
            self.selected.remove(char)
        elif len(self.selected) < 2:
            self.selected.append(char)
    


    def confirm_selection(self):
        if len(self.selected) == 2:
            if self.manager.mode == "LOCAL":
                # AI gets 2 random remaining characters
                remaining = [c for c in self.options if c not in self.selected]
                ai_choices = random.sample(remaining, min(2, len(remaining)))
                # Re-instantiate to avoid reference issues
                p_team = [type(c)() for c in self.selected]
                ai_team = [type(c)() for c in ai_choices]
                self.manager.start_battle(p_team, ai_team, weather=self.weather)
            elif self.manager.mode == "CREATE":
                # Create game on server with weather setting
                team_names = [c.__class__.__name__ for c in self.selected]
                client = NetworkClient()
                resp = client.create_game(team_names, weather=self.weather)
                if resp and "game_id" in resp:
                    self.manager.game_id = resp["game_id"]
                    self.manager.selected_weather = self.weather  # Store weather in manager
                    self.manager.change_scene("LOBBY")
            elif self.manager.mode == "JOIN":
                # Join game on server
                team_names = [c.__class__.__name__ for c in self.selected]
                client = NetworkClient()
                resp = client.join_game(self.manager.game_id, team_names)
                if resp and resp.get("ok"):
                    self.manager.change_scene("LOBBY")

    def handle_input(self, events):
        mouse_pos = pygame.mouse.get_pos()
        mouse_click = False
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_click = True
        
        for i, btn in enumerate(self.buttons):
            # Highlight selected
            if self.options[i] in self.selected:
                btn.border_color = (100, 255, 100)
            else:
                btn.border_color = hex_to_rgb(THEME["button_border"])
                
            if btn.update(mouse_pos, mouse_click): btn.callback()
            
        self.confirm_btn.disabled = len(self.selected) != 2
        if self.confirm_btn.update(mouse_pos, mouse_click) and len(self.selected) == 2:
            self.confirm_btn.callback()
        
        if self.back_btn.update(mouse_pos, mouse_click):
            self.back_btn.callback()
            
        # Only allow weather changes for host or local games
        if self.manager.mode != "JOIN":
            if self.weather_btn.update(mouse_pos, mouse_click):
                self.weather_btn.callback()
        else:
            # Still draw button but don't process clicks
            self.weather_btn.update(mouse_pos, False)

    def draw(self, screen):
        screen.blit(self.manager.assets["bg"], (0,0))
        
        # RPG-style title panel
        title_panel = pygame.Surface((550, 90), pygame.SRCALPHA)
        pygame.draw.rect(title_panel, (40, 30, 20), (0, 0, 550, 90), 0)
        pygame.draw.rect(title_panel, (200, 180, 120), (0, 0, 550, 90), 5)
        pygame.draw.rect(title_panel, (80, 60, 40), (5, 5, 540, 80), 3)
        screen.blit(title_panel, (SCREEN_WIDTH//2 - 275, 50))
        
        title = self.font.render("SELECT 2 HEROES", True, (255, 220, 100))
        title_shadow = self.font.render("SELECT 2 HEROES", True, (50, 30, 10))
        screen.blit(title_shadow, title_shadow.get_rect(center=(SCREEN_WIDTH//2 + 2, 97)))
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, 95)))
        
        subtitle_text = "Choose your champions" if self.manager.mode == "LOCAL" else "Choose your team"
        subtitle = self.small_font.render(subtitle_text, True, (240, 220, 180))
        screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH//2, 165)))
        
        for i, btn in enumerate(self.buttons):
            btn.draw(screen)
            # Draw sprite preview
            img = self.manager.assets[self.options[i].sprite_name]
            img = pygame.transform.scale(img, (100, 100))
            screen.blit(img, (btn.rect.centerx - 50, btn.rect.centery - 70))
            
            # Draw Name Below
            name_surf = self.manager.font.render(self.options[i].name, True, (255, 255, 255))
            screen.blit(name_surf, name_surf.get_rect(center=(btn.rect.centerx, btn.rect.bottom - 30)))
            
        self.confirm_btn.draw(screen)
        self.back_btn.draw(screen)
        self.weather_btn.draw(screen)
        
        # Show hint for joiners about weather control
        if self.manager.mode == "JOIN":
            hint_surf = self.small_font.render("Weather controlled by host", True, (180, 180, 180))
            screen.blit(hint_surf, (SCREEN_WIDTH//2 + 165, SCREEN_HEIGHT - 30))
        
        selection_names = ", ".join([c.name for c in self.selected]) if self.selected else "None"
        summary = self.small_font.render(f"Selected: {selection_names}", True, (240, 220, 180))
        screen.blit(summary, (SCREEN_WIDTH//2 - 150, SCREEN_HEIGHT - 150))



class BattleScene(Scene):
    def __init__(self, manager, t1_members, t2_members, multiplayer=False, player_idx=0, game_id=None, weather="Clear"):
        super().__init__(manager)
        self.multiplayer = multiplayer
        self.player_idx = player_idx
        self.game_id = game_id
        self.weather = weather
        self.client = NetworkClient()
        self.cached_state = None  # Cache to avoid double-fetching
        self.poll_timer = 0  # Initialize poll timer for multiplayer
        
        # Async polling infrastructure
        self.pending_server_state = None  # Thread-safe state passing
        self.state_lock = threading.Lock()  # Protect shared state
        self.polling_active = False  # Control background polling
        self.polling_thread = None  # Track background thread
        
        # Async move submission
        self.pending_move_result = None
        self.pending_action_result = None  # For new action system
        self.move_lock = threading.Lock()
        
        self.t1 = Team(t1_members)
        self.t2 = Team(t2_members)
        
        # Stop menu music
        pygame.mixer.music.stop()
        
        # Initialize Clouds (Smaller and Higher)
        self.clouds = []
        
        # Weather Setup
        cloud_images = ["cloud1", "cloud2", "cloud3"]
        if self.weather == "Rainy":
            cloud_images = ["raincloud1", "raincloud2", "raincloud3"]
            
        for i in range(5):
            self.clouds.append({
                "x": random.randint(0, SCREEN_WIDTH),
                "y": random.randint(0, 80), # Even higher up
                "speed": random.uniform(0.2, 0.5),
                "img": random.choice(cloud_images)
            })
        
        # Set initial positions for slide-in
        for m in self.t1.members:
            m.x = -200
        for m in self.t2.members:
            m.x = SCREEN_WIDTH + 200
            
        self.teams = [self.t1, self.t2]
        
        # Initialize turn index so that next_turn() flips it to the correct starter
        # Host (0) starts: Init to 1 -> flips to 0
        # Joiner (1) waits: Init to 0 -> flips to 1
        if self.multiplayer:
            self.current_team_idx = 1 if self.player_idx == 0 else 0
        else:
            self.current_team_idx = 1 # Local starts at 0 (Player 1)
            
        self.state = "IDLE"
        self.buttons = []
        self.log_messages = ["Battle Start!"]
        self.projectiles = []
        self.particles = []
        self.floating_texts = []
        self.font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 24)
        self.tiny_font = pygame.font.Font(None, 18)
        self.exit_match_btn = Button(
            SCREEN_WIDTH//2 - 110,
            SCREEN_HEIGHT//2 + 60,
            220,
            50,
            "EXIT MATCH",
            self.exit_match,
            color=(120, 40, 40)
        )
        self.shake_timer = 0
        self.pending_next_turn = False
        self.animation_lock_timer = 0
        self.waiting_for_projectiles = False
        self.paused = False
        self.ai_action_ready = False
        self.action_prompt = "Battle Start!"
        self.death_message_timer = 0  # Timer for death message display
        self.death_message_text = ""  # Death message to display
        self.pending_team_switch = None  # (character, team) waiting to switch
        self.victory_pending = False  # Flag for victory delay
        self.victory_timer = 0  # Timer for victory screen
        self.waiting_for_server_confirmation = False  # Optimistic UI flag
        
        # Visual Enhancement Systems
        self.screen_shake = ScreenShakeController()
        self.slow_motion = SlowMotionController()
        self.screen_flash = ScreenFlashController()
        self.vignette = VignetteEffect(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.zoom = ZoomController()
        self.color_filter = ColorFilterController(SCREEN_WIDTH, SCREEN_HEIGHT)
        
        # Weather Effects
        self.rain_effect = None
        self.lightning_timer = 0
        if self.weather == "Rainy":
            self.rain_effect = RainEffect(SCREEN_WIDTH, SCREEN_HEIGHT)
            self.color_filter.add_filter('desaturate', 0.3) # Gloomy look
            self.vignette.set_intensity(0.4) # Darker edges
        
        # Combat Enhancement
        # self.crit_chance = 0.15  # REMOVED
        # self.crit_multiplier = 1.5  # REMOVED
        self.combo_counter = 0  # Track consecutive hits
        self.last_attacker = None  # Track last attacker for combo
        
        # Ambient particles timer
        self.ambient_particle_timer = 0
        
        # Maximum particle limit for performance
        self.max_particles = 200
        
        self.next_turn()

    def log(self, msg):
        self.log_messages.append(msg)
        if len(self.log_messages) > 6: self.log_messages.pop(0)

    def spawn_particle(self, x, y, color, velocity, life, size=5, shape="circle", gravity=0.0, bounce=False, color_shift=None):
        """Spawn a particle with optional physics properties."""
        self.particles.append(Particle(x, y, color, velocity, life, size, shape, gravity, bounce, color_shift))

    def queue_next_turn(self, lock_frames=30, wait_for_projectiles=False):
        """Delay the next turn until cinematic effects complete."""
        self.pending_next_turn = True
        self.animation_lock_timer = lock_frames
        self.waiting_for_projectiles = wait_for_projectiles
        self.state = "ANIMATING"

    def process_animation_lock(self):
        if not self.pending_next_turn or self.paused:
            return
        # Don't process turn while death message is showing
        if self.death_message_timer > 0:
            return
        if self.waiting_for_projectiles:
            return
        if self.animation_lock_timer > 0:
            self.animation_lock_timer -= 1
            return
        self.pending_next_turn = False
        self.animation_lock_timer = 0
        self.state = "IDLE"
        self.next_turn()

    def toggle_pause(self):
        self.paused = not self.paused
        state_text = "PAUSED" if self.paused else "RESUMED"
        self.log(f"Game {state_text.lower()}" )

    def exit_match(self):
        self.stop_background_polling()  # Clean up background thread
        self.manager.change_scene("START")

    def sync_with_server(self, use_cached=False):
        if not self.multiplayer: return None
        
        # Use cached state if available and requested
        if use_cached and self.cached_state:
            return self.cached_state
            
        state = self.client.get_state(self.game_id)
        if not state: return None
        
        self.cached_state = state  # Cache for reuse
        
        # Helper to sync a team
        def sync_team(local_team, server_team_data):
            # Sync active index
            if "active_index" in server_team_data:
                local_team.active_index = server_team_data["active_index"]
                
            for i, m_data in enumerate(server_team_data["members"]):
                if i < len(local_team.members):
                    local_char = local_team.members[i]
                    local_char.hp = m_data["hp"]
                    local_char.resource = m_data["resource"]
                    # Sync effects if needed, but might be visual glitchy
        
        # Server team 0 is Host, team 1 is Joiner
        # If I am Host (0): t1=team0, t2=team1
        # If I am Joiner (1): t1=team1, t2=team0 (swapped in init)
        
        if self.player_idx == 0:
            sync_team(self.t1, state["teams"]["0"])
            sync_team(self.t2, state["teams"]["1"])
        else:
            sync_team(self.t1, state["teams"]["1"])
            sync_team(self.t2, state["teams"]["0"])
            
        return state
    
    def submit_action_async(self, action_data):
        """Background thread to submit action."""
        try:
            resp = self.client.submit_action(self.game_id, self.player_idx, action_data)
            with self.move_lock:
                self.pending_action_result = {"ok": resp and resp.get("ok"), "error": resp.get("error"), "action": action_data}
        except Exception as e:
            print(f"Action submission error: {e}")
            with self.move_lock:
                self.pending_action_result = {"ok": False, "error": str(e), "action": action_data}

    def poll_server_async(self):
        """Background thread function to poll server without blocking main thread."""
        import time
        while self.polling_active:
            try:
                # Send heartbeat with player_idx
                state = self.client.get_state(self.game_id, self.player_idx)
                if state:
                    with self.state_lock:
                        self.pending_server_state = state
            except Exception as e:
                print(f"Background polling error: {e}")
            time.sleep(0.05)  # Poll every 0.05 second (20Hz) for smoother updates
    
    def start_background_polling(self):
        """Start background thread for server polling."""
        if not self.polling_active:
            self.polling_active = True
            self.polling_thread = threading.Thread(target=self.poll_server_async, daemon=True)
            self.polling_thread.start()
            print("🌐 Started background polling")
    
    def stop_background_polling(self):
        """Stop background polling thread."""
        if self.polling_active:
            self.polling_active = False
            if self.polling_thread:
                self.polling_thread.join(timeout=2)  # Wait up to 2 seconds
            print("🛑 Stopped background polling")

    def next_turn(self):

        if not self.multiplayer:
            if self.t1.is_defeated():
                self.manager.game_over("Defeat!")
                return
            if self.t2.is_defeated():
                self.manager.game_over("Victory!")
                return

        active_t1 = self.t1.get_active_member()
        if not active_t1.is_alive():
            self.log(f"{active_t1.name} fell!")
            # Auto-switch if possible
            living_members = [i for i, m in enumerate(self.t1.members) if m.is_alive()]
            if living_members:
                self.t1.active_index = living_members[0]
                self.log(f"Go {self.t1.get_active_member().name}!")
                self.spawn_particle(200, 280, (255, 255, 255), (0,0), 30, size=10)
                # Don't return, continue to next turn logic or restart turn?
                # If we just swapped, we should probably let the new char act immediately or reset.
                # Recursive call to handle the new state
                self.next_turn() 
                return
            else:
                self.manager.game_over("Defeat!")
                return

        active_t2 = self.t2.get_active_member()
        if not active_t2.is_alive():
             self.log(f"{active_t2.name} fell!")
             self.ai_swap()
             return

        # Toggle turn locally (Background polling will handle sync/correction)
        self.current_team_idx = 1 - self.current_team_idx
        
        current_team = self.teams[self.current_team_idx]
        attacker = current_team.get_active_member()
        
        attacker.update_effects()
        # Check if attacker died from status effects (e.g. Burn)
        if not attacker.is_alive():
             self.check_and_switch_dead_character(attacker, current_team)
             # If they died, we need to stop this turn and potentially switch
             # check_and_switch_dead_character sets pending_team_switch and death_message_timer
             # We should probably return here to let the update loop handle the death message
             return
             
        attacker.regen_resource()
        
        self.buttons = []
        if current_team == self.t1:
            self.state = "PLAYER_ACTION"
            self.action_prompt = f"{attacker.name}: choose an ability"
            actions = attacker.get_actions()
            cols = 2
            btn_w, btn_h = 240, 50
            spacing_x, spacing_y = 30, 10
            grid_width = cols * btn_w + (cols - 1) * spacing_x
            start_x = (SCREEN_WIDTH - grid_width) // 2
            start_y = SCREEN_HEIGHT - 140
            for i, action in enumerate(actions):
                row = i // cols
                col = i % cols
                btn_x = start_x + col * (btn_w + spacing_x)
                btn_y = start_y + row * (btn_h + spacing_y)
                data = ACTION_DATA.get(action, {"cost": 0, "info": ""})
                subtext = f"{data['cost']} {attacker.resource_type[:3]} | {data['info']}"
                btn = Button(btn_x, btn_y, btn_w, btn_h, action, lambda a=action: self.select_action(a), subtext=subtext)
                if attacker.resource < data["cost"]:
                    btn.disabled = True
                self.buttons.append(btn)

            teammate_alive = any(m.is_alive() and m != attacker for m in self.t1.members)
            tag_color = (200, 150, 0) if teammate_alive else (100, 100, 100)
            tag_cb = self.setup_tag_menu if teammate_alive else lambda: None
            tag_btn_x = start_x + grid_width + 40
            tag_btn_y = start_y
            # TAG and SKIP buttons: slightly bigger than attack buttons
            special_btn_w = 160  # Bigger than attack (240) but not too wide
            special_btn_h = 60   # Taller than attack (50)
            tag_btn = Button(tag_btn_x, tag_btn_y, special_btn_w, special_btn_h, "TAG", tag_cb, color=tag_color)
            tag_btn.subtext = "Swap ally"
            if not teammate_alive:
                tag_btn.disabled = True
            self.buttons.append(tag_btn)
            
            # Skip Turn button
            skip_btn_x = tag_btn_x
            skip_btn_y = tag_btn_y + special_btn_h + 10
            skip_btn = Button(skip_btn_x, skip_btn_y, special_btn_w, special_btn_h, "SKIP", lambda: self.select_action("Skip Turn"), color=(80, 80, 120))
            skip_btn.subtext = "Pass turn"
            self.buttons.append(skip_btn)
        else:
            if self.multiplayer:
                self.state = "WAITING_FOR_OPPONENT"
                self.action_prompt = "Waiting for opponent..."
                self.start_background_polling()
            else:
                self.state = "ANIMATING"
                self.action_prompt = f"{attacker.name} is preparing an attack..."
                pygame.time.set_timer(pygame.USEREVENT, 1000, 1)

    def setup_tag_menu(self):
        self.state = "TAG_SELECT"
        self.action_prompt = "Choose a teammate to tag in"
        self.buttons = []
        x_pos = SCREEN_WIDTH // 2 - 100
        y_pos = 200
        for i, member in enumerate(self.t1.members):
            if member.is_alive() and member != self.t1.get_active_member():
                btn = Button(x_pos, y_pos + i*70, 200, 60, member.name, lambda idx=i: self.perform_tag(idx))
                self.buttons.append(btn)
        if self.t1.get_active_member().is_alive():
            cancel = Button(x_pos, y_pos + len(self.t1.members)*70 + 20, 200, 50, "Cancel", self.cancel_selection, color=(100, 50, 50))
            self.buttons.append(cancel)

    def perform_tag(self, new_index):
        print(f"🔄 Performing Tag to Index {new_index}...")
        
        # OPTIMISTIC UI: Execute immediately locally
        self.t1.active_index = new_index
        self.t1.get_active_member().x = -200
        self.log(f"Tagged in {self.t1.get_active_member().name}!")
        self.spawn_particle(200, 280, (255, 255, 255), (0,0), 30, size=10)
        
        if self.multiplayer:
            # Send tag action to server in background
            self.state = "SENDING_ACTION"
            self.action_prompt = "Switching..."
            self.buttons = []
            self.waiting_for_server_confirmation = True # Ignore server updates until confirmed
            print(f"📡 Sending tag action to server (Optimistic)...")
            action_data = {
                "type": "tag",
                "target_index": new_index
            }
            threading.Thread(target=self.submit_action_async, args=(action_data,), daemon=True).start()
            
            # Manually trigger next turn logic locally
            self.next_turn()
        else:
            # Local mode
            self.next_turn()

    def ai_swap(self):
        for i, m in enumerate(self.t2.members):
            if m.is_alive():
                self.t2.active_index = i
                m.x = SCREEN_WIDTH + 200
                self.log(f"Enemy tagged in {m.name}!")
                return
    
    def check_and_switch_dead_character(self, character, team):
        """Check if a character died and show death message for 3 seconds before switching"""
        if character.hp <= 0:
            # Mark as dead by setting hp to 0 or less
            character.hp = min(0, character.hp)
            self.log(f"{character.name} has fallen!")
            
            # Set up centered death message for 3 seconds
            self.death_message_text = f"{character.name} has fallen!"
            self.death_message_timer = 180  # 3 seconds at 60 FPS
            self.pending_team_switch = (character, team)  # Store for later switch
            
            # Spawn death particles
            for _ in range(10):
                angle = random.uniform(0, 6.28)
                vx = math.cos(angle) * 3
                vy = math.sin(angle) * 3
                self.spawn_particle(character.x + 100, character.y + 100, (150, 150, 150), (vx, vy), 40, size=5)
            
            return True  # Death registered
    
    def perform_delayed_team_switch(self):
        """Perform the team switch after death message timer expires"""
        if not self.pending_team_switch:
            return False
        
        character, team = self.pending_team_switch
        self.pending_team_switch = None
        
        # Switch to next alive teammate
        living_members = [i for i, m in enumerate(team.members) if m.is_alive()]
        if living_members:
            # Switch to first alive member
            team.active_index = living_members[0]
            new_char = team.get_active_member()
            
            if team == self.t2:
                new_char.x = SCREEN_WIDTH + 200
                dest_x = SCREEN_WIDTH - 400
            else:
                new_char.x = -200
                dest_x = 200
                
            self.log(f"{new_char.name} steps forward!")
            self.spawn_particle(dest_x + 100, 330, (255, 255, 0), (0, -2), 30, size=15)
            
            # Now proceed with next turn after switch
            self.pending_next_turn = False
            self.animation_lock_timer = 0
            self.state = "IDLE"
            self.next_turn()
            return True  # Switched successfully
        return False  # No one left to switch to

    def select_action(self, action_name):
        if self.state != "PLAYER_ACTION":
            return
        attacker = self.t1.get_active_member()
        target = self.t2.get_active_member()
        if action_name in ["Heal", "Blessing", "Purify", "Pray"]: target = attacker
        self.buttons = []
        
        # OPTIMISTIC UI: Execute immediately locally
        self.execute_move(attacker, target, action_name)
        
        if self.multiplayer:
            # Send action to server asynchronously
            self.state = "SENDING_ACTION"
            self.action_prompt = "Sending action..."
            self.waiting_for_server_confirmation = True # Ignore server updates until confirmed
            action_data = {
                "type": "attack",
                "move": action_name
            }
            threading.Thread(target=self.submit_action_async, args=(action_data,), daemon=True).start()

    def cancel_selection(self):
        self.current_team_idx = 1 - self.current_team_idx
        self.next_turn()

    def restore_resource(self, character, amount):
        """Replenish resource and show floating feedback."""
        before = character.resource
        character.resource = min(character.max_resource, character.resource + amount)
        gained = character.resource - before
        if gained > 0:
            color = (50, 255, 200) if character.resource_type == "Mana" else (255, 255, 120)
            self.floating_texts.append(
                FloatingText(character.x + 50, character.y - 30, f"+{gained} {character.resource_type[:3]}", color)
            )
        return gained

    def execute_move(self, attacker, target, move_name):
        # Handle Skip Turn
        if move_name == "Skip Turn":
            self.log(f"{attacker.name} skipped their turn!")
            self.pending_next_turn = True
            self.animation_lock_timer = 20  # Short delay
            return
        
        # Handle Tag Team
        if move_name.startswith("Tag:"):
            try:
                new_idx = int(move_name.split(":")[1])
                print(f"📥 Received Tag:{new_idx} from {attacker.name}")
                # Determine which team
                if attacker in self.t1.members:
                    team = self.t1
                    print("👉 Tagging Team 1 (Local/Host)")
                else:
                    team = self.t2
                    print("👉 Tagging Team 2 (Opponent)")
                
                team.active_index = new_idx
                team.get_active_member().x = -200 if team == self.t1 else SCREEN_WIDTH + 200
                self.log(f"{attacker.name} tagged out!")
                self.spawn_particle(200 if team == self.t1 else SCREEN_WIDTH-200, 280, (255, 255, 255), (0,0), 30, size=10)
                self.next_turn()
                return
            except Exception as e:
                print(f"❌ Execute Tag Error: {e}")
                pass

        success = False
        pending_damage = 0  # Track damage for projectile attacks (calculate FIRST)
        skip_hit_fx = False
        extra_lock = 0
        
        # Calculate damage and resource costs BEFORE creating projectiles
        if isinstance(attacker, Warrior):
            if move_name == "Slash":
                if attacker.resource >= 10:
                    attacker.resource -= 10
                    pending_damage = int(25 / target.def_mod)
                    self.restore_resource(attacker, 3)
                    success = True
            elif move_name == "Power Strike":
                if attacker.resource >= 20:
                    attacker.resource -= 20
                    pending_damage = int(40 / target.def_mod)
                    self.restore_resource(attacker, 5)
                    success = True
            elif move_name == "Shield Bash": 
                if attacker.resource >= 15:
                    attacker.resource -= 15
                    self.restore_resource(attacker, 4)
                    success = True
            elif move_name == "Spin Slash":
                if attacker.resource >= 25:
                    attacker.resource -= 25
                    pending_damage = int(35 / target.def_mod)  # Store damage for delayed application
                    self.restore_resource(attacker, 6)
                    success = True
        elif isinstance(attacker, Archer):
            if move_name == "Quick Shot":
                if attacker.resource >= 10:
                    attacker.resource -= 10
                    pending_damage = int(20 / target.def_mod)
                    self.restore_resource(attacker, 3)
                    success = True
            elif move_name == "Double Arrow":
                if attacker.resource >= 20:
                    attacker.resource -= 20
                    pending_damage = int((15 * 2 * attacker.attack_mod) / target.def_mod)
                    self.restore_resource(attacker, 5)
                    success = True
            elif move_name == "Piercing":
                if attacker.resource >= 25:
                    attacker.resource -= 25
                    pending_damage = int(30 * attacker.attack_mod * 1.5 / target.def_mod)
                    self.restore_resource(attacker, 6)
                    success = True
            elif move_name == "Cripple":
                if attacker.resource >= 15:
                    attacker.resource -= 15
                    pending_damage = 15
                    target.apply_effect(Effect("Weakness", 2, 0))
                    self.restore_resource(attacker, 4)
                    success = True
        elif isinstance(attacker, Mage):
            if move_name == "Magic Bolt":
                if attacker.resource >= 10:
                    attacker.resource -= 10
                    pending_damage = int(25 * attacker.attack_mod / target.def_mod)
                    self.restore_resource(attacker, 3)
                    success = True
            elif move_name == "Fireball":
                if attacker.resource >= 20:
                    attacker.resource -= 20
                    pending_damage = int(40 * attacker.attack_mod / target.def_mod)
                    target.apply_effect(Effect("Burn", 2, 5))
                    self.restore_resource(attacker, 5)
                    success = True
            elif move_name == "Chain":
                if attacker.resource >= 25:
                    attacker.resource -= 25
                    pending_damage = int(25 * attacker.attack_mod / target.def_mod)
                    self.restore_resource(attacker, 6)
                    success = True
            elif move_name == "Drain":
                if attacker.resource >= 15:
                    attacker.resource -= 15
                    pending_damage = int(20 / target.def_mod)
                    self.restore_resource(attacker, 10)
                    success = True
        elif isinstance(attacker, Priest):
            if move_name == "Smite":
                if attacker.resource >= 10:
                    attacker.resource -= 10
                    pending_damage = int(20 * attacker.attack_mod / target.def_mod)
                    self.restore_resource(attacker, 3)
                    success = True
            elif move_name == "Judgement":
                if attacker.resource >= 20:
                    attacker.resource -= 20
                    pending_damage = int(35 * attacker.attack_mod / target.def_mod)
                    self.restore_resource(attacker, 5)
                    success = True
            elif move_name == "Holy Nova":
                if attacker.resource >= 25:
                    attacker.resource -= 25
                    pending_damage = int(20 * attacker.attack_mod / target.def_mod)
                    self.restore_resource(attacker, 6)
                    success = True
            elif move_name == "Pray":
                if attacker.resource >= 15:
                    attacker.resource -= 15
                    attacker.hp = min(attacker.max_hp, attacker.hp + 30)
                    success = True
        elif isinstance(attacker, Somesh):
            if move_name == "Charged Spark":
                if attacker.resource >= 12:
                    attacker.resource -= 12
                    pending_damage = int(50 * attacker.attack_mod / target.def_mod)
                    success = True
            elif move_name == "Fah!!!":
                if attacker.resource >= 50:
                    attacker.resource -= 50
                    pending_damage = 999  # Instant kill damage
                    success = True
            elif move_name == "Run Man":
                if attacker.resource >= 15:
                    attacker.resource -= 15
                    pending_damage = int(35 * attacker.attack_mod / target.def_mod)
                    success = True
            elif move_name == "Spark":
                if attacker.resource >= 25:
                    attacker.resource -= 25
                    pending_damage = int(50 * attacker.attack_mod / target.def_mod)
                    success = True
            else:
                # Fallback for standard attacks if any
                attacker.target_x = attacker.x + target_x_offset if attacker in self.t1.members else attacker.x - target_x_offset
        
        # Ifresource check failed, log and end turn
        if not success:
            self.log("Not enough resource!")
            self.next_turn()
            return
        
        # Crit / Miss Logic - REMOVED as requested
        is_crit = False
        is_miss = False
        # if success and pending_damage > 0 and move_name not in ["Heal", "Pray", "Buffs..."]:
        #      # 10% Crit, 5% Miss
        #      roll = random.random()
        #      if roll < 0.05:
        #          is_miss = True
        #          pending_damage = 0
        #          self.floating_texts.append(FloatingText(target.x + 50, target.y - 20, "MISS", (200, 200, 200)))
        #      elif roll < 0.15: # 10% chance (0.05 to 0.15)
        #          is_crit = True
        #          pending_damage = int(pending_damage * 1.5)
        #          self.floating_texts.append(FloatingText(target.x + 50, target.y - 40, "CRIT!", (255, 215, 0), size=60))

        # Animation Lunge (only if successful)
        target_x_offset = 50
        
        if move_name == "Shield Bash":
             # Charge all the way to the enemy with multi-frame animation!
             if attacker in self.t1.members:
                 # Player attacking enemy - stop right in front (220px gap)
                 attacker.target_x = target.x - 220
             else:
                 # Enemy attacking player - stop right in front
                 attacker.target_x = target.x + 220
             
             # Start bash animation sequence
             attacker.bash_animation_frame = 0
             attacker.bash_animation_timer = 0
             
             # Store target for delayed damage
             attacker.pending_bash_target = target
             skip_hit_fx = True  # Delay impact effects until hit
             extra_lock = max(extra_lock, 90)
        elif move_name == "Slash" and isinstance(attacker, Warrior):
            attacker.current_sprite_override = "warrior_slash"
            attacker.target_x = attacker.x + target_x_offset if attacker in self.t1.members else attacker.x - target_x_offset
        elif move_name == "Power Strike" and isinstance(attacker, Warrior):
            attacker.current_sprite_override = "warrior_power_slash"
            attacker.target_x = attacker.x + target_x_offset if attacker in self.t1.members else attacker.x - target_x_offset
        elif move_name == "Spin Slash" and isinstance(attacker, Warrior):
            # Two-frame spin slash animation - start with windup (spinslash0)
            attacker.current_sprite_override = "warrior_spinslash0"
            print(f"🎬 Spin Slash initiated - Setting warrior_spinslash0 sprite for {attacker.name}")
            attacker.spin_slash_frame = 0  # 0 = windup, 1 = charge
            attacker.spin_slash_timer = 0
            # Set target_x to current position + 1 to prevent immediate impact detection
            # We need target_x != 0 to avoid "no target" condition, but close enough to stay in place
            attacker.target_x = attacker.x + 0.1  # Tiny offset to prevent impact trigger
            # Store the actual target for later
            if attacker in self.t1.members:
                attacker.spin_slash_target_x = target.x - 150
            else:
                attacker.spin_slash_target_x = target.x + 150
            # Enable vibration effect for both frames
            attacker.vibrate_timer = 70  # Longer duration for both frames
            attacker.vibrate_intensity = 8
            attacker.spin_slash_active = True  # Mark as active so sprite isn't cleared
        elif isinstance(attacker, Archer):
            # All archer attacks use the fire animation
            attacker.current_sprite_override = "archer_fire"
            attacker.target_x = attacker.x  # Archer stays in place
            
            # Archer Animation Logic
            if move_name == "Quick Shot":
                attacker.hit_pause_timer = 20
            elif move_name == "Double Arrow":
                attacker.hit_pause_timer = 30
            elif move_name == "Piercing":
                # Charge up effect
                for _ in range(20):
                    angle = random.uniform(0, 6.28)
                    dist = random.uniform(20, 60)
                    self.spawn_particle(
                        attacker.x + 100 + math.cos(angle)*dist, 
                        attacker.y + 100 + math.sin(angle)*dist,
                        (0, 200, 255),
                        (-math.cos(angle)*2, -math.sin(angle)*2), # Suck in
                        30,
                        size=3,
                        shape="energy"
                    )
                attacker.hit_pause_timer = 45
            elif move_name == "Cripple":
                # Purple glow
                for _ in range(15):
                    self.spawn_particle(
                        attacker.x + 100 + random.randint(-20, 20), 
                        attacker.y + 100 + random.randint(-20, 20),
                        (150, 0, 255),
                        (0, -1),
                        40,
                        size=4,
                        shape="ember"
                    )
                attacker.hit_pause_timer = 25
        elif isinstance(attacker, Mage):
            # Mage attack animations
            if move_name == "Magic Bolt":
                attacker.current_sprite_override = "mage_attack"
            elif "Fireball" in move_name:
                attacker.current_sprite_override = "mage_fireball"
            attacker.target_x = attacker.x  # Mage stays in place
        elif isinstance(attacker, Priest):
            if move_name == "Pray":
                attacker.current_sprite_override = "priest_heal"
                attacker.hit_pause_timer = max(attacker.hit_pause_timer, 45)
            else:
                attacker.current_sprite_override = "priest_attack"
                attacker.hit_pause_timer = max(attacker.hit_pause_timer, 30)
            attacker.target_x = attacker.x  # Priest channels in place
        elif isinstance(attacker, Somesh):
            # Somesh attack animations
            if move_name == "Charged Spark":
                attacker.current_sprite_override = "somesh_dixon"
                attacker.target_x = attacker.x  # Somesh stays in place
            elif move_name == "Fah!!!":
                attacker.current_sprite_override = "somesh_fah"
                attacker.target_x = attacker.x  # Stay in place for epic attack
            elif move_name == "Backsplash":
                attacker.current_sprite_override = "somesh_fireball"
                attacker.target_x = attacker.x  # Fire in place for backsplash
                attacker.hit_pause_timer = max(attacker.hit_pause_timer, 25)
            elif move_name == "Spark":
                attacker.target_x = attacker.x # Stay in place for Diddler
            else:
                attacker.target_x = attacker.x + target_x_offset if attacker in self.t1.members else attacker.x - target_x_offset
        else:
            attacker.target_x = attacker.x + target_x_offset if attacker in self.t1.members else attacker.x - target_x_offset
        
        # Projectile Logic
        # Determine if attacker is on left (t1) or right (t2)
        is_player_side = attacker in self.t1.members
        
        # Start position: Spawn from distance from player
        if is_player_side:
            start_x = attacker.x + 140  # Player side: spawn 140px to the right
        else:
            start_x = attacker.x + 30   # Enemy side: spawn 30px to the right (facing left)
        start_y = attacker.y + 75
        
        # End position: Land on the CENTER of the opponent (not behind)
        end_x = target.x + 100  # Center of character sprite
        end_y = target.y + 75
        
        # Adjust arrow spawn position to match bow for archers
        if isinstance(attacker, Archer):
            # Already set above, but fine-tune Y position for bow
            start_y = attacker.y + 80  # Moved lower to match bow position
        
        proj_list = []
        projectile_wait = False
        
        if move_name == "Double Arrow":
            proj_list.append((start_y - 20, end_y - 20, self.manager.assets["arrow"], None, False, False))
            proj_list.append((start_y + 20, end_y + 20, self.manager.assets["arrow"], None, False, False))
        # REMOVED DUPLICATE CHAIN AND PIERCING BLOCKS HERE TO USE EPIC VERSIONS BELOW
        elif move_name == "Cripple":
             proj_list.append((start_y, end_y, self.manager.assets["arrow_purple"], (200, 0, 255), False, False))
        elif move_name == "Power Strike":
             # Start farther out (120px) to match blade, fade in, and vibrate
             start_x_slash = attacker.x + 120 if attacker in self.t1.members else attacker.x + 30
             proj_list.append((start_y, end_y, self.manager.assets["slash_red"], (255, 0, 0), True, True))
        elif "Fireball" in move_name:
             proj_list.append((start_y, end_y, self.manager.assets["fireball"], (255, 100, 0), False, False))
             # Hold mage sprite for visual feedback
             if isinstance(attacker, Mage):
                 attacker.hit_pause_timer = 20
        elif "Bolt" in move_name:
             # Instant lightning effect instead of projectile
             self.particles.append(LightningEffect(target.x + 75, target.y + 75))
             # Apply damage immediately since there's no projectile
             target.hp -= pending_damage
             target.shake_timer = 10
             
             # Manual Hit Sprite Trigger
             if isinstance(target, Warrior) and target.current_sprite_override not in ["warrior_bash_charge", "warrior_bash_post"]:
                 target.current_sprite_override = "warrior_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Archer):
                 target.current_sprite_override = "archer_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Mage):
                 target.current_sprite_override = "mage_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Priest):
                  target.current_sprite_override = "priest_hit"
                  target.hit_animation_timer = 30
                  target.is_taking_hit = True
             elif isinstance(target, Somesh):
                  target.current_sprite_override = "somesh_hit"
                  target.hit_animation_timer = 30
                  target.is_taking_hit = True
                  
             self.floating_texts.append(FloatingText(target.x + 50, target.y, f"-{pending_damage}", (255, 50, 50)))
             skip_hit_fx = True
             # Hold mage sprite for visual feedback (30 frames = 0.5 seconds)
             if isinstance(attacker, Mage):
                 attacker.hit_pause_timer = 30
        elif move_name == "Smite":
             proj_list.append((start_y, end_y, self.manager.assets["blast"], (255, 255, 0), False, False))
        elif move_name == "Judgement":
             proj_list.append((start_y, end_y, self.manager.assets["blast"], (255, 215, 0), False, False))
        elif move_name == "Chain":
             # EPIC CHAIN LIGHTNING - Electric arcs with energy surges
             # Lightning bolts radiating from mage
             for i in range(8):
                 angle = (i / 8) * 6.28
                 vx = math.cos(angle) * 15
                 vy = math.sin(angle) * 15
                 self.spawn_particle(attacker.x + 130, attacker.y + 150, (150, 150, 255), (vx, vy), 30, size=18)
             # Electric arcs to target
             for _ in range(25):
                 rand_x = random.randint(-50, 50)
                 rand_y = random.randint(-50, 50)
                 self.spawn_particle(target.x + 130 + rand_x, target.y + 150 + rand_y, (200, 200, 255), (random.uniform(-5, 5), random.uniform(-5, 5)), 35, size=random.randint(6, 12))
             # Electric shockwave ripple
             self.particles.append(RippleEffect(target.x + 130, target.y + 150, 'purple'))
             self.shake_timer = 35
             target.hp -= pending_damage
             target.shake_timer = 45
             
             # Manual Hit Sprite Trigger
             if isinstance(target, Warrior) and target.current_sprite_override not in ["warrior_bash_charge", "warrior_bash_post"]:
                 target.current_sprite_override = "warrior_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Archer):
                 target.current_sprite_override = "archer_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Mage):
                 target.current_sprite_override = "mage_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Priest):
                  target.current_sprite_override = "priest_hit"
                  target.hit_animation_timer = 30
                  target.is_taking_hit = True
             elif isinstance(target, Somesh):
                  target.current_sprite_override = "somesh_hit"
                  target.hit_animation_timer = 30
                  target.is_taking_hit = True
                  
             # Check for death (Instant Damage)
             target_team = self.t1 if target in self.t1.members else self.t2
             self.check_and_switch_dead_character(target, target_team)

             self.floating_texts.append(FloatingText(target.x + 50, target.y, "CHAIN LIGHTNING!", (150, 150, 255)))
             self.floating_texts.append(FloatingText(target.x + 50, target.y + 50, f"-{pending_damage}", (255, 255, 0)))
             skip_hit_fx = True
             if isinstance(attacker, Mage):
                 attacker.hit_pause_timer = 50
             extra_lock = max(extra_lock, 70)
        elif move_name == "Holy Nova":
             # EPIC HOLY NOVA - Divine light explosion with healing aura
             # Divine light burst from priest
             for angle_deg in range(0, 360, 20):
                 angle_rad = math.radians(angle_deg)
                 vx = math.cos(angle_rad) * 12
                 vy = math.sin(angle_rad) * 12
                 self.spawn_particle(attacker.x + 130, attacker.y + 150, (255, 255, 200), (vx, vy), 45, size=20)
             # Holy explosion around target
             for _ in range(35):
                 angle = random.uniform(0, 6.28)
                 speed = random.uniform(6, 14)
                 vx = math.cos(angle) * speed
                 vy = math.sin(angle) * speed
                 self.spawn_particle(target.x + 130, target.y + 150, (255, 255, 150), (vx, vy), 60, size=random.randint(10, 18))
             # Golden ripple waves
             self.particles.append(RippleEffect(target.x + 130, target.y + 150, 'gold'))
             self.shake_timer = 30
             target.hp -= pending_damage
             target.shake_timer = 40
             
             # Manual Hit Sprite Trigger
             if isinstance(target, Warrior) and target.current_sprite_override not in ["warrior_bash_charge", "warrior_bash_post"]:
                 target.current_sprite_override = "warrior_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Archer):
                 target.current_sprite_override = "archer_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Mage):
                 target.current_sprite_override = "mage_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Priest):
                  target.current_sprite_override = "priest_hit"
                  target.hit_animation_timer = 30
                  target.is_taking_hit = True
             elif isinstance(target, Somesh):
                  target.current_sprite_override = "somesh_hit"
                  target.hit_animation_timer = 30
                  target.is_taking_hit = True
                  
             # Check for death (Instant Damage)
             target_team = self.t1 if target in self.t1.members else self.t2
             self.check_and_switch_dead_character(target, target_team)

             self.floating_texts.append(FloatingText(target.x + 50, target.y, "HOLY NOVA!", (255, 255, 100)))
             self.floating_texts.append(FloatingText(target.x + 50, target.y + 50, f"-{pending_damage}", (255, 200, 0)))
             skip_hit_fx = True
             if isinstance(attacker, Priest):
                 attacker.hit_pause_timer = 50
             extra_lock = max(extra_lock, 70)
             # Original projectiles for visual continuity (COSMETIC ONLY - damage=0)
             # We set pending_damage to 0 for these projectiles so they don't deal double damage
             # But we need to restore it later if we use it? No, it's local.
             # Actually, we can just pass 0 to the projectile constructor loop below if we change how we add them.
             # Or simpler: Add them here directly with 0 damage.
             self.projectiles.append(Projectile(start_y, start_y, end_x, end_y, self.manager.assets["blast"], speed=15, trail_color=(255, 255, 200), source_char=attacker, target_char=target, damage_amount=0))
             self.projectiles.append(Projectile(start_y - 40, start_y - 40, end_x, end_y, self.manager.assets["blast"], speed=15, trail_color=(255, 255, 200), source_char=attacker, target_char=target, damage_amount=0))
             self.projectiles.append(Projectile(start_y + 40, start_y + 40, end_x, end_y, self.manager.assets["blast"], speed=15, trail_color=(255, 255, 200), source_char=attacker, target_char=target, damage_amount=0))
        elif move_name == "Charged Spark":
             # Hold somesh sprite for visual feedback
             if isinstance(attacker, Somesh):
                 attacker.hit_pause_timer = 25
             proj_list.append((start_y, end_y, self.manager.assets["blast"], (150, 0, 150), False, False))
        elif move_name == "Fah!!!":
             # EPIC OVERPOWERED ATTACK - Ripples, massive shake, instant kill
             # Spawn ripple effects around attacker
             self.particles.append(RippleEffect(attacker.x + 130, attacker.y + 150))
             # Massive screen shake
             self.shake_timer = 60  # 1 second of intense shaking
             # Ground vibration particles everywhere
             for _ in range(50):
                 vx = random.uniform(-8, 8)
                 vy = random.uniform(-5, 5)
                 x_pos = random.randint(0, SCREEN_WIDTH)
                 y_pos = random.randint(SCREEN_HEIGHT // 2, SCREEN_HEIGHT)
                 self.spawn_particle(x_pos, y_pos, (255, random.randint(100, 200), 0), (vx, vy), 60, size=random.randint(8, 15))
             # Explosion particles around target
             for _ in range(30):
                 angle = random.uniform(0, 6.28)
                 speed = random.uniform(5, 15)
                 vx = math.cos(angle) * speed
                 vy = math.sin(angle) * speed
                 self.spawn_particle(target.x + 130, target.y + 150, (255, 0, 0), (vx, vy), 80, size=12)
             # Energy waves
             for i in range(5):
                 delay_offset = i * 10
                 self.spawn_particle(attacker.x + 130 + delay_offset, attacker.y + 150, (255, 255, 0), (10, 0), 40, size=20)
             # Apply instant damage
             target.hp -= pending_damage
             target.shake_timer = 60
             
             # Manual Hit Sprite Trigger
             if isinstance(target, Warrior) and target.current_sprite_override not in ["warrior_bash_charge", "warrior_bash_post"]:
                 target.current_sprite_override = "warrior_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Archer):
                 target.current_sprite_override = "archer_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Mage):
                 target.current_sprite_override = "mage_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Priest):
                  target.current_sprite_override = "priest_hit"
                  target.hit_animation_timer = 30
                  target.is_taking_hit = True
             elif isinstance(target, Somesh):
                  target.current_sprite_override = "somesh_hit"
                  target.hit_animation_timer = 30
                  target.is_taking_hit = True
                  
             # Check for death (Instant Damage)
             target_team = self.t1 if target in self.t1.members else self.t2
             self.check_and_switch_dead_character(target, target_team)

             self.floating_texts.append(FloatingImage(target.x + 50, target.y, self.manager.assets["fah_icon"]))
             self.floating_texts.append(FloatingText(target.x + 50, target.y + 50, f"-{pending_damage}", (255, 0, 0), size=28))
             skip_hit_fx = True
             # Play Fah!! sound effect and hold pose for audio duration
             audio_frames = 0
             if "fah" in self.manager.sounds:
                 sound = self.manager.sounds["fah"]
                 sound.play()
                 # Get audio length in seconds and convert to frames (60 FPS)
                 audio_length_seconds = sound.get_length()
                 audio_frames = int(audio_length_seconds * 60)
                 if isinstance(attacker, Somesh):
                     attacker.hit_pause_timer = audio_frames  # Hold pose for audio duration
             extra_lock = max(extra_lock, max(audio_frames, 150))
        elif move_name == "Run Man":
             # Running charge attack with animation frames r1->r2->r3->r4
             if isinstance(attacker, Somesh):
                 # Start running animation
                 attacker.run_animation_frame = 0
                 attacker.run_animation_timer = 0
                 
                 # Set target position (charge toward enemy)
                 if attacker in self.t1.members:
                     attacker.target_x = target.x - 150  # Stop in front of target
                 else:
                     attacker.target_x = target.x + 150
                 
                 # Impact particles when reached (will be handled when target_x == 0)
                 attacker.pending_bash_target = target  # Reuse this for Run Man damage delay
                 
                 # Damage will be applied on impact in draw_character update loop
                 skip_hit_fx = True  # We'll add custom effects
             extra_lock = max(extra_lock, 60)  # Duration for animation
        elif move_name == "Spark":
             # Use somesh_chain as POSE, but blast as projectile
             if isinstance(attacker, Somesh):
                 attacker.current_sprite_override = "somesh_chain"
                 attacker.hit_pause_timer = 45 # Hold pose
                 attacker.hit_animation_timer = 45 # Duration of sprite override
             
             # Create a purple blast projectile
             proj_list.append((start_y, end_y, self.manager.assets["blast"], (200, 0, 255), False, False))
        elif move_name == "Spin Slash":
             # EPIC SPIN SLASH - Vibrating warrior charges at enemy with spinning effects
             # Circular blade slashes around attacker as they charge
             for angle_offset in range(0, 360, 45):
                 angle_rad = math.radians(angle_offset)
                 vx = math.cos(angle_rad) * 12
                 vy = math.sin(angle_rad) * 12
                 self.spawn_particle(attacker.x + 130, attacker.y + 150, (192, 192, 192), (vx, vy), 35, size=15)
             
             # Store target for delayed impact damage (applied when warrior reaches target)
             attacker.pending_bash_target = target  # Reuse for spin slash
             attacker.spin_slash_active = True  # Flag to distinguish from bash
             attacker.spin_rotation = 0  # Start rotation animation
             
             skip_hit_fx = True  # Custom particles applied on impact
             extra_lock = max(extra_lock, 70)
        elif "Slash" in move_name:
             # Start farther out (120px) to match blade, fade in, and vibrate
             start_x_slash = attacker.x + 120 if attacker in self.t1.members else attacker.x + 30
             proj_list.append((start_y, end_y, self.manager.assets["slash"], None, True, True))
        elif move_name == "Piercing":
             # EPIC PIERCING SHOT - Time-slow effect with arrow afterimages
             # Multiple arrow trails for piercing effect
             for i in range(5):
                 trail_offset = i * -15
                 self.spawn_particle(start_x + trail_offset, start_y, (100, 200, 255), (15, 0), 25 + i*5, size=10)
             # Piercing impact burst
             for angle_step in range(0, 360, 30):
                 angle_rad = math.radians(angle_step)
                 vx = math.cos(angle_rad) * 10
                 vy = math.sin(angle_rad) * 10  
                 self.spawn_particle(target.x + 130, target.y + 150, (0, 255, 255), (vx, vy), 40, size=12)
             # Energy shockwave
             self.particles.append(RippleEffect(target.x + 130, target.y + 150, 'cyan'))
             self.shake_timer = 25
             
             # REMOVED INSTANT DAMAGE - Let projectile handle it to avoid double damage
             # target.hp -= pending_damage
             target.shake_timer = 35
             
             self.floating_texts.append(FloatingText(target.x + 50, target.y, "PIERCING!", (0, 255, 255)))
             # self.floating_texts.append(FloatingText(target.x + 50, target.y + 50, f"-{pending_damage}", (255, 0, 255))) # Projectile will show damage
             skip_hit_fx = True
             if isinstance(attacker, Archer):
                 attacker.hit_pause_timer = 45
             extra_lock = max(extra_lock, 65)
             # Create the main piercing arrow projectile
             proj_list.append((start_y, end_y, self.manager.assets["arrow"], (100, 200, 255), False, False))
        elif "Shot" in move_name:
             proj_list.append((start_y, end_y, self.manager.assets["arrow"], None, False, False))
             
        projectile_wait = len(proj_list) > 0

        for item in proj_list:
            if len(item) == 6:  # New format with fade_in and vibrate
                py, ey, img, trail, fade_in, vibrate = item
                # Use custom start_x for slashes if set
                sx = start_x_slash if 'start_x_slash' in locals() and (fade_in or vibrate) else start_x
                self.projectiles.append(Projectile(sx, py, end_x, ey, img, speed=20 if move_name == "Piercing" else 15, trail_color=trail, fade_in=fade_in, vibrate=vibrate, source_char=attacker, target_char=target, damage_amount=pending_damage))
            else:  # Old format for backwards compatibility
                py, ey, img, trail = item
                self.projectiles.append(Projectile(start_x, py, end_x, ey, img, speed=20 if move_name == "Piercing" else 15, trail_color=trail, source_char=attacker, target_char=target, damage_amount=pending_damage))

        # Visual effects and animations (after damage calculation and projectile creation)

        if success:

            if not proj_list:
                # No projectiles - this is a melee/instant attack, trigger hit animation immediately
                # This block now runs even if skip_hit_fx is True (for custom effects like Chain/Fah)
                if move_name not in ["Heal", "Guard", "Taunt", "Blessing", "Weakness", "Purify", "Pray", "Shield Bash", "Run Man"]:
                    if isinstance(target, Warrior) and target.current_sprite_override not in ["warrior_bash_charge", "warrior_bash_post"]:
                        print(f"🎯 Melee hit! Setting warrior_hit animation for {target.name} (move: {move_name})")
                        target.current_sprite_override = "warrior_hit"
                        target.hit_animation_timer = 30  # Show hit sprite for 30 frames
                        target.is_taking_hit = True
                    elif isinstance(target, Archer) and target.current_sprite_override != "archer_fire":
                        print(f"🎯 Melee hit! Setting archer_hit animation for {target.name} (move: {move_name})")
                        target.current_sprite_override = "archer_hit"
                        target.hit_animation_timer = 30
                        target.is_taking_hit = True
                    elif isinstance(target, Mage):
                        print(f"🎯 Melee hit! Setting mage_hit animation for {target.name} (move: {move_name})")
                        target.current_sprite_override = "mage_hit"
                        target.hit_animation_timer = 30
                        target.is_taking_hit = True
                    elif isinstance(target, Priest):
                        print(f"🎯 Melee hit! Setting priest_hit animation for {target.name} (move: {move_name})")
                        target.current_sprite_override = "priest_hit"
                        target.hit_animation_timer = 30
                        target.is_taking_hit = True
                    elif isinstance(target, Somesh):
                        print(f"🎯 Melee hit! Setting somesh_hit animation for {target.name} (move: {move_name})")
                        target.current_sprite_override = "somesh_hit"
                        target.hit_animation_timer = 30
                        target.is_taking_hit = True
                
                # Attack-Specific Impact Particles (Only if not skipped)
                if not skip_hit_fx:
                    if move_name not in ["Heal", "Guard", "Taunt", "Blessing", "Weakness", "Purify", "Pray"]:
                        # Determine particle type based on attack
                        if "Slash" in move_name or "Strike" in move_name or move_name == "Shield Bash":
                            # Metal sparks for physical attacks
                            for _ in range(8):
                                angle = random.uniform(0, 6.28)
                                speed = random.uniform(3, 7)
                                self.spawn_particle(
                                    target.x + 75 + random.randint(-10, 10),
                                    target.y + 75 + random.randint(-10, 10),
                                    (255, 220, 100),  # Metallic yellow
                                    (math.cos(angle) * speed, math.sin(angle) * speed),
                                    25,
                                    size=4,
                                    shape='spark',
                                    gravity=0.3
                                )
                        elif "Fireball" in move_name or "Burn" in move_name:
                            # Fiery embers
                            for _ in range(12):
                                angle = random.uniform(0, 6.28)
                                speed = random.uniform(2, 5)
                                self.spawn_particle(
                                    target.x + 75 + random.randint(-15, 15),
                                    target.y + 75 + random.randint(-15, 15),
                                    (255, 150, 50),  # Orange
                                    (math.cos(angle) * speed, math.sin(angle) * speed - 1),
                                    40,
                                    size=5,
                                    shape='ember',
                                    gravity=0.2,
                                    color_shift=(255, 0, 0)  # Fade to red
                                )
                        elif "Magic" in move_name or "Bolt" in move_name or "Drain" in move_name:
                            # Magic energy waves
                            for _ in range(10):
                                angle = random.uniform(0, 6.28)
                                speed = random.uniform(2, 6)
                                self.spawn_particle(
                                    target.x + 75,
                                    target.y + 75,
                                    (150, 100, 255),  # Purple
                                    (math.cos(angle) * speed, math.sin(angle) * speed),
                                    30,
                                    size=6,
                                    shape='energy'
                                )
                        elif "Smite" in move_name or "Judgement" in move_name:
                            # Holy light beams
                            for _ in range(6):
                                angle = random.uniform(-0.5, 0.5)  # Upward cone
                                self.spawn_particle(
                                    target.x + 75 + random.randint(-20, 20),
                                    target.y + 120,
                                    (255, 255, 200),  # Golden
                                    (math.sin(angle) * 2, -abs(math.cos(angle)) * 8),
                                    35,
                                    size=8,
                                    shape='energy',
                                    color_shift=(255, 255, 255)
                                )
                        elif "Shot" in move_name or "Arrow" in move_name:
                            # Debris/impact spray
                            for _ in range(6):
                                angle = random.uniform(0, 6.28)
                                speed = random.uniform(2, 5)
                                self.spawn_particle(
                                    target.x + 75,
                                    target.y + 75,
                                    (150, 150, 150),  # Gray debris
                                    (math.cos(angle) * speed, math.sin(angle) * speed),
                                    20,
                                    size=3,
                                    shape='circle',
                                    gravity=0.4,
                                    bounce=True
                                )
                        else:
                            # Default impact particles
                            for _ in range(5):
                                angle = random.uniform(0, 6.28)
                                speed = random.uniform(2, 4)
                                self.spawn_particle(
                                    target.x + 75,
                                    target.y + 75,
                                    (255, 100, 100),
                                    (math.cos(angle) * speed, math.sin(angle) * speed),
                                    20,
                                    size=4
                                )
                
                # Specific Visuals
                if move_name == "Heal":
                    for _ in range(5):
                        self.spawn_particle(target.x + 75 + random.randint(-20, 20), target.y + 75 + random.randint(-20, 20), (255, 255, 0), (0, -1), 30, size=15, shape="plus")
                elif move_name == "Pray":
                    for _ in range(10):
                        self.spawn_particle(target.x + 75 + random.randint(-20, 20), target.y + 75 + random.randint(-20, 20), (255, 255, 100), (0, -2), 40, size=10, shape="plus")
                    # Use Heal Icon for Pray
                    self.floating_texts.append(FloatingImage(target.x + 100, target.y + 50, self.manager.assets["heal_icon"]))
                elif move_name == "Shield Bash":
                     self.spawn_particle(target.x + 75, target.y + 75, (100, 100, 255), (0, 0), 20, size=15, shape="circle")
                elif move_name == "Spin Slash":
                     for _ in range(8):
                        angle = random.uniform(0, 6.28)
                        vx = math.cos(angle) * 5
                        vy = math.sin(angle) * 5
                        self.spawn_particle(target.x + 75, target.y + 75, (200, 200, 200), (vx, vy), 20, size=3)
                target.shake_timer = 10
                if move_name not in ["Heal", "Blessing", "Purify", "Pray"]:
                    self.floating_texts.append(FloatingImage(target.x + 100, target.y + 50, self.manager.assets["hit_icon"]))
            # else: projectiles exist - hit animation will trigger when projectile lands
            
            # Enhanced Screen Shake & Effects based on attack type
            if move_name in ["Power Strike", "Judgement", "Fah!!!", "Run Man"]:
                self.screen_shake.add_shake(12, 25)  # Heavy attacks
                self.screen_flash.flash((255, 255, 255), 10, 100) # Flash white
                if move_name == "Fah!!!":
                    self.slow_motion.trigger(0.2, 60) # Slow motion for ultimate
            elif move_name in ["Fireball", "Piercing", "Magic Bolt", "Spin Slash"]:
                self.screen_shake.add_shake(8, 15)  # Medium attacks
            elif move_name in ["Slash", "Quick Shot", "Smite"]:
                self.screen_shake.add_shake(4, 10)  # Light attacks
            
            # Also keep legacy shake for compatibility
            if move_name in ["Fireball", "Power Strike", "Piercing", "Judgement", "Magic Bolt"]:
                self.shake_timer = 15
            
            # Check if target died and switch immediately
            if move_name not in ["Heal", "Blessing", "Purify", "Pray"]:
                target_team = self.t1 if target in self.t1.members else self.t2
                self.check_and_switch_dead_character(target, target_team)
            lock_frames = max(30, extra_lock, getattr(attacker, "hit_pause_timer", 0))
            if projectile_wait:
                lock_frames = max(lock_frames, 45)
            self.queue_next_turn(lock_frames=lock_frames, wait_for_projectiles=projectile_wait)
        else:
            self.log("Not enough resource!")
            if self.current_team_idx == 0:
                 self.current_team_idx = 1
                 self.next_turn()

    def ai_turn(self):
        attacker = self.t2.get_active_member()
        target = self.t1.get_active_member()
        
        # 1. Survival Check (Tag out if low HP)
        if attacker.hp < attacker.max_hp * 0.3:
            for i, m in enumerate(self.t2.members):
                if m.is_alive() and m != attacker and m.hp > m.max_hp * 0.5:
                    self.t2.active_index = i
                    self.t2.members[i].x = SCREEN_WIDTH + 200
                    self.log(f"Enemy tags in {m.name}!")
                    self.next_turn()
                    return

        moves = attacker.get_actions()
        
        # Get resource costs for filtering
        move_costs = {move: ACTION_DATA.get(move, {}).get("cost", 0) for move in moves}
        
        # Filter moves by resource availability
        affordable_moves = [m for m in moves if move_costs[m] <= attacker.resource]
        
        # If no affordable moves, skip turn and regenerate
        if not affordable_moves:
            self.log(f"{attacker.name} is out of resources!")
            self.next_turn()
            return
        
        chosen_move = None
        
        # 2. Smart Defense (HP < 40% and has resources)
        if attacker.hp < attacker.max_hp * 0.4:
            defensive_moves = [m for m in affordable_moves if m in ["Heal", "Drain", "Pray"]]
            if defensive_moves:
                chosen_move = random.choice(defensive_moves)

        # 3. Aggression (Player HP < 30%)
        if not chosen_move and target.hp < target.max_hp * 0.3:
            aggressive_moves = [m for m in affordable_moves if m in ["Power Strike", "Piercing", "Fireball", "Double Arrow"]]
            if aggressive_moves:
                chosen_move = random.choice(aggressive_moves)
        
        # 4. Resource Conservation (Low resources < 30%)
        if not chosen_move and attacker.resource < attacker.max_resource * 0.3:
            cheap_moves = [m for m in affordable_moves if move_costs[m] <= 15]
            if cheap_moves:
                chosen_move = random.choice(cheap_moves)

        # 5. Default - Choose random affordable move
        if not chosen_move:
            chosen_move = random.choice(affordable_moves)

        # Set target for support moves
        if chosen_move in ["Heal", "Blessing", "Purify", "Pray"]:
            target = attacker
        
        self.log(f"{attacker.name} uses {chosen_move}!")
        self.execute_move(attacker, target, chosen_move)

    def handle_input(self, events):
        mouse_pos = pygame.mouse.get_pos()
        mouse_click = False
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.toggle_pause()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_click = True
            if event.type == pygame.USEREVENT and self.state == "ANIMATING":
                if self.paused:
                    self.ai_action_ready = True
                else:
                    self.ai_turn()

        if not self.paused and self.ai_action_ready and self.state == "ANIMATING":
            self.ai_action_ready = False
            self.ai_turn()

        if self.paused:
            if self.exit_match_btn.update(mouse_pos, mouse_click):
                self.exit_match_btn.callback()
            return

        if self.state not in ["PLAYER_ACTION", "TAG_SELECT"]:
            return
        
        for btn in self.buttons:
            if btn.update(mouse_pos, mouse_click): btn.callback()

    def update(self):
        if self.paused:
            return
        
        # Handle multiplayer action results
        if self.multiplayer and hasattr(self, 'pending_action_result'):
            with self.move_lock:
                if self.pending_action_result is not None:
                    result = self.pending_action_result
                    action_data = result.get("action", {})
                    self.pending_action_result = None
                    
                    if result.get("ok"):
                        print("✅ Action accepted by server (Optimistic UI - Already Executed)")
                        # We already executed the move locally, so we don't need to do anything here
                        # except maybe sync HP if we want to be super safe, but let's trust the logic for now
                        
                        # Just ensure we are back to IDLE/WAITING state if not already
                        if self.state == "SENDING_ACTION":
                             self.state = "WAITING_FOR_OPPONENT"
                             self.start_background_polling()
                        
                    else:
                        error = result.get("error", "Unknown error")
                        print(f"❌ Action rejected: {error}")
                        self.log(f"Error: {error}")
                        # Revert? For now just go back to action selection
                        self.state = "IDLE"
                        self.next_turn()
        
        if self.shake_timer > 0: self.shake_timer -= 1
        
        # Update all visual enhancement systems
        self.screen_shake.update()
        self.slow_motion.update()
        self.screen_flash.update()
        self.vignette.update()
        self.vignette.update()
        self.zoom.update()

        # Weather Updates
        if self.rain_effect:
            self.rain_effect.update()
            
            # Random Lightning
            if random.random() < 0.001: # 0.1% chance per frame (reduced from 0.5%)
                self.screen_flash.flash((255, 255, 255), 10, 150)
                self.particles.append(LightningEffect(random.randint(100, SCREEN_WIDTH-100), random.randint(100, SCREEN_HEIGHT-100)))

        
        # Death message timer countdown
        if self.death_message_timer > 0:
            self.death_message_timer -= 1
            if self.death_message_timer == 0:
                # Timer expired, perform the team switch
                self.perform_delayed_team_switch()
                self.death_message_text = ""

        # Victory Delay Timer
        if self.victory_pending:
            self.victory_timer -= 1
            if self.victory_timer <= 0:
                # Play victory sound if available
                if self.victory_result == "Victory!" and "victory" in self.manager.sounds:
                    self.manager.sounds["victory"].play()
                elif self.victory_result == "Victory!" and "menu_theme" in self.manager.sounds:
                     # Fallback to menu theme if no specific victory sound
                     pass 
                
                self.manager.game_over(self.victory_result)
                return
        
        # Update Clouds
        for cloud in self.clouds:
            cloud["x"] -= cloud["speed"]
            if cloud["x"] < -200:
                cloud["x"] = SCREEN_WIDTH + 200
                cloud["y"] = random.randint(0, 80)
        
        # Update character visual states
        for team in [self.t1, self.t2]:
            for char in team.members:
                if not char.is_alive():
                    # Death fade animation - DISABLED to show defeat sprite
                    # if char.is_dying and char.death_fade_alpha > 0:
                    #     char.death_fade_alpha = max(0, char.death_fade_alpha - 5)
                        
                    # Spawn dissolve particles (keep this for effect)
                    if char.is_dying and not char.death_particles_spawned:
                        for _ in range(20):
                            dx = random.uniform(-2, 2)
                            dy = random.uniform(-3, -1)
                            self.spawn_particle(
                                char.x + 75 + random.randint(-40, 40),
                                char.y + 100 + random.randint(-40, 40),
                                (200, 200, 200),
                                (dx, dy),
                                50,
                                size=4,
                                shape="energy"
                            )
                        char.death_particles_spawned = True
                else:
                    # Breathing animation
                    char.breathing_phase += 0.02
                    hp_ratio = char.hp / char.max_hp
                    if hp_ratio < 0.3:
                        # Rapid breathing when low HP
                        char.breathing_scale = 1.0 + 0.04 * math.sin(char.breathing_phase * 2)
                    else:
                        # Normal breathing
                        char.breathing_scale = 1.0 + 0.02 * math.sin(char.breathing_phase)
                    
                    # Update status effect auras
                    char.aura_color = None
                    char.aura_intensity = 0
                    for effect in char.effects:
                        if effect == "burn":
                            char.aura_color = (255, 100, 50)
                            char.aura_intensity = 80
                        elif effect == "weakness":
                            char.aura_color = (150, 50, 150)
                            char.aura_intensity = 60
                        elif effect == "blessing":
                            char.aura_color = (255, 220, 100)
                            char.aura_intensity = 100
                        # Add more effect auras as needed
                    
                    # Spawn aura particles
                    if char.aura_color and random.random() < 0.2:
                        angle = random.uniform(0, 6.28)
                        radius = 50
                        px = char.x + 75 + math.cos(angle) * radius
                        py = char.y + 100 + math.sin(angle) * radius
                        self.spawn_particle(
                            px, py,
                            char.aura_color,
                            (math.cos(angle) * 0.5, math.sin(angle) * 0.5),
                            30,
                            size=3,
                            shape="energy"
                        )
                        
                    # Update Dynamic Animations
                    # Return scale to base
                    if char.current_scale > char.base_scale:
                        char.current_scale = max(char.base_scale, char.current_scale - 0.05)
                    elif char.current_scale < char.base_scale:
                        char.current_scale = min(char.base_scale, char.current_scale + 0.05)
                        
                    # Return rotation to 0
                    if char.rotation > 0:
                        char.rotation = max(0, char.rotation - 5)
                    elif char.rotation < 0:
                        char.rotation = min(0, char.rotation + 5)
                        
                    # Hit flash timer
                    if char.hit_flash_timer > 0:
                        char.hit_flash_timer -= 1
        
        # Vignette update removed
        
        # Spawn ambient particles
        self.ambient_particle_timer += 1
        if self.ambient_particle_timer % 10 == 0:  # Every 10 frames
            # Dust motes
            if random.random() < 0.3:
                x = random.randint(0, SCREEN_WIDTH)
                y = random.randint(100, SCREEN_HEIGHT - 100)
                self.spawn_particle(
                    x, y,
                    (200, 200, 180),
                    (random.uniform(-0.2, 0.2), random.uniform(-0.5, 0)),
                    100,
                    size=2,
                    shape="circle"
                )
        
        # Idle Particles
        if self.t1.get_active_member(): self.t1.get_active_member().update_idle_particles(self)
        if self.t2.get_active_member(): self.t2.get_active_member().update_idle_particles(self)
        
        # Limit particles for performance
        if len(self.particles) > self.max_particles:
            self.particles = self.particles[-self.max_particles:]
        
        self.process_animation_lock()
        
        # Async Multiplayer Polling - Check for pending state from background thread
        if self.multiplayer and self.state == "WAITING_FOR_OPPONENT":
            # Start background polling if not already running
            if not self.polling_active:
                self.start_background_polling()
            
            # Check if background thread has new state (non-blocking!)
            with self.state_lock:
                if self.pending_server_state:
                    state = self.pending_server_state
                    self.pending_server_state = None  # Clear pending state
                    
                    
                    
                    # Check if turn changed to me
                    # CRITICAL FIX: Only process this if we are currently waiting
                    if state["turn"] == self.player_idx:
                        if self.waiting_for_server_confirmation:
                            # Server hasn't processed our move yet (turn is still ours)
                            # IGNORE this state to prevent rubber-banding
                            pass
                        elif self.state == "WAITING_FOR_OPPONENT":
                            # Opponent moved!
                            self.stop_background_polling()
                        last_action = state.get("last_action")
                        if last_action:
                            action_type = last_action.get("type")
                            
                            if action_type == "attack":
                                move_name = last_action.get("move")
                                attacker = self.t2.get_active_member()
                                target = self.t1.get_active_member()
                                if move_name in ["Heal", "Blessing", "Purify", "Pray"]:
                                    target = attacker
                                
                                self.last_processed_move = move_name
                                self.log(f"Opponent used {move_name}!")
                                self.execute_move(attacker, target, move_name)
                            elif action_type == "tag":
                                # Sync to get updated opponent team state
                                self.sync_with_server()
                                new_char = self.t2.get_active_member()
                                if new_char:
                                    new_char.x = SCREEN_WIDTH + 200  # Off screen, will slide in
                                    self.log(f"Opponent switched to {new_char.name}!")
                                
                                # CRITICAL FIX: Manually advance turn for tag since execute_move isn't called
                                self.next_turn()
                        else:
                            # No last action (maybe first turn or just passing?)
                            # Just advance to my turn
                            self.next_turn()
                        
                        # Clear last_action from our local copy to prevent reprocessing
                        state["last_action"] = None
                    
                    elif state["turn"] != self.player_idx and self.waiting_for_server_confirmation:
                        # Turn has changed, meaning server accepted our move!
                        self.waiting_for_server_confirmation = False
                        print("✅ Server confirmed move (Optimistic UI)")
                    
                    
                        # Check for Game Over status from server
                    if state.get("status") == "FINISHED" and not self.victory_pending:
                        self.stop_background_polling()
                        # Determine winner based on server state
                        # Server team 0 is Host, team 1 is Joiner
                        server_t0_dead = all(m["hp"] <= 0 for m in state["teams"]["0"]["members"])
                        server_t1_dead = all(m["hp"] <= 0 for m in state["teams"]["1"]["members"])
                        
                        # If I am Host (player 0): I win if t1 dead
                        # If I am Joiner (player 1): I win if t0 dead
                        if self.player_idx == 0:
                            self.victory_result = "Defeat!" if server_t0_dead else "Victory!"
                        else:
                            self.victory_result = "Defeat!" if server_t1_dead else "Victory!"
                        
                        # Start victory delay instead of ending immediately
                        self.victory_pending = True
                        self.victory_timer = 120  # 2 seconds at 60 FPS
                        
                        # Sync one last time to ensure defeat sprites are shown
                        self.sync_with_server()
        else:
            # Stop polling if not waiting for opponent
            if self.polling_active:
                self.stop_background_polling()
                
        # Check for async move submission result
        if self.multiplayer and self.state == "SENDING_MOVE":
            with self.move_lock:
                if self.pending_move_result:
                    result = self.pending_move_result
                    self.pending_move_result = None
                    
                    if result and result.get("success"):
                        self.cached_state = None
                        attacker = self.t1.get_active_member()
                        target = self.t2.get_active_member()
                        action_name = result.get("action", "Unknown") # Safe get
                        if action_name in ["Heal", "Blessing", "Purify", "Pray"]: target = attacker
                        self.execute_move(attacker, target, action_name)
                    else:
                        # Log full result to screen for debugging
                        debug_str = str(result) if result else "None"
                        self.log(f"Err: {debug_str[:50]}") # Show first 50 chars
                        print(f"❌ DEBUG: Full Server Result: {result}")
                        self.log(f"Connection Error: {result.get('error', 'Unknown') if result else 'No Response'}")
                        self.state = "PLAYER_ACTION"
                        self.next_turn() # Reset buttons



    def draw_character(self, screen, char, x, y, is_flipped=False):
        # Floating removed
        offset = 0
        
        # Breathing Animation - Use character's own breathing state
        breath_scale = char.breathing_scale
        
        # Hit animation timer countdown
        if char.hit_animation_timer > 0:
            char.hit_animation_timer -= 1
            if char.hit_animation_timer == 0:
                if char.current_sprite_override == "warrior_hit":
                    char.current_sprite_override = None  # Revert to normal sprite
                    char.is_taking_hit = False
                    print(f"ℹ️ Reverting {char.name} from warrior_hit animation")
                elif char.current_sprite_override == "archer_hit":
                    char.current_sprite_override = None
                    char.is_taking_hit = False
                    print(f"ℹ️ Reverting {char.name} from archer_hit animation")
                elif char.current_sprite_override == "mage_hit":
                    char.current_sprite_override = None
                    char.is_taking_hit = False
                    print(f"ℹ️ Reverting {char.name} from mage_hit animation")
                elif char.current_sprite_override == "priest_hit":
                    char.current_sprite_override = None
                    char.is_taking_hit = False
                    print(f"ℹ️ Reverting {char.name} from priest_hit animation")
                elif char.current_sprite_override == "somesh_hit":
                    char.current_sprite_override = None
                    char.is_taking_hit = False
                    print(f"ℹ️ Reverting {char.name} from somesh_hit animation")
                elif char.current_sprite_override == "somesh_chain":
                    char.current_sprite_override = None
                    print(f"ℹ️ Reverting {char.name} from somesh_chain animation")
        
        # Lunge Logic
        lerp_speed = 0.15  # Default slower speed
        
        if char.current_sprite_override == "warrior_bash_charge": 
            lerp_speed = 0.0  # Not used for manual movement
        elif char.current_sprite_override in ["warrior_slash", "warrior_power_slash", "warrior_spinslash", "warrior_spinslash0"]:
            lerp_speed = 0.2  # Medium speed for attack animations
        elif char.current_sprite_override in ["warrior_hit", "archer_hit", "mage_hit", "priest_hit", "somesh_hit", "somesh_chain"]:
            lerp_speed = 0.0  # Stay still when hit or doing special animation
        elif char.current_sprite_override:
            lerp_speed = 0.25  # Other animations
        else:
            lerp_speed = 0.25 # Snappier return
        
        if char.target_x != 0:
            # Special Constant Speed for Shield Bash
            if char.bash_animation_frame >= 0:
                direction = 1 if char.target_x > char.x else -1
                speed = 25
                char.x += speed * direction
                # Check if passed or close enough
                if (direction == 1 and char.x >= char.target_x) or (direction == -1 and char.x <= char.target_x):
                     char.x = char.target_x # Snap
            # Slower constant speed for Run Man animation
            elif char.run_animation_frame >= 0:
                direction = 1 if char.target_x > char.x else -1
                speed = 12  # Slower than Shield Bash for visible animation
                char.x += speed * direction
                # Check if passed or close enough
                if (direction == 1 and char.x >= char.target_x) or (direction == -1 and char.x <= char.target_x):
                     char.x = char.target_x # Snap
            else:
                char.x += (char.target_x - char.x) * lerp_speed
            
            if abs(char.target_x - char.x) < 10: 
                # Reached target - pause at impact
                char.target_x = 0
                # If we were bashing, switch to post pose and pause
                if char.bash_animation_frame >= 0:
                    char.current_sprite_override = "warrior_bash_post"
                    char.hit_pause_timer = 60  # Extended pause for impact (1 second)
                    char.bash_animation_frame = -1  # Stop bash animation
                    
                    # Apply Shield Bash damage NOW (at impact)
                    if char.pending_bash_target:
                        char.pending_bash_target.hp -= int(20 / char.pending_bash_target.def_mod)
                        char.pending_bash_target.shake_timer = 20
                        
                        # Intense screen shake on impact
                        self.shake_timer = 30
                        self.screen_shake.add_shake(12, 30)  # Very intense shake
                        
                        # Impact ripple effect
                        self.particles.append(RippleEffect(char.pending_bash_target.x + 130, char.pending_bash_target.y + 150, 'silver'))
                        
                        # Impact particles
                        for _ in range(20):
                            angle = random.uniform(0, 6.28)
                            speed = random.uniform(5, 12)
                            vx = math.cos(angle) * speed
                            vy = math.sin(angle) * speed
                            self.spawn_particle(
                                char.pending_bash_target.x + 130,
                                char.pending_bash_target.y + 150,
                                (200, 200, 255),
                                (vx, vy),
                                40,
                                size=10,
                                shape='spark'
                            )
                        
                        # Show hit sprite on target if it's a warrior
                        if isinstance(char.pending_bash_target, Warrior):
                            char.pending_bash_target.current_sprite_override = "warrior_hit"
                            char.pending_bash_target.hit_animation_timer = 30
                            char.pending_bash_target.is_taking_hit = True
                        elif isinstance(char.pending_bash_target, Priest):
                            char.pending_bash_target.current_sprite_override = "priest_hit"
                            char.pending_bash_target.hit_animation_timer = 30
                            char.pending_bash_target.is_taking_hit = True
                        elif isinstance(char.pending_bash_target, Somesh):
                            char.pending_bash_target.current_sprite_override = "somesh_hit"
                            char.pending_bash_target.hit_animation_timer = 30
                            char.pending_bash_target.is_taking_hit = True
                        
                        # Check for death
                        target_team = self.t1 if char.pending_bash_target in self.t1.members else self.t2
                        self.check_and_switch_dead_character(char.pending_bash_target, target_team)
                        
                        char.pending_bash_target = None  # Clear the pending target
                
                # If we were doing Spin Slash, apply damage and effects ONLY during charge phase
                elif hasattr(char, 'spin_slash_active') and char.spin_slash_active and isinstance(char, Warrior):
                    # CRITICAL: Only apply damage if we're in the CHARGE phase (frame 1), not windup (frame 0)
                    if hasattr(char, 'spin_slash_frame') and char.spin_slash_frame == 1:
                        char.hit_pause_timer = 50  # Hold spinslash pose
                        char.spin_slash_active = False  # Reset flag
                        char.spin_slash_frame = -1  # End spin slash animation
                        
                        # SLOW MOTION EFFECT for dramatic impact
                        self.slow_motion.trigger(0.3, 20)  # 30% speed for 20 frames
                        
                        # Apply Spin Slash damage NOW (at impact) - ONLY to the enemy target
                        if char.pending_bash_target and char.pending_bash_target != char:
                            # Ensure we're not damaging the attacker
                            target = char.pending_bash_target
                            target.hp -= int(35 / target.def_mod)
                            target.shake_timer = 40
                            
                            # Intense screen shake
                            self.shake_timer = 30
                            self.screen_shake.add_shake(10, 30)
                            
                            # IMPACT FRAME - Multiple ripples
                            for i in range(3):
                                delay_frames = i * 5
                                self.particles.append(RippleEffect(target.x + 130, target.y + 150, 'silver'))
                            
                            # Metal sparks flying outward from impact (MORE)
                            for _ in range(60):  # Increased from 40
                                angle = random.uniform(0, 6.28)
                                speed = random.uniform(8, 18)
                                vx = math.cos(angle) * speed
                                vy = math.sin(angle) * speed
                                self.spawn_particle(
                                    target.x + 130,
                                    target.y + 150,
                                    (255, 255, 200),  # Golden metallic
                                    (vx, vy),
                                    50,
                                    size=random.randint(4, 8),
                                    shape='spark'
                                )
                            
                            # Energy burst particles (NEW)
                            for _ in range(30):
                                angle = random.uniform(0, 6.28)
                                speed = random.uniform(5, 15)
                                vx = math.cos(angle) * speed
                                vy = math.sin(angle) * speed
                                self.spawn_particle(
                                    target.x + 130,
                                    target.y + 150,
                                    (200, 255, 255),  # Cyan energy
                                    (vx, vy),
                                    60,
                                    size=random.randint(6, 12),
                                    shape='energy'
                                )
                            
                            # Spinning blade particles radiating outward (NEW)
                            for i in range(8):
                                angle = (i / 8) * 6.28
                                for dist in [50, 100, 150]:
                                    vx = math.cos(angle) * 10
                                    vy = math.sin(angle) * 10
                                    self.spawn_particle(
                                        target.x + 130 + math.cos(angle) * dist,
                                        target.y + 150 + math.sin(angle) * dist,
                                        (180, 180, 255),
                                        (vx, vy),
                                        40,
                                        size=8,
                                        shape='spark'
                                    )
                            
                            # Floating damage text
                            self.floating_texts.append(FloatingText(target.x + 50, target.y, "SPIN SLASH!", (255, 200, 0)))
                            self.floating_texts.append(FloatingText(target.x + 50, target.y + 50, "-35", (255, 100, 0)))
                            
                            # Show hit sprite on target
                            if isinstance(target, Warrior):
                                target.current_sprite_override = "warrior_hit"
                                target.hit_animation_timer = 30
                                target.is_taking_hit = True
                            elif isinstance(target, Archer):
                                target.current_sprite_override = "archer_hit"
                                target.hit_animation_timer = 30
                                target.is_taking_hit = True
                            elif isinstance(target, Mage):
                                target.current_sprite_override = "mage_hit"
                                target.hit_animation_timer = 30
                                target.is_taking_hit = True
                            elif isinstance(target, Priest):
                                target.current_sprite_override = "priest_hit"
                                target.hit_animation_timer = 30
                                target.is_taking_hit = True
                            elif isinstance(target, Somesh):
                                target.current_sprite_override = "somesh_hit"
                                target.hit_animation_timer = 30
                                target.is_taking_hit = True
                            
                            # Check for death
                            target_team = self.t1 if target in self.t1.members else self.t2
                            self.check_and_switch_dead_character(target, target_team)
                            
                            char.pending_bash_target = None  # Clear the pending target
                # If we were doing Run Man, switch to punch sprite and apply damage
                elif char.run_animation_frame >= 0 and isinstance(char, Somesh):
                    char.current_sprite_override = "somesh_punch"
                    char.hit_pause_timer = 40  # Hold punch pose
                    char.run_animation_frame = -1  # Stop running animation
                    
                    # Apply Run Man damage NOW (at impact)
                    if char.pending_bash_target:
                        char.pending_bash_target.hp -= int(35 * char.attack_mod / char.pending_bash_target.def_mod)
                        char.pending_bash_target.shake_timer = 15
                        
                        # Show hit sprite on target
                        if isinstance(char.pending_bash_target, Warrior):
                            char.pending_bash_target.current_sprite_override = "warrior_hit"
                            char.pending_bash_target.hit_animation_timer = 30
                            char.pending_bash_target.is_taking_hit = True
                        elif isinstance(char.pending_bash_target, Archer):
                            char.pending_bash_target.current_sprite_override = "archer_hit"
                            char.pending_bash_target.hit_animation_timer = 30
                            char.pending_bash_target.is_taking_hit = True
                        elif isinstance(char.pending_bash_target, Mage):
                            char.pending_bash_target.current_sprite_override = "mage_hit"
                            char.pending_bash_target.hit_animation_timer = 30
                            char.pending_bash_target.is_taking_hit = True
                        elif isinstance(char.pending_bash_target, Priest):
                            char.pending_bash_target.current_sprite_override = "priest_hit"
                            char.pending_bash_target.hit_animation_timer = 30
                            char.pending_bash_target.is_taking_hit = True
                        elif isinstance(char.pending_bash_target, Somesh):
                            char.pending_bash_target.current_sprite_override = "somesh_hit"
                            char.pending_bash_target.hit_animation_timer = 30
                            char.pending_bash_target.is_taking_hit = True
                        
                        # Impact particles (orange/red energy burst)
                        for _ in range(18):
                            angle = random.uniform(0, 6.28)
                            speed = random.uniform(4, 10)
                            vx = math.cos(angle) * speed
                            vy = math.sin(angle) * speed
                            self.spawn_particle(
                                char.pending_bash_target.x + 130, 
                                char.pending_bash_target.y + 150, 
                                (255, random.randint(100, 150), 0),  # Orange/red
                                (vx, vy), 
                                35, 
                                size=8,
                                shape='energy'
                            )
                        
                        # Screen shake
                        self.shake_timer = 20
                        self.screen_shake.add_shake(7, 18)
                        
                        # Ripple effect
                        self.particles.append(RippleEffect(char.pending_bash_target.x + 130, char.pending_bash_target.y + 150, 'purple'))
                        
                        # Floating text
                        self.floating_texts.append(FloatingText(char.pending_bash_target.x + 50, char.pending_bash_target.y, "RUN MAN!", (255, 150, 0)))
                        self.floating_texts.append(FloatingText(char.pending_bash_target.x + 50, char.pending_bash_target.y + 50, "-35", (255, 100, 0)))
                        
                        # Check for death
                        target_team = self.t1 if char.pending_bash_target in self.t1.members else self.t2
                        self.check_and_switch_dead_character(char.pending_bash_target, target_team)
                        
                        char.pending_bash_target = None  # Clear the pending target
        else:
            # Check if we're in hit pause
            if char.hit_pause_timer > 0:
                char.hit_pause_timer -= 1
                # Stay in place during pause
            else:
                # Returning to start
                char.x += (x - char.x) * lerp_speed
                # Increased threshold to 10 to prevent getting stuck
                if abs(char.x - x) < 10:
                    char.x = x
                    # Don't clear sprite override if character is taking a hit, archer firing, or doing spin slash
                    if not char.is_taking_hit and char.current_sprite_override not in ["archer_fire"] and not (hasattr(char, 'spin_slash_active') and char.spin_slash_active):
                        char.current_sprite_override = None
            
        # Shake Logic
        shake_x = 0
        if char.shake_timer > 0:
            char.shake_timer -= 1
            shake_x = random.randint(-5, 5)

        # Special adjustment for Archer sprite alignment
        draw_x_offset = 0
        draw_y_offset = 0
        if isinstance(char, Archer):
            # Only apply standing alignment if archer is alive
            # Otherwise the horizontal defeat sprite needs to be on the ground
            if char.hp > 0:
                draw_y_offset = -27  # Move up to align feet with ground (standing sprites)
                draw_x_offset = 7   # Move right to align with shadow center
            else:
                draw_y_offset = 0  # Reset offset for defeat sprite (horizontal position)
                draw_x_offset = 7   # Keep horizontal centering
        elif isinstance(char, Warrior):
            # Bash animation sprites need grounding
            if char.bash_animation_frame >= 0:
                draw_y_offset = 0  # Bash sprites are grounded, no offset
                draw_x_offset = 0
        elif isinstance(char, Somesh):
            # Running animation sprites need different alignment
            if char.run_animation_frame >= 0:
                draw_y_offset = 0  # Running sprites are already grounded, no offset needed
                draw_x_offset = 0
            else:
                draw_y_offset = -15 # Move up slightly to align feet (larger sprite)
                draw_x_offset = 0
        elif isinstance(char, Mage):
            # Check if mage is dead first (defeat sprite)
            if char.hp <= 0:
                draw_y_offset = 0  # Reset offset for defeat sprite (horizontal position)
                draw_x_offset = 0
            elif char.current_sprite_override == "mage_hit":
                draw_y_offset = 20  # Move down for smaller mage_hit sprite
                draw_x_offset = 0
        elif isinstance(char, Priest) and char.current_sprite_override == "priest_heal":
            draw_y_offset = -60  # Lift taller heal sprite upward

        # Base Y position
        draw_y = y + offset + char.y_offset + draw_y_offset
        
        # Adjust Y for larger defeat sprites to keep feet aligned
        # User requested to "reduce height vertically" (lower them)baldwinn
        if char.hp <= 0:
            if isinstance(char, Warrior): draw_y += 20 
            elif isinstance(char, Archer): draw_y += 30  # Increased to properly ground the horizontal sprite
            elif isinstance(char, Mage): draw_y += 35  # Increased to properly ground the horizontal defeat sprite
            elif isinstance(char, Priest): draw_y += 20
            elif isinstance(char, Somesh): draw_y += 20
            
        char.y = draw_y

        # Bash Animation Frame Cycling (for Warrior Shield Bash)
        if char.bash_animation_frame >= 0:
            # Cycle through bash frames every 18 game frames (very slow, cinematic)
            char.bash_animation_timer += 1
            if char.bash_animation_timer >= 18:
                char.bash_animation_timer = 0
                char.bash_animation_frame = (char.bash_animation_frame + 1) % 4  # Cycle 0→1→2→3→0

        # Running Animation Frame Cycling (for Somesh Run Man)
        if char.run_animation_frame >= 0:
            # Cycle through frames every 5 game frames (smooth running animation)
            char.run_animation_timer += 1
            if char.run_animation_timer >= 5:
                char.run_animation_timer = 0
                char.run_animation_frame = (char.run_animation_frame + 1) % 4  # Cycle 0→1→2→3→0

        sprite_key = char.current_sprite_override if char.current_sprite_override else char.sprite_name
        
        # Override sprite with bash animation frames if active
        if char.bash_animation_frame >= 0 and isinstance(char, Warrior):
            bash_frame_names = ["bash1", "bash2", "bash3", "bash_before_impact"]
            sprite_key = f"warrior_{bash_frame_names[char.bash_animation_frame]}"
        
        # Override sprite with running animation frames if active
        if char.run_animation_frame >= 0 and isinstance(char, Somesh):
            sprite_key = f"somesh_r{char.run_animation_frame + 1}"  # r1, r2, r3, r4
        
        # Spin Slash Animation Frame Management
        if hasattr(char, 'spin_slash_frame') and char.spin_slash_frame >= 0 and isinstance(char, Warrior):
            char.spin_slash_timer += 1
            
            # Frame 0 (windup): Hold spinslash0 for 15 frames
            if char.spin_slash_frame == 0 and char.spin_slash_timer >= 15:
                # Switch to charge frame
                char.spin_slash_frame = 1
                char.current_sprite_override = "warrior_spinslash"
                print(f"⚔️ Spin Slash windup complete - Transitioning to charge sprite for {char.name}")
                # NOW start charging toward target
                if hasattr(char, 'spin_slash_target_x'):
                    char.target_x = char.spin_slash_target_x
                char.spin_slash_timer = 0  # Reset timer for charge phase
        
        # Use defeat sprite if dead
        if char.hp <= 0:
            if isinstance(char, Warrior): sprite_key = "warrior_defeat"
            elif isinstance(char, Archer): sprite_key = "archer_defeat"
            elif isinstance(char, Mage): sprite_key = "mage_defeat"
            elif isinstance(char, Priest): sprite_key = "priest_defeat"
            elif isinstance(char, Somesh): sprite_key = "somesh_defeat"
            
        img = self.manager.assets.get(sprite_key, self.manager.assets["warrior"])
        
        original_w = img.get_width()
        original_h = img.get_height()
        
        # Vibration Effect for Spin Slash
        spin_vibrate_x = 0
        spin_vibrate_y = 0
        if hasattr(char, 'vibrate_timer') and char.vibrate_timer > 0:
            char.vibrate_timer -= 1
            intensity = getattr(char, 'vibrate_intensity', 5)
            spin_vibrate_x = random.randint(-intensity, intensity)
            spin_vibrate_y = random.randint(-intensity, intensity)
        
        # Vibration Effect for Shield Bash Impact
        bash_vibrate_x = 0
        bash_vibrate_y = 0
        if char.current_sprite_override == "warrior_bash_post" and isinstance(char, Warrior):
            # Add vibration during hit pause
            if char.hit_pause_timer > 0:
                bash_vibrate_x = random.randint(-3, 3)
                bash_vibrate_y = random.randint(-3, 3)
        
        # Apply Breathing Scale (Upper Body Only)
        if not char.current_sprite_override and char.hp > 0: # Only breathe when idle and alive
            # Split image at 60% height (waist)
            split_y = int(original_h * 0.6)
            
            # Create surfaces
            top_surf = img.subsurface((0, 0, original_w, split_y)).copy()
            bot_surf = img.subsurface((0, split_y, original_w, original_h - split_y)).copy()
            
            # Scale top
            scaled_top_h = int(split_y * breath_scale)
            scaled_top = pygame.transform.scale(top_surf, (original_w, scaled_top_h))
            
            # Combine
            new_h = scaled_top_h + (original_h - split_y)
            new_img = pygame.Surface((original_w, new_h), pygame.SRCALPHA)
            new_img.blit(scaled_top, (0, 0))
            new_img.blit(bot_surf, (0, scaled_top_h))
            
            img = new_img
            
            # Adjust draw_y to keep feet planted
            # The feet are at draw_y + original_h originally.
            # We want feet at draw_y_new + new_h = draw_y + original_h
            draw_y -= (new_h - original_h)
            char.y = draw_y
        

        
        # Death Tint (Softer Red) - DISABLED for defeat sprites
        if char.hp <= 0 and not any(x in sprite_key for x in ["defeat"]):
            # Use BLEND_RGBA_MULT with a lighter red to preserve some detail/other channels
            # or just a reddish tint. (255, 100, 100) keeps some blue/green.
            img = tint_image(img, (255, 100, 100))
        
        # Somesh sprites are facing opposite direction, so flip logic is reversed
        flip_sprite = is_flipped
        if isinstance(char, Somesh):
            flip_sprite = not is_flipped
            
        if flip_sprite: img = pygame.transform.flip(img, True, False)
        
        # Enhanced Shadow Rendering
        # Dynamic shadow size based on character state
        base_shadow_w = 100
        if char.current_sprite_override:  # Larger shadow during special animations
            shadow_w = int(base_shadow_w * 1.2)
            shadow_alpha = 120
        elif not char.is_alive():  # Keep shadow visible when dead (don't make it disappear)
            shadow_w = int(base_shadow_w * 0.8)
            shadow_alpha = 120
        else:
            shadow_w = base_shadow_w
            shadow_alpha = 100
        
        shadow_x = char.x + (original_w - shadow_w) // 2 + shake_x
        shadow_y = y + offset + char.y_offset + 240
        
        # Draw shadow with soft edges (multiple layers)
        for i in range(3):
            layer_w = shadow_w + i * 10
            layer_h = 20 + i * 5
            layer_alpha = shadow_alpha // (i + 1)
            shadow_surf = pygame.Surface((layer_w, layer_h), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_surf, (0, 0, 0, layer_alpha), (0, 0, layer_w, layer_h))
            screen.blit(shadow_surf, (shadow_x - i * 5, shadow_y - i * 2))
            
        # Draw Motion Blur Trail (Ghost Images)
        if char.trail:
            new_trail = []
            for t_img, t_x, t_y, t_alpha in char.trail:
                if t_alpha > 0:
                    t_img.set_alpha(t_alpha)
                    screen.blit(t_img, (t_x, t_y))
                    new_trail.append((t_img, t_x, t_y, t_alpha - 15)) # Fade out speed (15 per frame)
            char.trail = new_trail
        
        # Draw aura glow if character has active buff/debuff
        if char.aura_color and char.is_alive():
            aura_surf = pygame.Surface((original_w + 60, original_h + 60), pygame.SRCALPHA)
            # Create pulsing glow
            pulse = math.sin(pygame.time.get_ticks() * 0.005) * 0.3 + 0.7
            aura_alpha = int(char.aura_intensity * pulse)
            # Draw multiple glow layers
            for i in range(3):
                glow_size = (original_w + 20 * (3 - i), original_h + 20 * (3 - i))
                glow_pos = (30 - 10 * (3 - i), 30 - 10 * (3 - i))
                pygame.draw.ellipse(
                    aura_surf,
                    (*char.aura_color, aura_alpha // (i + 1)),
                    (*glow_pos, *glow_size)
                )
            screen.blit(aura_surf, (char.x + shake_x + draw_x_offset - 30, draw_y - 30))
        
        # Apply death fade opacity
        if not char.is_alive() and char.is_dying:
            img_copy = img.copy()
            img_copy.set_alpha(char.death_fade_alpha)
            screen.blit(img_copy, (char.x + shake_x + draw_x_offset + bash_vibrate_x, draw_y + bash_vibrate_y))
        else:
            # Brighten in Rainy weather
            if self.weather == "Rainy":
                img = img.copy() # Ensure we don't modify the original asset
                # Create a white silhouette with low alpha to brighten
                bright_mask = tint_image(img, (255, 255, 255))
                bright_mask.set_alpha(40) # Slight brightness boost
                img.blit(bright_mask, (0, 0))
            
            # Apply Dynamic Scaling and Rotation
            if char.current_scale != 1.0 or char.rotation != 0:
                # Scale
                if char.current_scale != 1.0:
                    w = int(img.get_width() * char.current_scale)
                    h = int(img.get_height() * char.current_scale)
                    img = pygame.transform.scale(img, (w, h))
                
                # Rotate
                if char.rotation != 0:
                    img = pygame.transform.rotate(img, char.rotation)
            
            # Calculate centered position after transformations
            draw_x = char.x + shake_x + draw_x_offset + bash_vibrate_x + spin_vibrate_x
            draw_y_pos = draw_y + bash_vibrate_y + spin_vibrate_y
            
            # Adjust for center pivot if rotated/scaled
            if char.current_scale != 1.0 or char.rotation != 0:
                rect = img.get_rect(center=(draw_x + original_w//2, draw_y_pos + original_h//2))
                screen.blit(img, rect)
            else:
                screen.blit(img, (draw_x, draw_y_pos))
            
            # Update Trail for Spin Slash (NEW - ghost trail ONLY during charge)
            if char.current_sprite_override == "warrior_spinslash" and isinstance(char, Warrior):
                # Only add ghost trail when charging (target_x != 0 and actually moving)
                if char.target_x != 0 and abs(char.x - char.target_x) > 10:
                    # Add ghost trail every 2 frames during charge
                    if pygame.time.get_ticks() % 2 == 0:
                        trail_img = img.copy()
                        # Calculate rotation for spinning effect
                        if hasattr(char, 'spin_rotation'):
                            char.spin_rotation = (char.spin_rotation + 15) % 360
                            # Rotate trail image
                            trail_img = pygame.transform.rotate(trail_img, char.spin_rotation)
                        final_x = char.x + shake_x + draw_x_offset + bash_vibrate_x + spin_vibrate_x
                        final_y = draw_y + bash_vibrate_y + spin_vibrate_y
                        char.trail.append((trail_img, final_x, final_y, 100))  # Start alpha 100
            
            # Update Trail (only during bash charge)
            if char.bash_animation_frame >= 0 and isinstance(char, Warrior):
                # Add current frame to trail every 3 frames
                if char.bash_animation_timer % 3 == 0:
                    trail_img = img.copy()
                    # Use final calculated position
                    final_x = char.x + shake_x + draw_x_offset + bash_vibrate_x
                    final_y = draw_y + bash_vibrate_y
                    char.trail.append((trail_img, final_x, final_y, 120)) # Start alpha 120
        
        # Active Turn Indicator (Graphical Improvement #3)
        active_char = self.teams[self.current_team_idx].get_active_member()
        if char == active_char and self.state in ["PLAYER_ACTION", "ANIMATING"] and char.is_alive():
            # Draw a bouncing yellow arrow above
            arrow_y = y - 100 + math.sin(pygame.time.get_ticks() * 0.01) * 10
            arrow_x = char.x + 130 # Center of 260 width
            points = [(arrow_x, arrow_y + 20), (arrow_x - 15, arrow_y), (arrow_x + 15, arrow_y)]
            pygame.draw.polygon(screen, (255, 255, 0), points)
            
        # Bars
        bar_width = 180
        
        # Initialize catch-up HP if not present
        if not hasattr(char, 'catch_up_hp'):
            char.catch_up_hp = char.hp
            
        # Update catch-up HP
        if char.catch_up_hp > char.hp:
            char.catch_up_hp -= (char.catch_up_hp - char.hp) * 0.1
        else:
            char.catch_up_hp = char.hp
            
        hp_ratio = 0 if char.max_hp == 0 else max(0, min(1, char.hp / char.max_hp))
        catch_up_ratio = 0 if char.max_hp == 0 else max(0, min(1, char.catch_up_hp / char.max_hp))
        
        hp_bg = pygame.Rect(char.x + 25 + shake_x, y - 28, bar_width, 16)
        
        # Draw Bar Background
        pygame.draw.rect(screen, (10, 10, 10), hp_bg.inflate(4, 4), border_radius=6)
        pygame.draw.rect(screen, (40, 10, 10), hp_bg, border_radius=5)
        
        # Draw Catch-up Bar (White/Yellow)
        catch_up_fill = hp_bg.copy()
        catch_up_fill.width = int(hp_bg.width * catch_up_ratio)
        pygame.draw.rect(screen, (255, 200, 100), catch_up_fill, border_radius=5)
        
        # Draw HP Bar
        hp_fill = hp_bg.copy()
        hp_fill.width = int(hp_bg.width * hp_ratio)
        hp_color = (int(255 * (1 - hp_ratio)), int(80 + 120 * hp_ratio), 90)
        pygame.draw.rect(screen, hp_color, hp_fill, border_radius=5)
        
        # Draw Gloss/Shine on HP Bar
        if hp_fill.width > 0:
            shine_rect = pygame.Rect(hp_fill.x, hp_fill.y, hp_fill.width, hp_fill.height // 2)
            s = pygame.Surface((shine_rect.width, shine_rect.height), pygame.SRCALPHA)
            s.fill((255, 255, 255, 50))
            screen.blit(s, shine_rect)
        
        hp_text = self.small_font.render(f"HP {max(0, int(char.hp))}/{char.max_hp}", True, (255, 255, 255))
        screen.blit(hp_text, (hp_bg.x, hp_bg.y - 18))

        # Status Icons (Graphical Improvement #1)
        icon_x = hp_bg.right + 10
        for eff in char.effects:
            icon_rect = pygame.Rect(icon_x, hp_bg.y - 5, 20, 20)
            if eff.name == "Burn":
                pygame.draw.circle(screen, (255, 100, 0), icon_rect.center, 8) # Orange circle
            elif eff.name == "Weakness":
                pygame.draw.polygon(screen, (150, 0, 255), [(icon_rect.centerx, icon_rect.bottom), (icon_rect.left, icon_rect.top), (icon_rect.right, icon_rect.top)]) # Purple Down Arrow
            elif eff.name == "Blessing":
                pygame.draw.polygon(screen, (255, 255, 0), [(icon_rect.centerx, icon_rect.top), (icon_rect.left, icon_rect.bottom), (icon_rect.right, icon_rect.bottom)]) # Yellow Up Arrow
            elif eff.name == "Guard":
                pygame.draw.rect(screen, (0, 100, 255), icon_rect) # Blue Square
            icon_x += 25

        res_ratio = 0 if char.max_resource == 0 else max(0, min(1, char.resource / char.max_resource))
        res_bg = pygame.Rect(char.x + 25 + shake_x, y - 8, bar_width, 10)
        pygame.draw.rect(screen, (10, 10, 10), res_bg.inflate(4, 4), border_radius=5)
        pygame.draw.rect(screen, (30, 30, 30), res_bg, border_radius=4)
        res_fill = res_bg.copy()
        res_fill.width = int(res_bg.width * res_ratio)
        res_color = (80, 150, 255) if char.resource_type == "Mana" else (255, 230, 120)
        pygame.draw.rect(screen, res_color, res_fill, border_radius=4)
        res_text = self.small_font.render(f"{char.resource_type[:3]} {int(char.resource)}/{char.max_resource}", True, (220, 220, 220))
        screen.blit(res_text, (res_bg.x, res_bg.y + 12))

        name_surf = self.font.render(char.name, True, (255, 255, 255))
        screen.blit(name_surf, (char.x + 25 + shake_x, y - 85))

    def draw(self, screen):
        # Global Shake Offset
        gx, gy = 0, 0
        if self.shake_timer > 0:
            gx = random.randint(-5, 5)
            gy = random.randint(-5, 5)
            
        # Create a temporary surface for shaking
        game_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        
        bg_img = self.manager.assets["bg"]
        if self.weather == "Rainy" and "cloudy_bg" in self.manager.assets:
            bg_img = self.manager.assets["cloudy_bg"]
            
        game_surf.blit(bg_img, (0, -220))
        
        # Draw Clouds
        for cloud in self.clouds:
            img = self.manager.assets.get(cloud["img"])
            if img:
                game_surf.blit(img, (cloud["x"], cloud["y"]))
        
        t1_active = self.t1.get_active_member()
        if t1_active: 
            self.draw_character(game_surf, t1_active, 200, 230, is_flipped=True)
        t2_active = self.t2.get_active_member()
        if t2_active: 
            self.draw_character(game_surf, t2_active, SCREEN_WIDTH - 400, 230, is_flipped=False)

        for p in self.projectiles:
            if not self.paused:
                p.update(self)
            p.draw(game_surf)
            if not self.paused and not p.active:
                # Apply pending damage when projectile lands
                if p.target_char and p.damage_amount > 0:
                    p.target_char.hp -= p.damage_amount
                    print(f"💥 Projectile landed! {p.target_char.name} took {p.damage_amount} damage (HP: {p.target_char.hp})")
                    
                    # Check if target died from projectile impact
                    target_team = self.t1 if p.target_char in self.t1.members else self.t2
                    self.check_and_switch_dead_character(p.target_char, target_team)
                
                self.spawn_particle(p.end_x, p.end_y, (255, 200, 50), (0,0), 20, size=10)
                self.floating_texts.append(FloatingImage(p.end_x, p.end_y - 20, self.manager.assets["hit_icon"]))
                # Trigger hit animation for warriors
                if p.target_char == t1_active and t1_active:
                    t1_active.shake_timer = 10
                    if isinstance(t1_active, Warrior) and t1_active.current_sprite_override not in ["warrior_bash_charge", "warrior_bash_post"]:
                        print(f"🎯 Projectile hit! Setting warrior_hit for {t1_active.name}")
                        t1_active.current_sprite_override = "warrior_hit"
                        t1_active.hit_animation_timer = 30
                        t1_active.is_taking_hit = True
                    elif isinstance(t1_active, Archer) and t1_active.current_sprite_override != "archer_fire":
                        print(f"🎯 Projectile hit! Setting archer_hit for {t1_active.name}")
                        t1_active.current_sprite_override = "archer_hit"
                        t1_active.hit_animation_timer = 30
                        t1_active.is_taking_hit = True
                    elif isinstance(t1_active, Mage):
                        print(f"🎯 Projectile hit! Setting mage_hit for {t1_active.name}")
                        t1_active.current_sprite_override = "mage_hit"
                        t1_active.hit_animation_timer = 30
                        t1_active.is_taking_hit = True
                    elif isinstance(t1_active, Priest):
                        print(f"🎯 Projectile hit! Setting priest_hit for {t1_active.name}")
                        t1_active.current_sprite_override = "priest_hit"
                        t1_active.hit_animation_timer = 30
                        t1_active.is_taking_hit = True
                    elif isinstance(t1_active, Somesh):
                        print(f"🎯 Projectile hit! Setting somesh_hit for {t1_active.name}")
                        t1_active.current_sprite_override = "somesh_hit"
                        t1_active.hit_animation_timer = 30
                        t1_active.is_taking_hit = True
                elif p.target_char == t2_active and t2_active:
                    t2_active.shake_timer = 10
                    if isinstance(t2_active, Warrior) and t2_active.current_sprite_override not in ["warrior_bash_charge", "warrior_bash_post"]:
                        print(f"🎯 Projectile hit! Setting warrior_hit for {t2_active.name}")
                        t2_active.current_sprite_override = "warrior_hit"
                        t2_active.hit_animation_timer = 30
                        t2_active.is_taking_hit = True
                    elif isinstance(t2_active, Archer) and t2_active.current_sprite_override != "archer_fire":
                        print(f"🎯 Projectile hit! Setting archer_hit for {t2_active.name}")
                        t2_active.current_sprite_override = "archer_hit"
                        t2_active.hit_animation_timer = 30
                        t2_active.is_taking_hit = True
                    elif isinstance(t2_active, Mage):
                        print(f"🎯 Projectile hit! Setting mage_hit for {t2_active.name}")
                        t2_active.current_sprite_override = "mage_hit"
                        t2_active.hit_animation_timer = 30
                        t2_active.is_taking_hit = True
                    elif isinstance(t2_active, Priest):
                        print(f"🎯 Projectile hit! Setting priest_hit for {t2_active.name}")
                        t2_active.current_sprite_override = "priest_hit"
                        t2_active.hit_animation_timer = 30
                        t2_active.is_taking_hit = True
                    elif isinstance(t2_active, Somesh):
                        print(f"🎯 Projectile hit! Setting somesh_hit for {t2_active.name}")
                        t2_active.current_sprite_override = "somesh_hit"
                        t2_active.hit_animation_timer = 30
                        t2_active.is_taking_hit = True
                
                # Revert archer_fire sprite when projectile lands
                if p.source_char and isinstance(p.source_char, Archer):
                    if p.source_char.current_sprite_override == "archer_fire":
                        p.source_char.current_sprite_override = None
                        print(f"🏹 Reverting {p.source_char.name} from archer_fire (projectile landed)")
        if not self.paused:
            self.projectiles = [p for p in self.projectiles if p.active]
            if self.waiting_for_projectiles and not self.projectiles:
                self.waiting_for_projectiles = False
        
        for p in self.particles:
            if not self.paused:
                p.update()
            p.draw(game_surf)
        if not self.paused:
            self.particles = [p for p in self.particles if p.life > 0]

        for ft in self.floating_texts:
            if not self.paused:
                ft.update()
            ft.draw(game_surf)
        if not self.paused:
            self.floating_texts = [ft for ft in self.floating_texts if ft.timer < ft.duration]


        
        # Get enhanced screen shake offset (combines old and new shake systems)
        shake_x, shake_y = self.screen_shake.get_offset()
        gx += shake_x
        gy += shake_y
        
        # Blit game surface with combined shake
        screen.blit(game_surf, (gx, gy))
        
        # Draw vignette overlay (on screen, not game_surf)
        if self.vignette:
            self.vignette.draw(screen)
        
        # Draw screen flash (on screen, on top of everything)
        if self.screen_flash:
            self.screen_flash.draw(screen)
            
        # Draw Rain (Top Layer)
        if self.rain_effect:
            self.rain_effect.draw(screen)

        # UI (No shake)
        log_width = 420
        log_height = 130
        log_x = (SCREEN_WIDTH - log_width) // 2
        log_y = 10
        log_bg = pygame.Surface((log_width, log_height), pygame.SRCALPHA)
        log_bg.fill((0, 0, 0, 150))
        screen.blit(log_bg, (log_x, log_y))
        text_y = log_y + 10
        for msg in self.log_messages:
            txt = self.tiny_font.render(msg, True, hex_to_rgb(THEME["text_secondary"]))
            screen.blit(txt, (log_x + 12, text_y))
            text_y += 16

        panel_height = 160
        action_panel = pygame.Surface((SCREEN_WIDTH, panel_height), pygame.SRCALPHA)
        panel_color = (5, 5, 15, 200) if self.state == "PLAYER_ACTION" else (20, 10, 10, 180)
        action_panel.fill(panel_color)
        screen.blit(action_panel, (0, SCREEN_HEIGHT - panel_height))
        prompt_color = (255, 255, 255) if self.state == "PLAYER_ACTION" else (200, 200, 200)
        prompt_text = self.font.render(self.action_prompt, True, prompt_color)
        screen.blit(prompt_text, (40, SCREEN_HEIGHT - panel_height + 20))

        for btn in self.buttons: btn.draw(screen)
        
        # Death Message (Centered below battle log)
        if self.death_message_timer > 0 and self.death_message_text:
            # Create overlay panel (smaller size)
            death_panel = pygame.Surface((450, 80), pygame.SRCALPHA)
            death_panel.fill((20, 0, 0, 220))  # Dark red tint
            pygame.draw.rect(death_panel, (255, 100, 100), (0, 0, 450, 80), 3)  # Red border
            
            # Position centered horizontally, below battle log
            panel_x = SCREEN_WIDTH // 2 - 225
            panel_y = 200  # Below battle log
            screen.blit(death_panel, (panel_x, panel_y))
            
            # Render death message text
            death_font = pygame.font.Font(None, 44)
            death_text = death_font.render(self.death_message_text, True, (255, 255, 255))
            death_text_shadow = death_font.render(self.death_message_text, True, (100, 0, 0))
            text_x = SCREEN_WIDTH // 2
            text_y = panel_y + 40
            screen.blit(death_text_shadow, death_text_shadow.get_rect(center=(text_x + 2, text_y + 2)))
            screen.blit(death_text, death_text.get_rect(center=(text_x, text_y)))

        # Teammate HP Bars
        # Player Teammate (Top Left)
        for m in self.t1.members:
            if m != self.t1.get_active_member() and m.is_alive():
                # Draw small bar
                pygame.draw.rect(screen, (50, 0, 0), (20, 200, 100, 10))
                pct = m.hp / m.max_hp
                pygame.draw.rect(screen, (0, 255, 0), (20, 200, 100 * pct, 10))
                name_s = self.small_font.render(m.name, True, (200, 200, 200))
                screen.blit(name_s, (20, 180))

        # Enemy Teammate (Top Right)
        for m in self.t2.members:
            if m != self.t2.get_active_member() and m.is_alive():
                pygame.draw.rect(screen, (50, 0, 0), (SCREEN_WIDTH - 120, 200, 100, 10))
                pct = m.hp / m.max_hp
                pygame.draw.rect(screen, (255, 100, 0), (SCREEN_WIDTH - 120, 200, 100 * pct, 10))
                name_s = self.small_font.render(m.name, True, (200, 200, 200))
                screen.blit(name_s, (SCREEN_WIDTH - 120, 180))

        # Draw offline indicator
        if self.multiplayer and self.cached_state:
            opponent_idx = 1 - self.player_idx
            is_online = self.cached_state.get(f"t{opponent_idx+1}_online", True)
            if not is_online:
                offline_txt = self.font.render("OPPONENT OFFLINE", True, (255, 50, 50))
                # Draw with background for visibility
                bg_rect = offline_txt.get_rect(center=(SCREEN_WIDTH//2, 100))
                bg_rect.inflate_ip(20, 10)
                pygame.draw.rect(screen, (0, 0, 0, 180), bg_rect, border_radius=5)
                screen.blit(offline_txt, offline_txt.get_rect(center=(SCREEN_WIDTH//2, 100)))

        if self.paused:
            pause_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pause_overlay.fill((0, 0, 0, 140))
            screen.blit(pause_overlay, (0, 0))
            paused_text = self.font.render("PAUSED", True, (255, 255, 255))
            screen.blit(paused_text, paused_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 20)))
            self.exit_match_btn.draw(screen)

class GameOverScene(Scene):
    def __init__(self, manager, result):
        super().__init__(manager)
        self.result = result
        self.font = pygame.font.Font(None, 72)
        self.btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2 + 50, 200, 60, "MAIN MENU", self.go_menu)
        # Play victory or defeat sound
        if "Victory" in result and "victory" in self.manager.sounds:
            try:
                self.manager.sounds["victory"].play()
            except Exception as e:
                print(f"Failed to play victory sound: {e}")
        elif "Defeat" in result and "defeat" in self.manager.sounds:
            try:
                self.manager.sounds["defeat"].play()
            except Exception as e:
                print(f"Failed to play defeat sound: {e}")

    def go_menu(self):
        self.manager.change_scene("START")

    def handle_input(self, events):
        mouse_pos = pygame.mouse.get_pos()
        mouse_click = False
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_click = True
        if self.btn.update(mouse_pos, mouse_click): self.btn.callback()

    def draw(self, screen):
        screen.blit(self.manager.assets["bg"], (0,0))
        title = self.font.render(self.result, True, (255, 255, 0))
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 50)))
        self.btn.draw(screen)

class SceneManager:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Freaky fighters")
        self.clock = pygame.time.Clock()
        self.assets = {}
        self.sounds = {}
        self.music_volume = 0.5
        self.sfx_volume = 0.5
        self.font = pygame.font.Font(None, 32) # Shared font
        self.load_assets()
        self.mode = "LOCAL" # LOCAL, CREATE, JOIN
        self.game_id = None
        self.selected_weather = "Clear"  # Track weather selection across scenes
        self.current_scene = StartScene(self)
        
        # Apply initial volume
        self.set_music_volume(self.music_volume)
        self.set_sfx_volume(self.sfx_volume)

    def set_music_volume(self, vol):
        self.music_volume = vol
        try:
            pygame.mixer.music.set_volume(vol)
        except: pass

    def set_sfx_volume(self, vol):
        self.sfx_volume = vol
        for sound in self.sounds.values():
            if isinstance(sound, pygame.mixer.Sound):
                sound.set_volume(vol)

    def load_assets(self):
        asset_dir = "assets"
        try:
            self.assets["bg"] = pygame.image.load(os.path.join(asset_dir, "Backgrounds", "ground.png")).convert()
            self.assets["bg"] = pygame.transform.scale(self.assets["bg"], (SCREEN_WIDTH, SCREEN_HEIGHT + 220))
        except:
            self.assets["bg"].fill(hex_to_rgb(THEME["background"]))
            
        # Load Cloudy Background
        try:
            self.assets["cloudy_bg"] = pygame.image.load(os.path.join(asset_dir, "Backgrounds", "cloudy_background.png")).convert()
            self.assets["cloudy_bg"] = pygame.transform.scale(self.assets["cloudy_bg"], (SCREEN_WIDTH, SCREEN_HEIGHT + 220))
            print(f"✓ Loaded cloudy_background.png")
        except Exception as e:
            print(f"Failed to load cloudy_background: {e}")
            self.assets["cloudy_bg"] = self.assets["bg"] # Fallback
            
        # Load Clouds (Scaled Down)
        for i in range(1, 4):
            try:
                img = pygame.image.load(os.path.join(asset_dir, "Backgrounds", f"cloud{i}.png")).convert_alpha()
                # Scale to 60%
                w = int(img.get_width() * 0.6)
                h = int(img.get_height() * 0.6)
                self.assets[f"cloud{i}"] = pygame.transform.scale(img, (w, h))
                print(f"✓ Loaded cloud{i}.png (Scaled)")
            except Exception as e:
                print(f"Failed to load cloud{i}: {e}")
        
        # Load Rain Clouds
        for i in range(1, 4):
            try:
                img = pygame.image.load(os.path.join(asset_dir, "Backgrounds", f"raincloud{i}.png")).convert_alpha()
                # Scale to 60%
                w = int(img.get_width() * 0.6)
                h = int(img.get_height() * 0.6)
                self.assets[f"raincloud{i}"] = pygame.transform.scale(img, (w, h))
                print(f"✓ Loaded raincloud{i}.png")
            except Exception as e:
                print(f"Failed to load raincloud{i}: {e}")
            
        # Load character sprites from their folders
        # Warrior sprites
        warrior_sprites = ["warrior", "warrior_bash_charge", "warrior_bash post", "warrior_power_slash", "warror_slash", "warrior_HIT", "spinslash", "spinslash0"]
        for name in warrior_sprites:
            try:
                img = pygame.image.load(os.path.join(asset_dir, "Warrior", f"{name}.png")).convert_alpha()
                # Map filenames to asset keys
                asset_key = name
                if name == "warrior_bash post": asset_key = "warrior_bash_post"
                if name == "warror_slash": asset_key = "warrior_slash"  # Fix typo in filename
                if name == "warrior_HIT": asset_key = "warrior_hit"
                if name == "spinslash": 
                    asset_key = "warrior_spinslash"
                    # Make spinslash sprite 10px larger
                    self.assets[asset_key] = pygame.transform.scale(img, (270, 270))
                    print(f"✓ Loaded {name} as '{asset_key}' (270x270)")
                    continue
                if name == "spinslash0": 
                    asset_key = "warrior_spinslash0"
                    # Make spinslash0 sprite 10px larger to match
                    self.assets[asset_key] = pygame.transform.scale(img, (270, 270))
                    print(f"✓ Loaded {name} as '{asset_key}' (270x270)")
                    continue
                self.assets[asset_key] = pygame.transform.scale(img, (260, 260))
                print(f"✓ Loaded {name} as '{asset_key}'")
            except Exception as e:
                print(f"Failed to load {name}: {e}")
                self.assets.setdefault("warrior", pygame.Surface((260, 260)))
        
        # Load Warrior Defeat
        try:
            img = pygame.image.load(os.path.join(asset_dir, "Warrior", "warrior_defeat.png")).convert_alpha()
            self.assets["warrior_defeat"] = pygame.transform.scale(img, (280, 280)) # Slightly larger
            print(f"✓ Loaded warrior_defeat.png")
        except Exception as e:
            print(f"Failed to load warrior_defeat: {e}")
        
        # Load Warrior Shield Bash animation frames
        bash_frames = ["bash1", "bash2", "bash3", "bash before impact"]
        for frame_name in bash_frames:
            try:
                img = pygame.image.load(os.path.join(asset_dir, "Warrior", "bash", f"{frame_name}.png")).convert_alpha()
                asset_key = frame_name.replace(" ", "_")  # Convert to snake_case
                self.assets[f"warrior_{asset_key}"] = pygame.transform.scale(img, (290, 290))  # Larger for visibility
                print(f"✓ Loaded {frame_name}.png as 'warrior_{asset_key}'")
            except Exception as e:
                print(f"Failed to load warrior bash frame {frame_name}: {e}")
        
        # Other character sprites (archer, mage, priest)
        for char_name in ["archer", "mage", "priest"]:
            try:
                # Try capitalized folder name first
                folder = char_name.capitalize()
                img = pygame.image.load(os.path.join(asset_dir, folder, f"{char_name}.png")).convert_alpha()
                # Make archer bigger
                if char_name == "archer":
                    self.assets[char_name] = pygame.transform.scale(img, (312, 312))  # 20% larger
                else:
                    self.assets[char_name] = pygame.transform.scale(img, (260, 260))
                print(f"✓ Loaded {char_name}.png")
            except:
                # Fallback to plain colored square
                s = pygame.Surface((260, 260))
                s.fill((255, 0, 0))
                self.assets[char_name] = s
        
        # Load archer_fire sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "Archer", "archer_fire.png")).convert_alpha()
            self.assets["archer_fire"] = pygame.transform.scale(img, (312, 312))  # Match archer size
            print(f"✓ Loaded archer_fire.png")
        except Exception as e:
            print(f"Failed to load archer_fire: {e}")
        
        # Load archer_hit sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "Archer", "archer_HIT.png")).convert_alpha()
            self.assets["archer_hit"] = pygame.transform.scale(img, (312, 312))  # Match archer size
            print(f"✓ Loaded archer_HIT.png as 'archer_hit'")
        except Exception as e:
            print(f"Failed to load archer_HIT: {e}")
            
        # Load archer_defeat sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "Archer", "archer_defeat.png")).convert_alpha()
            self.assets["archer_defeat"] = pygame.transform.scale(img, (315, 315))  # Slightly larger
            print(f"✓ Loaded archer_defeat.png")
        except Exception as e:
            print(f"Failed to load archer_defeat: {e}")
        
        # Load mage_attack sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "mage", "mage_attack.png")).convert_alpha()
            self.assets["mage_attack"] = pygame.transform.scale(img, (260, 260))
            print(f"✓ Loaded mage_attack.png")
        except Exception as e:
            print(f"Failed to load mage_attack: {e}")
        
        # Load priest_attack sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "priest", "priest_attack.png")).convert_alpha()
            img = pygame.transform.flip(img, True, False)  # Face toward enemy
            self.assets["priest_attack"] = pygame.transform.scale(img, (260, 260))
            print(f"✓ Loaded priest_attack.png")
        except Exception as e:
            print(f"Failed to load priest_attack: {e}")
        
        # Load priest_heal sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "priest", "priest_heal.png")).convert_alpha()
            self.assets["priest_heal"] = pygame.transform.scale(img, (300, 320))
            print(f"✓ Loaded priest_heal.png")
        except Exception as e:
            print(f"Failed to load priest_heal: {e}")
            
        # Load priest_hit sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "priest", "priest_hit.png")).convert_alpha()
            img = pygame.transform.flip(img, True, False) # Face toward enemy
            self.assets["priest_hit"] = pygame.transform.scale(img, (260, 260))
            print(f"✓ Loaded priest_hit.png")
        except Exception as e:
            print(f"Failed to load priest_hit: {e}")
            
        # Load priest_defeat sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "priest", "priest_defeat.png")).convert_alpha()
            # img = pygame.transform.flip(img, True, False) # Removed flip as requested
            self.assets["priest_defeat"] = pygame.transform.scale(img, (270, 270)) # Slightly larger
            print(f"✓ Loaded priest_defeat.png")
        except Exception as e:
            print(f"Failed to load priest_defeat: {e}")
        
        # Load mage_fireball sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "mage", "mage_fireball.png")).convert_alpha()
            self.assets["mage_fireball"] = pygame.transform.scale(img, (260, 260))
            print(f"✓ Loaded mage_fireball.png")
        except Exception as e:
            print(f"Failed to load mage_fireball: {e}")
        
        # Load mage_hit sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "mage", "mage_hit.png")).convert_alpha()
            self.assets["mage_hit"] = pygame.transform.scale(img, (237, 237))
            print(f"✓ Loaded mage_hit.png as 'mage_hit'")
        except Exception as e:
            print(f"Failed to load mage_hit: {e}")
            
        # Load mage_defeat sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "mage", "mage_defeat.png")).convert_alpha()
            self.assets["mage_defeat"] = pygame.transform.scale(img, (320, 320)) # Slightly larger
            print(f"✓ Loaded mage_defeat.png")
        except Exception as e:
            print(f"Failed to load mage_defeat: {e}")
        
        # Load Somesh sprites
        try:
            img = pygame.image.load(os.path.join(asset_dir, "shesh", "sohn_.png")).convert_alpha()
            self.assets["somesh"] = pygame.transform.scale(img, (290, 290))
            print(f"✓ Loaded sohn_.png as 'somesh'")
        except Exception as e:
            print(f"Failed to load somesh: {e}")
            s = pygame.Surface((290, 290))
            s.fill((255, 0, 0))
            self.assets["somesh"] = s
        
        # Load Dixon Myers animation sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "shesh", "Dixon myers.png")).convert_alpha()
            self.assets["somesh_dixon"] = pygame.transform.scale(img, (290, 290))
            print(f"✓ Loaded Dixon myers.png as 'somesh_dixon'")
        except Exception as e:
            print(f"Failed to load Dixon myers: {e}")
        
        # Load Somu fireball animation sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "shesh", "Somufireball.png")).convert_alpha()
            self.assets["somesh_fireball"] = pygame.transform.scale(img, (290, 290))
            print(f"✓ Loaded Somufireball.png as 'somesh_fireball'")
        except Exception as e:
            print(f"Failed to load Somufireball: {e}")
        
        # Load Fah!! animation sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "shesh", "FAHH!!!.png")).convert_alpha()
            self.assets["somesh_fah"] = pygame.transform.scale(img, (290, 290))
            print(f"✓ Loaded fahh!!.png as 'somesh_fah'")
        except Exception as e:
            print(f"Failed to load fahh!!: {e}")
            
        # Load Somesh hit sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "shesh", "somu_hit.png")).convert_alpha()
            self.assets["somesh_hit"] = pygame.transform.scale(img, (290, 290))
            print(f"✓ Loaded somu_hit.png as 'somesh_hit'")
        except Exception as e:
            print(f"Failed to load somu_hit: {e}")
            
        # Load Somesh defeat sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "shesh", "somudefeat.png")).convert_alpha()
            img = pygame.transform.flip(img, True, False) # Flip horizontally as requested
            self.assets["somesh_defeat"] = pygame.transform.scale(img, (300, 300)) # Slightly larger
            print(f"✓ Loaded somudefeat.png as 'somesh_defeat'")
        except Exception as e:
            print(f"Failed to load somudefeat: {e}")

        # Load Somesh chain sprite (Diddler projectile)
        try:
            img = pygame.image.load(os.path.join(asset_dir, "shesh", "somuchain.png")).convert_alpha()
            self.assets["somesh_chain"] = pygame.transform.scale(img, (290, 290))
            print(f"✓ Loaded somuchain.png as 'somesh_chain'")
        except Exception as e:
            print(f"Failed to load somuchain: {e}")
        
        # Load Somesh Run Man animation sprites
        run_frames = ["r1", "r2", "r3", "r4"]
        for frame in run_frames:
            try:
                img = pygame.image.load(os.path.join(asset_dir, "shesh", "Run Man", f"{frame}.png")).convert_alpha()
                self.assets[f"somesh_{frame}"] = pygame.transform.scale(img, (290, 290))
                print(f"✓ Loaded {frame}.png as 'somesh_{frame}'")
            except Exception as e:
                print(f"Failed to load somesh_{frame}: {e}")
        
        # Load Somesh punch sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "shesh", "Run Man", "punch.png")).convert_alpha()
            self.assets["somesh_punch"] = pygame.transform.scale(img, (290, 290))
            print(f"✓ Loaded punch.png as 'somesh_punch'")
        except Exception as e:
            print(f"Failed to load somesh_punch: {e}")
        
        # Load attack/projectile sprites
        for name in ["fireball", "arrow", "slash", "blast"]:
            try:
                img = pygame.image.load(os.path.join(asset_dir, "attacks", f"{name}.png")).convert_alpha()
                # Make arrows smaller to match bow size
                if name == "arrow":
                    self.assets[name] = pygame.transform.scale(img, (100, 100))  # Smaller arrows
                else:
                    self.assets[name] = pygame.transform.scale(img, (150, 150))
            except:
                s = pygame.Surface((150, 150))
                s.fill((255, 0, 0))
                self.assets[name] = s
        
        # Programmatic Tints
        self.assets["arrow_blue"] = tint_image(self.assets["arrow"], (0, 100, 255))
        self.assets["arrow_blue"] = pygame.transform.scale(self.assets["arrow_blue"], (120, 120))  # Slightly larger for special arrows
        self.assets["arrow_purple"] = tint_image(self.assets["arrow"], (200, 0, 255))
        self.assets["arrow_purple"] = pygame.transform.scale(self.assets["arrow_purple"], (100, 100))  # Match regular arrow size
        self.assets["slash_red"] = tint_image(self.assets["slash"], (255, 0, 0))
        
        # Load UI icons
        try:
            img = pygame.image.load(os.path.join(asset_dir, "UI", "hit.png")).convert_alpha()
            self.assets["hit_icon"] = pygame.transform.scale(img, (120, 60))  # Much wider
            print(f"✓ Loaded hit.png as 'hit_icon'")
        except Exception as e:
            print(f"Failed to load hit.png: {e}")
            # Fallback to red ellipse
            s = pygame.Surface((120, 60), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (255, 50, 50), (10, 10, 100, 40))
            self.assets["hit_icon"] = s

        # Load heal icon
        try:
            img = pygame.image.load(os.path.join(asset_dir, "UI", "heal.png")).convert_alpha()
            self.assets["heal_icon"] = pygame.transform.scale(img, (120, 60))  # Match hit icon size
            print(f"✓ Loaded heal.png as 'heal_icon'")
        except Exception as e:
            print(f"Failed to load heal.png: {e}")
            # Fallback to green ellipse
            s = pygame.Surface((120, 60), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (50, 255, 50), (10, 10, 100, 40))
            self.assets["heal_icon"] = s



        # Load Somesh Chain
        try:
            img = pygame.image.load(os.path.join(asset_dir, "shesh", "somuchain.png")).convert_alpha()
            self.assets["somesh_chain"] = pygame.transform.scale(img, (290, 290)) # Match Somesh size
            print(f"✓ Loaded somuchain.png as 'somesh_chain'")
        except Exception as e:
            print(f"Failed to load somuchain.png: {e}")
            s = pygame.Surface((290, 290))
            s.fill((255, 0, 255))
            self.assets["somesh_chain"] = s

        # Load fah icon
        try:
            img = pygame.image.load(os.path.join(asset_dir, "UI", "fah.png")).convert_alpha()
            self.assets["fah_icon"] = pygame.transform.scale(img, (320, 160))  # Even bigger icon
            print(f"✓ Loaded fah.png as 'fah_icon'")
        except Exception as e:
            print(f"Failed to load fah.png: {e}")
            s = pygame.Surface((320, 160), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (255, 255, 0), (40, 40, 240, 80))
            self.assets["fah_icon"] = s
        
        # Load sound effects
        try:
            self.sounds["fah"] = pygame.mixer.Sound(os.path.join(asset_dir, "shesh", "fah!!.mp3"))
            print(f"✓ Loaded fah!!.mp3")
        except Exception as e:
            print(f"Failed to load fah!!.mp3: {e}")
        # Load victory and defeat sounds
        try:
            self.sounds["victory"] = pygame.mixer.Sound(os.path.join(asset_dir, "sfx", "victory.mp3"))
            print(f"✓ Loaded victory.mp3")
        except Exception as e:
            print(f"Failed to load victory.mp3: {e}")
        try:
            self.sounds["defeat"] = pygame.mixer.Sound(os.path.join(asset_dir, "sfx", "defeat.mp3"))
            print(f"✓ Loaded defeat.mp3")
        except Exception as e:
            print(f"Failed to load defeat.mp3: {e}")
            
        # Load menu music
        try:
            # Store path string instead of Sound object for streaming music
            self.sounds["menu_theme"] = os.path.join(asset_dir, "sfx", "menu.mp3")
            print(f"✓ Loaded menu.mp3")
        except Exception as e:
            print(f"Failed to load menu.mp3: {e}")

    def change_scene(self, scene_name):
        if scene_name == "START": self.current_scene = StartScene(self)
        elif scene_name == "SELECT": self.current_scene = SelectScene(self)
        elif scene_name == "MULTIPLAYER": self.current_scene = MultiplayerScene(self)
        elif scene_name == "LOBBY": self.current_scene = LobbyScene(self, self.game_id)
        elif scene_name == "SETTINGS": self.current_scene = SettingsScene(self)

    def start_battle(self, p_team, ai_team, weather="Clear"):
        self.current_scene = BattleScene(self, p_team, ai_team, weather=weather)

    def start_multiplayer_battle(self, state, player_idx):
        # Parse state to create teams
        # We need to map class names back to classes
        def create_team(team_data):
            members = []
            for m_data in team_data["members"]:
                cls_name = m_data["type"]
                if cls_name == "Warrior": char = Warrior()
                elif cls_name == "Archer": char = Archer()
                elif cls_name == "Mage": char = Mage()
                elif cls_name == "Priest": char = Priest()
                elif cls_name == "Somesh": char = Somesh()
                else: char = Warrior() # Fallback
                
                # Restore state
                char.hp = m_data["hp"]
                char.max_hp = m_data["max_hp"]
                char.resource = m_data["resource"]
                char.max_resource = m_data["max_resource"]
                members.append(char)
            return members
        
        # Extract teams from new state structure
        t1_members = create_team(state["teams"]["0"])
        t2_members = create_team(state["teams"]["1"])
        weather = state.get("weather", "Clear")
        
        # Server team 0 is Host, team 1 is Joiner
        # If I am Host (0): t1=team0, t2=team1
        # If I am Joiner (1): t1=team1, t2=team0 (swap so my team is always t1)
        
        if self.mode == "JOIN": # Joiner is player 1
             self.current_scene = BattleScene(self, t2_members, t1_members, multiplayer=True, player_idx=1, game_id=self.game_id, weather=weather)
        else: # Host is player 0
             self.current_scene = BattleScene(self, t1_members, t2_members, multiplayer=True, player_idx=0, game_id=self.game_id, weather=weather)

    def game_over(self, result):
        self.current_scene = GameOverScene(self, result)

    def run(self):
        running = True
        while running:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT: running = False
            
            self.current_scene.handle_input(events)
            self.current_scene.update()
            self.current_scene.draw(self.screen)
            
            pygame.display.flip()
            self.clock.tick(FPS)
        pygame.quit()

if __name__ == "__main__":
    game = SceneManager()
    game.run()
