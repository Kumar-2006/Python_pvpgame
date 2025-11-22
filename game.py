import pygame
import json
import random
import math
import os
import requests
# Removed shared_logic imports to avoid conflicts

# ---------- Configuration & Theme ----------
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

    def create_game(self, team_classes):
        try:
            url = f"{self.base_url.rstrip('/')}/create"
            print(f"POST {url}")
            resp = requests.post(url, json={"team": team_classes})
            print(f"Response: {resp.status_code} {resp.text}")
            return resp.json()
        except Exception as e:
            print(f"Create Game Error: {e}")
            return None

    def join_game(self, game_id, team_classes):
        try:
            resp = requests.post(f"{self.base_url}/join", json={"game_id": game_id, "team": team_classes})
            return resp.json()
        except: return None

    def get_state(self, game_id):
        try:
            resp = requests.get(f"{self.base_url}/state/{game_id}")
            if resp.status_code == 200: return resp.json()
            return None
        except: return None

    def submit_move(self, game_id, player_idx, move_name):
        try:
            resp = requests.post(f"{self.base_url}/move", json={
                "game_id": game_id, 
                "player_idx": player_idx,
                "move": move_name
            })
            return resp.json()
        except: return None
class Warrior(Character):
    def __init__(self):
        super().__init__("Warrior", 120, "Stamina", 60, "warrior")
    def get_actions(self): return ["Slash", "Power Strike", "Shield Bash", "Spin Slash"]
    
    def slash(self, target):
        if self.resource >= 10:
            self.resource -= 10
            target.hp -= int(25 / target.def_mod)
            return True
        return False

    def power_strike(self, target):
        if self.resource >= 20:
            self.resource -= 20
            target.hp -= int(40 / target.def_mod)
            return True
        return False

    def shield_bash(self, target):
        if self.resource >= 15:
            self.resource -= 15
            target.hp -= int(20 / target.def_mod)
            # Could add stun or knockback logic here if supported
            return True
        return False
        
    def spin_slash(self, target):
        if self.resource >= 25:
            self.resource -= 25
            target.hp -= int(35 / target.def_mod)
            return True
        return False

class Archer(Character):
    def __init__(self):
        super().__init__("Archer", 100, "Stamina", 60, "archer")
        self.float_amp = 2
        self.y_offset = 0
    def get_actions(self): return ["Quick Shot", "Double Arrow", "Piercing", "Cripple"]
    
    def quick_shot(self, target):
        if self.resource >= 10:
            self.resource -= 10
            target.hp -= int(20 / target.def_mod)
            return True
        return False

    def double_arrow(self, target):
        if self.resource >= 20:
            self.resource -= 20
            dmg = int((15 * 2 * self.attack_mod) / target.def_mod)
            target.hp -= dmg
            return True
        return False

    def piercing_arrow(self, target):
        if self.resource >= 25:
            self.resource -= 25
            dmg = int(30 * self.attack_mod * 1.5)
            target.hp -= dmg
            return True
        return False

    def crippling_shot(self, target):
        if self.resource >= 15:
            self.resource -= 15
            target.hp -= 15
            target.apply_effect(Effect("Weakness", 2, 0))
            return True
        return False

class Mage(Character):
    def __init__(self):
        super().__init__("Mage", 90, "Mana", 80, "mage")
    def get_actions(self): return ["Magic Bolt", "Fireball", "Chain", "Drain"]
    
    def magic_bolt(self, target):
        if self.resource >= 10:
            self.resource -= 10
            target.hp -= int(25 * self.attack_mod / target.def_mod)
            return True
        return False

    def fireball(self, target):
        if self.resource >= 20:
            self.resource -= 20
            target.hp -= int(40 * self.attack_mod / target.def_mod)
            target.apply_effect(Effect("Burn", 2, 5))
            return True
        return False

    def lightning_chain(self, enemies):
        if self.resource >= 25:
            self.resource -= 25
            for e in enemies:
                e.hp -= int(25 * self.attack_mod / e.def_mod)
            return True
        return False

    def arcane_drain(self, target):
        if self.resource >= 15:
            self.resource -= 15
            target.hp -= int(20 / target.def_mod)
            self.resource = min(self.max_resource, self.resource + 10)
            return True
        return False

class Priest(Character):
    def __init__(self):
        super().__init__("Priest", 100, "Mana", 80, "priest")
    def get_actions(self): return ["Smite", "Judgement", "Holy Nova", "Pray"]
    
    def smite(self, target):
        if self.resource >= 10:
            self.resource -= 10
            target.hp -= int(20 * self.attack_mod / target.def_mod)
            return True
        return False

    def judgement(self, target):
        if self.resource >= 20:
            self.resource -= 20
            target.hp -= int(35 * self.attack_mod / target.def_mod)
            return True
        return False

    def holy_nova(self, enemies):
        if self.resource >= 25:
            self.resource -= 25
            for e in enemies:
                e.hp -= int(20 * self.attack_mod / e.def_mod)
            return True
        return False

    def pray(self, self_target):
        if self.resource >= 15:
            self.resource -= 15
            self_target.hp = min(self_target.max_hp, self_target.hp + 30)
            return True
        return False

class Somesh(Character):
    def __init__(self):
        super().__init__("Somesh", 110, "Stamina", 70, "somesh")
    def get_actions(self): return ["Dixon Myers", "Fah!!!", "Backsplash", "Diddler"]
    
    def dixon_myers(self, target):
        if self.resource >= 12:
            self.resource -= 12
            target.hp -= int(50 * self.attack_mod / target.def_mod)
            return True
        return False

    def fah(self, target):
        if self.resource >= 50:
            self.resource -= 50
            target.hp -= 999  # Instant kill
            return True
        return False

    def backsplash(self, target):
        if self.resource >= 15:
            self.resource -= 15
            target.hp -= int(32 * self.attack_mod / target.def_mod)
            return True
        return False

    def diddler(self, target):
        if self.resource >= 25:
            self.resource -= 25
            target.hp -= int(50 * self.attack_mod / target.def_mod)
            return True
        return False

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
    def __init__(self, x, y, color, velocity, life, size=5, shape="circle"):
        self.x = x
        self.y = y
        self.color = color
        self.vx, self.vy = velocity
        self.life = life
        self.max_life = life
        self.size = size
        self.shape = shape

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        self.size = max(0, self.size - 0.05)

    def draw(self, surface):
        if self.life > 0:
            alpha = int((self.life / self.max_life) * 255)
            s = pygame.Surface((int(self.size)*2, int(self.size)*2), pygame.SRCALPHA)
            
            if self.shape == "circle":
                pygame.draw.circle(s, (*self.color, alpha), (int(self.size), int(self.size)), int(self.size))
            elif self.shape == "plus":
                # Draw a plus sign
                rect_h = pygame.Rect(0, int(self.size) - 2, int(self.size)*2, 4)
                rect_v = pygame.Rect(int(self.size) - 2, 0, 4, int(self.size)*2)
                pygame.draw.rect(s, (*self.color, alpha), rect_h)
                pygame.draw.rect(s, (*self.color, alpha), rect_v)
            elif self.shape == "exclamation":
                # Draw an exclamation mark
                rect_body = pygame.Rect(int(self.size) - 2, 0, 4, int(self.size)*1.5)
                rect_dot = pygame.Rect(int(self.size) - 2, int(self.size)*1.7, 4, 4)
                pygame.draw.rect(s, (*self.color, alpha), rect_body)
                pygame.draw.rect(s, (*self.color, alpha), rect_dot)
                
            surface.blit(s, (self.x - self.size, self.y - self.size))

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
        start_y = self.y - 400
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
        self.max_scale = 1.2
        self.target_scale = 1.0

    def update(self):
        self.y -= 0.8 # Float up
        self.timer += 1
        
        # Pop effect
        if self.timer < 10:
            self.scale = min(self.max_scale, self.scale + 0.2)
        elif self.timer < 20:
            self.scale = max(self.target_scale, self.scale - 0.05)

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
            
            rect = text_surf.get_rect(center=(self.x, self.y))
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
            text_color = hex_to_rgb(THEME["text_primary"])

        pygame.draw.rect(surface, color, self.rect, border_radius=8)
        pygame.draw.rect(surface, border_color, self.rect, 2, border_radius=8)
        
        if self.text:
            text_surf = self.font.render(self.text, True, text_color)
            text_rect = text_surf.get_rect(center=(self.rect.centerx, self.rect.centery - 10 if self.subtext else self.rect.centery))
            surface.blit(text_surf, text_rect)
        
        if self.subtext:
            sub_color = hex_to_rgb(THEME["text_secondary"]) if not self.disabled else (120, 120, 120)
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
    "Dixon Myers": {"cost": 0, "info": "50 Dmg"},
    "Backsplash": {"cost": 0, "info": "32 Dmg"},
    "Diddler": {"cost": 0, "info": "50 AoE"}
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
        self.create_btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2 - 60, 200, 60, "CREATE GAME", self.go_create)
        self.join_btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2 + 20, 200, 60, "JOIN GAME", self.go_join)
        self.back_btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2 + 100, 200, 60, "BACK", self.go_back, color=(100, 50, 50))
        self.input = TextInput(SCREEN_WIDTH//2 - 150, SCREEN_HEIGHT//2 - 140, 300, 50, "Enter Game ID to Join")
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

    def update(self):
        self.timer += 1
        if self.timer % 60 == 0: # Poll every second
            state = self.client.get_state(self.game_id)
            if state and state.get("status") == "ACTIVE":
                # Game started!
                # We need to reconstruct the teams from the state
                # But BattleScene expects objects.
                # For now, we just pass the raw state and let BattleScene handle it?
                # Or we parse it here.
                # Let's pass the state to start_battle
                self.manager.start_multiplayer_battle(state, 0) # 0 is Host

    def draw(self, screen):
        screen.blit(self.manager.assets["bg"], (0,0))
        text = self.font.render(f"GAME ID: {self.game_id}", True, (255, 255, 0))
        screen.blit(text, text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 50)))
        sub = self.small_font.render("Waiting for opponent...", True, (200, 200, 200))
        screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 20)))

class StartScene(Scene):
    def __init__(self, manager):
        super().__init__(manager)
        self.font = pygame.font.Font(None, 72)
        self.small_font = pygame.font.Font(None, 36)
        self.start_btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2 + 50, 200, 60, "LOCAL GAME", self.go_select)
        self.multi_btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2 + 120, 200, 60, "MULTIPLAYER", self.go_multi)
        self.exit_btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2 + 190, 200, 60, "EXIT", self.exit_game, color=(100, 50, 50))

    def go_multi(self):
        self.manager.change_scene("MULTIPLAYER")

    def go_select(self):
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
        if self.exit_btn.update(mouse_pos, mouse_click): self.exit_btn.callback()

    def draw(self, screen):
        screen.blit(self.manager.assets["bg"], (0,0))
        title = self.font.render("GOD-TIER ARENA", True, hex_to_rgb(THEME["accent"]))
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 100)))
        subtitle = self.small_font.render("Assemble two heroes and conquer the arena", True, (240, 240, 240))
        screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 40)))

        info_panel = pygame.Surface((420, 140), pygame.SRCALPHA)
        info_panel.fill((0, 0, 0, 150))
        panel_y = SCREEN_HEIGHT//2 + 210
        screen.blit(info_panel, (SCREEN_WIDTH//2 - 210, panel_y))
        hints = ["Mouse: select heroes & attacks", "ESC: Pause/Resume battle", "Tag button: swap teammates"]
        for i, hint in enumerate(hints):
            hint_text = self.small_font.render(hint, True, (220, 220, 220))
            screen.blit(hint_text, (SCREEN_WIDTH//2 - 190, panel_y + 20 + i*30))
        self.start_btn.draw(screen)
        self.multi_btn.draw(screen)
        self.exit_btn.draw(screen)

class SelectScene(Scene):
    def __init__(self, manager):
        super().__init__(manager)
        self.font = pygame.font.Font(None, 48)
        self.small_font = pygame.font.Font(None, 28)
        self.options = [Warrior(), Archer(), Mage(), Priest(), Somesh()]
        self.selected = []
        self.buttons = []
        
        start_x = SCREEN_WIDTH//2 - 450
        for i, char in enumerate(self.options):
            # Pass empty text to avoid overlap
            btn = Button(start_x + i*180, SCREEN_HEIGHT//2, 160, 200, "", lambda idx=i: self.toggle_select(idx))
            self.buttons.append(btn)
            
        self.confirm_btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT - 100, 200, 60, "CONFIRM", self.confirm_selection)

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
                self.manager.start_battle(p_team, ai_team)
            elif self.manager.mode == "CREATE":
                # Create game on server
                team_names = [c.__class__.__name__ for c in self.selected]
                client = NetworkClient()
                resp = client.create_game(team_names)
                if resp and "game_id" in resp:
                    self.manager.game_id = resp["game_id"]
                    self.manager.change_scene("LOBBY")
            elif self.manager.mode == "JOIN":
                # Join game on server
                team_names = [c.__class__.__name__ for c in self.selected]
                client = NetworkClient()
                resp = client.join_game(self.manager.game_id, team_names)
                if resp and resp.get("success"):
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
                btn.border_color = (0, 255, 0)
            else:
                btn.border_color = hex_to_rgb(THEME["button_border"])
                
            if btn.update(mouse_pos, mouse_click): btn.callback()
            
        self.confirm_btn.disabled = len(self.selected) != 2
        if self.confirm_btn.update(mouse_pos, mouse_click) and len(self.selected) == 2:
            self.confirm_btn.callback()

    def draw(self, screen):
        screen.blit(self.manager.assets["bg"], (0,0))
        title = self.font.render("SELECT 2 HEROES", True, (255, 255, 255))
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, 100)))
        subtitle = self.small_font.render("AI will recruit two of the remaining heroes", True, (220, 220, 220))
        screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH//2, 140)))
        
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
        selection_names = ", ".join([c.name for c in self.selected]) if self.selected else "None"
        summary = self.small_font.render(f"Selected: {selection_names}", True, (220, 220, 220))
        screen.blit(summary, (SCREEN_WIDTH//2 - 150, SCREEN_HEIGHT - 140))

class BattleScene(Scene):
    def __init__(self, manager, t1_members, t2_members, multiplayer=False, player_idx=0, game_id=None):
        super().__init__(manager)
        self.multiplayer = multiplayer
        self.player_idx = player_idx
        self.game_id = game_id
        self.client = NetworkClient()
        self.last_server_turn = -1
        self.poll_timer = 0
        self.t1 = Team(t1_members)
        self.t2 = Team(t2_members)
        
        # Set initial positions for slide-in
        for m in self.t1.members:
            m.x = -200
        for m in self.t2.members:
            m.x = SCREEN_WIDTH + 200
            
        self.teams = [self.t1, self.t2]
        self.current_team_idx = 0
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
        self.next_turn()

    def log(self, msg):
        self.log_messages.append(msg)
        if len(self.log_messages) > 6: self.log_messages.pop(0)

    def spawn_particle(self, x, y, color, velocity, life, size=5, shape="circle"):
        self.particles.append(Particle(x, y, color, velocity, life, size, shape))

    def queue_next_turn(self, lock_frames=30, wait_for_projectiles=False):
        """Delay the next turn until cinematic effects complete."""
        self.pending_next_turn = True
        self.animation_lock_timer = lock_frames
        self.waiting_for_projectiles = wait_for_projectiles
        self.state = "ANIMATING"

    def process_animation_lock(self):
        if not self.pending_next_turn or self.paused:
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
        self.manager.change_scene("START")

    def sync_with_server(self):
        if not self.multiplayer: return
        state = self.client.get_state(self.game_id)
        if not state: return
        
        # Helper to sync a team
        def sync_team(local_team, server_team_data):
            for i, m_data in enumerate(server_team_data["members"]):
                if i < len(local_team.members):
                    local_char = local_team.members[i]
                    local_char.hp = m_data["hp"]
                    local_char.resource = m_data["resource"]
                    # Sync effects if needed, but might be visual glitchy
        
        # Server t1 is Host, t2 is Joiner
        # If I am Host (0): t1=t1, t2=t2
        # If I am Joiner (1): t1=t2, t2=t1 (because I swapped them in init)
        
        if self.player_idx == 0:
            sync_team(self.t1, state["t1"])
            sync_team(self.t2, state["t2"])
        else:
            sync_team(self.t1, state["t2"])
            sync_team(self.t2, state["t1"])

    def next_turn(self):
        if self.multiplayer:
            self.sync_with_server()

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

        self.current_team_idx = 1 - self.current_team_idx
        current_team = self.teams[self.current_team_idx]
        attacker = current_team.get_active_member()
        
        attacker.update_effects()
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
            tag_btn = Button(tag_btn_x, tag_btn_y, 140, btn_h * 2 + spacing_y, "TAG", tag_cb, color=tag_color)
            tag_btn.subtext = "Swap ally"
            if not teammate_alive:
                tag_btn.disabled = True
            self.buttons.append(tag_btn)
        else:
            if self.multiplayer:
                self.state = "WAITING_FOR_OPPONENT"
                self.action_prompt = "Waiting for opponent..."
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
        self.t1.active_index = new_index
        self.t1.get_active_member().x = -200
        self.log(f"Tagged in {self.t1.get_active_member().name}!")
        self.spawn_particle(200, 280, (255, 255, 255), (0,0), 30, size=10)
        self.next_turn()

    def ai_swap(self):
        for i, m in enumerate(self.t2.members):
            if m.is_alive():
                self.t2.active_index = i
                m.x = SCREEN_WIDTH + 200
                self.log(f"Enemy tagged in {m.name}!")
                return
    
    def check_and_switch_dead_character(self, character, team):
        """Check if a character died and immediately switch to next teammate"""
        if character.hp <= 0:
            # Mark as dead by setting hp to 0 or less
            character.hp = min(0, character.hp)
            self.log(f"{character.name} has fallen!")
            
            # Spawn death particles
            for _ in range(10):
                angle = random.uniform(0, 6.28)
                vx = math.cos(angle) * 3
                vy = math.sin(angle) * 3
                self.spawn_particle(character.x + 100, character.y + 100, (150, 150, 150), (vx, vy), 40, size=5)
            
            # Immediately switch to next alive teammate
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
                return True  # Switched successfully
            return False  # No one left to switch to

    def select_action(self, action_name):
        if self.state != "PLAYER_ACTION":
            return
        attacker = self.t1.get_active_member()
        target = self.t2.get_active_member()
        if action_name in ["Heal", "Blessing", "Purify", "Pray"]: target = attacker
        self.buttons = []
        
        if self.multiplayer:
            # Send move to server
            resp = self.client.submit_move(self.game_id, self.player_idx, action_name)
            if resp and resp.get("success"):
                self.execute_move(attacker, target, action_name)
            else:
                self.log("Connection Error!")
        else:
            self.execute_move(attacker, target, action_name)

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
                    target.hp -= int(35 / target.def_mod)  # Immediate damage (melee)
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
                    pending_damage = int(30 * attacker.attack_mod * 1.5)
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
            if move_name == "Dixon Myers":
                pending_damage = int(50 * attacker.attack_mod / target.def_mod)
                success = True
            elif move_name == "Fah!!!":
                pending_damage = 999  # Instant kill damage
                success = True
            elif move_name == "Backsplash":
                pending_damage = int(32 * attacker.attack_mod / target.def_mod)
                success = True
            elif move_name == "Diddler":
                pending_damage = int(50 * attacker.attack_mod / target.def_mod)
                success = True
        
        # Ifresource check failed, log and end turn
        if not success:
            self.log("Not enough resource!")
            self.next_turn()
            return
        
        # Crit / Miss Logic (Logical Improvement #1)
        is_crit = False
        is_miss = False
        if success and pending_damage > 0 and move_name not in ["Heal", "Pray", "Buffs..."]:
             # 10% Crit, 5% Miss
             roll = random.random()
             if roll < 0.05:
                 is_miss = True
                 pending_damage = 0
                 self.floating_texts.append(FloatingText(target.x + 50, target.y - 20, "MISS", (200, 200, 200)))
             elif roll < 0.15: # 10% chance (0.05 to 0.15)
                 is_crit = True
                 pending_damage = int(pending_damage * 1.5)
                 self.floating_texts.append(FloatingText(target.x + 50, target.y - 40, "CRIT!", (255, 215, 0), size=60))

        # Animation Lunge (only if successful)
        target_x_offset = 50
        
        if move_name == "Shield Bash":
             # Charge all the way to the enemy!
             if attacker in self.t1.members:
                 # Player attacking enemy - stop right in front (150px gap)
                 attacker.target_x = target.x - 150
             else:
                 # Enemy attacking player - stop right in front
                 attacker.target_x = target.x + 150
             attacker.current_sprite_override = "warrior_bash_charge"
             # Store target for delayed damage
             attacker.pending_bash_target = target
             extra_lock = max(extra_lock, 90)
        elif move_name == "Slash" and isinstance(attacker, Warrior):
            attacker.current_sprite_override = "warrior_slash"
            attacker.target_x = attacker.x + target_x_offset if attacker in self.t1.members else attacker.x - target_x_offset
        elif move_name == "Power Strike" and isinstance(attacker, Warrior):
            attacker.current_sprite_override = "warrior_power_slash"
            attacker.target_x = attacker.x + target_x_offset if attacker in self.t1.members else attacker.x - target_x_offset
        elif isinstance(attacker, Archer):
            # All archer attacks use the fire animation
            attacker.current_sprite_override = "archer_fire"
            attacker.target_x = attacker.x  # Archer stays in place
        elif isinstance(attacker, Mage):
            # Mage attack animations
            if move_name == "Magic Bolt":
                attacker.current_sprite_override = "mage_attack"
            elif "Fireball" in move_name:
                attacker.current_sprite_override = "mage_fireball"
            attacker.target_x = attacker.x  # Mage stays in place
        elif isinstance(attacker, Somesh):
            # Somesh attack animations
            if move_name == "Dixon Myers":
                attacker.current_sprite_override = "somesh_dixon"
                attacker.target_x = attacker.x  # Somesh stays in place
            elif move_name == "Fah!!!":
                attacker.current_sprite_override = "somesh_fah"
                attacker.target_x = attacker.x  # Stay in place for epic attack
            else:
                attacker.target_x = attacker.x + target_x_offset if attacker in self.t1.members else attacker.x - target_x_offset
        else:
            attacker.target_x = attacker.x + target_x_offset if attacker in self.t1.members else attacker.x - target_x_offset
        
        # Projectile Logic
        start_x = attacker.x + 75
        start_y = attacker.y + 75
        end_x = target.x + 75
        end_y = target.y + 75
        
        # Adjust arrow spawn position to match bow for archers
        if isinstance(attacker, Archer):
            # Spawn arrow farther out to match bow position (140px from archer)
            if attacker in self.t1.members:
                start_x = attacker.x + 140  # Player archer facing right
            else:
                start_x = attacker.x + 30   # Enemy archer facing left
            # Adjust Y position to match bow height at chest level (increase Y to move down)
            start_y = attacker.y + 80  # Moved lower to match bow position
        
        proj_list = []
        projectile_wait = False
        
        if move_name == "Double Arrow":
            proj_list.append((start_y - 20, end_y - 20, self.manager.assets["arrow"], None, False, False))
            proj_list.append((start_y + 20, end_y + 20, self.manager.assets["arrow"], None, False, False))
        elif move_name == "Chain":
            proj_list.append((start_y, end_y, self.manager.assets["blast"], (0, 200, 255), False, False))
            proj_list.append((start_y, end_y - 50, self.manager.assets["blast"], (0, 200, 255), False, False))
            proj_list.append((start_y, end_y + 50, self.manager.assets["blast"], (0, 200, 255), False, False))
        elif move_name == "Piercing":
             proj_list.append((start_y, end_y, self.manager.assets["arrow_blue"], (0, 100, 255), False, False))
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
             if isinstance(target, Warrior) and target.current_sprite_override not in ["warrior_bash_charge", "warrior_bash_post"]:
                 target.current_sprite_override = "warrior_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Archer) and target.current_sprite_override != "archer_fire":
                 target.current_sprite_override = "archer_hit"
                 target.hit_animation_timer = 30
                 target.is_taking_hit = True
             elif isinstance(target, Mage):
                 target.current_sprite_override = "mage_hit"
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
             self.floating_texts.append(FloatingText(target.x + 50, target.y, "HOLY NOVA!", (255, 255, 100)))
             self.floating_texts.append(FloatingText(target.x + 50, target.y + 50, f"-{pending_damage}", (255, 200, 0)))
             skip_hit_fx = True
             if isinstance(attacker, Priest):
                 attacker.hit_pause_timer = 50
             extra_lock = max(extra_lock, 70)
             # Original projectiles for visual continuity
             proj_list.append((start_y, end_y, self.manager.assets["blast"], (255, 255, 200), False, False))
             proj_list.append((start_y - 40, end_y - 40, self.manager.assets["blast"], (255, 255, 200), False, False))
             proj_list.append((start_y + 40, end_y + 40, self.manager.assets["blast"], (255, 255, 200), False, False))
        elif move_name == "Dixon Myers":
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
             self.floating_texts.append(FloatingText(target.x + 50, target.y, "FAH!!!", (255, 50, 0)))
             self.floating_texts.append(FloatingText(target.x + 50, target.y + 50, f"-{pending_damage}", (255, 0, 0)))
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
        elif move_name == "Backsplash":
             proj_list.append((start_y, end_y, self.manager.assets["fireball"], (0, 255, 255), False, False))
        elif move_name == "Diddler":
             proj_list.append((start_y, end_y, self.manager.assets["blast"], (255, 0, 150), False, False))
             proj_list.append((start_y - 30, end_y - 30, self.manager.assets["blast"], (255, 0, 150), False, False))
             proj_list.append((start_y + 30, end_y + 30, self.manager.assets["blast"], (255, 0, 150), False, False))
        elif move_name == "Spin Slash":
             # EPIC SPIN SLASH - Spinning blade vortex with metal sparks
             # Circular blade slashes around attacker
             for angle_offset in range(0, 360, 45):
                 angle_rad = math.radians(angle_offset)
                 radius = 80
                 vx = math.cos(angle_rad) * 12
                 vy = math.sin(angle_rad) * 12
                 self.spawn_particle(attacker.x + 130, attacker.y + 150, (192, 192, 192), (vx, vy), 35, size=15)
             # Metal sparks flying outward
             for _ in range(40):
                 angle = random.uniform(0, 6.28)
                 speed = random.uniform(8, 18)
                 vx = math.cos(angle) * speed
                 vy = math.sin(angle) * speed
                 self.spawn_particle(target.x + 130, target.y + 150, (255, 255, 200), (vx, vy), 50, size=random.randint(4, 8))
             # Impact shockwave
             self.particles.append(RippleEffect(target.x + 130, target.y + 150, 'silver'))
             self.shake_timer = 30
             target.hp -= pending_damage
             target.shake_timer = 40
             self.floating_texts.append(FloatingText(target.x + 50, target.y, "SPIN SLASH!", (255, 200, 0)))
             self.floating_texts.append(FloatingText(target.x + 50, target.y + 50, f"-{pending_damage}", (255, 100, 0)))
             skip_hit_fx = True
             if isinstance(attacker, Warrior):
                 attacker.hit_pause_timer = 50
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
             target.hp -= pending_damage
             target.shake_timer = 35
             self.floating_texts.append(FloatingText(target.x + 50, target.y, "PIERCING!", (0, 255, 255)))
             self.floating_texts.append(FloatingText(target.x + 50, target.y + 50, f"-{pending_damage}", (255, 0, 255)))
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
            if not proj_list and not skip_hit_fx:
                # No projectiles - this is a melee attack, trigger hit animation immediately
                if move_name not in ["Heal", "Guard", "Taunt", "Blessing", "Weakness", "Purify", "Pray"]:
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
                
                # Default hit particle
                if move_name not in ["Heal", "Guard", "Taunt", "Blessing", "Weakness", "Purify", "Pray"]:
                    self.spawn_particle(target.x + 75, target.y + 75, (255, 100, 100), (0,0), 20)
                
                # Specific Visuals
                if move_name == "Heal":
                    for _ in range(5):
                        self.spawn_particle(target.x + 75 + random.randint(-20, 20), target.y + 75 + random.randint(-20, 20), (255, 255, 0), (0, -1), 30, size=15, shape="plus")
                elif move_name == "Pray":
                    for _ in range(10):
                        self.spawn_particle(target.x + 75 + random.randint(-20, 20), target.y + 75 + random.randint(-20, 20), (255, 255, 100), (0, -2), 40, size=10, shape="plus")
                elif move_name == "Shield Bash":
                     self.spawn_particle(target.x + 75, target.y + 75, (100, 100, 255), (0, 0), 20, size=15, shape="circle")
                elif move_name == "Spin Slash":
                     for _ in range(8):
                        angle = random.uniform(0, 6.28)
                        vx = math.cos(angle) * 5
                        vy = math.sin(angle) * 5
                        self.spawn_particle(target.x + 75, target.y + 75, (200, 200, 200), (vx, vy), 20, size=3)
                target.shake_timer = 10
                self.floating_texts.append(FloatingText(target.x + 50, target.y, "HIT!", (255, 50, 50)))
            # else: projectiles exist - hit animation will trigger when projectile lands
            
            # Screen Shake on heavy hits
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
        if self.shake_timer > 0: self.shake_timer -= 1
        
        # Idle Particles
        if self.t1.get_active_member(): self.t1.get_active_member().update_idle_particles(self)
        if self.t2.get_active_member(): self.t2.get_active_member().update_idle_particles(self)
        if self.t1.get_active_member(): self.t1.get_active_member().update_idle_particles(self)
        if self.t2.get_active_member(): self.t2.get_active_member().update_idle_particles(self)
        self.process_animation_lock()
        
        # Multiplayer Polling
        if self.multiplayer and self.state == "WAITING_FOR_OPPONENT":
            self.poll_timer += 1
            if self.poll_timer % 60 == 0:
                state = self.client.get_state(self.game_id)
                if state:
                    # Check if turn changed to me
                    if state["turn"] == self.player_idx:
                        # Opponent moved!
                        last_action = state.get("last_action")
                        if last_action:
                            move_name = last_action["move"]
                            attacker = self.t2.get_active_member()
                            target = self.t1.get_active_member()
                            if move_name in ["Heal", "Blessing", "Purify", "Pray"]: target = attacker
                            
                            self.log(f"Opponent used {move_name}!")
                            self.execute_move(attacker, target, move_name)

    def draw_character(self, screen, char, x, y, is_flipped=False):
        # Floating removed
        offset = 0
        
        # Breathing Animation (Graphical Improvement #4)
        breath_scale = 1.0 + 0.02 * math.sin(pygame.time.get_ticks() * 0.005)
        
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
        
        # Lunge Logic
        lerp_speed = 0.15  # Default slower speed
        if char.current_sprite_override == "warrior_bash_charge": 
            lerp_speed = 0.08  # Extra slow charge for dramatic Shield Bash
        elif char.current_sprite_override in ["warrior_slash", "warrior_power_slash"]:
            lerp_speed = 0.2  # Medium speed for attack animations
        elif char.current_sprite_override in ["warrior_hit", "archer_hit", "mage_hit"]:
            lerp_speed = 0.0  # Stay still when hit
        elif char.current_sprite_override:
            lerp_speed = 0.25  # Other animations
        
        if char.target_x != 0:
            char.x += (char.target_x - char.x) * lerp_speed
            if abs(char.target_x - char.x) < 10: 
                # Reached target - pause at impact
                char.target_x = 0
                # If we were bashing, switch to post pose and pause
                if char.current_sprite_override == "warrior_bash_charge":
                    char.current_sprite_override = "warrior_bash_post"
                    char.hit_pause_timer = 30  # Pause for 30 frames (~0.5 seconds)
                    # Apply Shield Bash damage NOW (at impact)
                    if char.pending_bash_target:
                        char.pending_bash_target.hp -= int(20 / char.pending_bash_target.def_mod)
                        char.pending_bash_target.shake_timer = 10
                        # Show hit sprite on target if it's a warrior
                        if isinstance(char.pending_bash_target, Warrior):
                            char.pending_bash_target.current_sprite_override = "warrior_hit"
                            char.pending_bash_target.hit_animation_timer = 30
                            char.pending_bash_target.is_taking_hit = True
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
                    # Don't clear sprite override if character is taking a hit or is an archer firing
                    if not char.is_taking_hit and char.current_sprite_override not in ["archer_fire"]:
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
            draw_y_offset = -27  # Move up to align feet with ground
            draw_x_offset = 7   # Move right to align with shadow center
        elif isinstance(char, Somesh):
            draw_y_offset = -15 # Move up slightly to align feet (larger sprite)
            draw_x_offset = 0
        elif isinstance(char, Mage) and char.current_sprite_override == "mage_hit":
            draw_y_offset = 20  # Move down for smaller mage_hit sprite
            draw_x_offset = 0

        # Base Y position
        draw_y = y + offset + char.y_offset + draw_y_offset
        char.y = draw_y

        sprite_key = char.current_sprite_override if char.current_sprite_override else char.sprite_name
        img = self.manager.assets.get(sprite_key, self.manager.assets["warrior"])
        
        original_w = img.get_width()
        original_h = img.get_height()
        
        # Apply Breathing Scale (Upper Body Only)
        if not char.current_sprite_override: # Only breathe when idle
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
        
        # Death Tint (Softer Red)
        if char.hp <= 0:
            # Use BLEND_RGBA_MULT with a lighter red to preserve some detail/other channels
            # or just a reddish tint. (255, 100, 100) keeps some blue/green.
            img = tint_image(img, (255, 100, 100))
        
        # Somesh sprites are facing opposite direction, so flip logic is reversed
        flip_sprite = is_flipped
        if isinstance(char, Somesh):
            flip_sprite = not is_flipped
            
        if flip_sprite: img = pygame.transform.flip(img, True, False)
        
        # Shadow Logic (Fixed Alignment)
        # Center shadow based on image width
        shadow_w = 100
        shadow_x = char.x + (original_w - shadow_w) // 2 + shake_x
        # Position shadow at fixed ground level (240px from top) to align all characters
        # Note: We use the original 'y' and 'char.y_offset' (which is 0 for Archer)
        # We do NOT include draw_y_offset because that is for sprite correction only.
        shadow_y = y + offset + char.y_offset + 240
        
        pygame.draw.ellipse(screen, (0,0,0, 100), (shadow_x, shadow_y, shadow_w, 20))
        screen.blit(img, (char.x + shake_x + draw_x_offset, draw_y))
        
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
        hp_ratio = 0 if char.max_hp == 0 else max(0, min(1, char.hp / char.max_hp))
        hp_bg = pygame.Rect(char.x + 25 + shake_x, y - 28, bar_width, 16)
        pygame.draw.rect(screen, (10, 10, 10), hp_bg.inflate(4, 4), border_radius=6)
        pygame.draw.rect(screen, (80, 20, 20), hp_bg, border_radius=5)
        hp_fill = hp_bg.copy()
        hp_fill.width = int(hp_bg.width * hp_ratio)
        hp_color = (int(255 * (1 - hp_ratio)), int(80 + 120 * hp_ratio), 90)
        pygame.draw.rect(screen, hp_color, hp_fill, border_radius=5)
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
        game_surf.blit(self.manager.assets["bg"], (0, -220))
        
        t1_active = self.t1.get_active_member()
        if t1_active and t1_active.is_alive(): 
            self.draw_character(game_surf, t1_active, 200, 230, is_flipped=True)
        t2_active = self.t2.get_active_member()
        if t2_active and t2_active.is_alive(): 
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
                self.floating_texts.append(FloatingText(p.end_x, p.end_y - 20, "HIT!", (255, 50, 50)))
                # Trigger hit animation for warriors
                if math.hypot(p.end_x - 200, p.end_y - 230) < 200 and t1_active:
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
                elif t2_active:
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

        # Blit game surface with shake
        screen.blit(game_surf, (gx, gy))

        # UI (No shake)
        log_bg = pygame.Surface((220, 120), pygame.SRCALPHA)
        log_bg.fill((0, 0, 0, 150))
        screen.blit(log_bg, (10, 10))
        log_y = 10
        for msg in self.log_messages:
            txt = self.tiny_font.render(msg, True, hex_to_rgb(THEME["text_secondary"]))
            screen.blit(txt, (15, log_y))
            log_y += 16

        panel_height = 160
        action_panel = pygame.Surface((SCREEN_WIDTH, panel_height), pygame.SRCALPHA)
        panel_color = (5, 5, 15, 200) if self.state == "PLAYER_ACTION" else (20, 10, 10, 180)
        action_panel.fill(panel_color)
        screen.blit(action_panel, (0, SCREEN_HEIGHT - panel_height))
        prompt_color = (255, 255, 255) if self.state == "PLAYER_ACTION" else (200, 200, 200)
        prompt_text = self.font.render(self.action_prompt, True, prompt_color)
        screen.blit(prompt_text, (40, SCREEN_HEIGHT - panel_height + 20))
        hint_text = self.small_font.render("Press ESC to pause", True, (180, 180, 180))
        screen.blit(hint_text, (SCREEN_WIDTH - 220, SCREEN_HEIGHT - panel_height + 25))

        for btn in self.buttons: btn.draw(screen)

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

        if self.paused:
            pause_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pause_overlay.fill((0, 0, 0, 140))
            screen.blit(pause_overlay, (0, 0))
            paused_text = self.font.render("PAUSED", True, (255, 255, 255))
            screen.blit(paused_text, paused_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 20)))
            resume_hint = self.small_font.render("Press ESC to resume", True, (220, 220, 220))
            screen.blit(resume_hint, resume_hint.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 20)))
            self.exit_match_btn.draw(screen)

class GameOverScene(Scene):
    def __init__(self, manager, result):
        super().__init__(manager)
        self.result = result
        self.font = pygame.font.Font(None, 72)
        self.btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2 + 50, 200, 60, "MAIN MENU", self.go_menu)

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
        pygame.display.set_caption("God-Tier Battle Arena")
        self.clock = pygame.time.Clock()
        self.assets = {}
        self.sounds = {}
        self.font = pygame.font.Font(None, 32) # Shared font
        self.load_assets()
        self.mode = "LOCAL" # LOCAL, CREATE, JOIN
        self.game_id = None
        self.current_scene = StartScene(self)

    def load_assets(self):
        asset_dir = "assets"
        try:
            self.assets["bg"] = pygame.image.load(os.path.join(asset_dir, "Backgrounds", "ground.png")).convert()
            self.assets["bg"] = pygame.transform.scale(self.assets["bg"], (SCREEN_WIDTH, SCREEN_HEIGHT + 220))
        except:
            self.assets["bg"] = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT + 220))
            self.assets["bg"].fill(hex_to_rgb(THEME["background"]))
            
        # Load character sprites from their folders
        # Warrior sprites
        warrior_sprites = ["warrior", "warrior_bash_charge", "warrior_bash post", "warrior_power_slash", "warror_slash", "warrior_HIT"]
        for name in warrior_sprites:
            try:
                img = pygame.image.load(os.path.join(asset_dir, "Warrior", f"{name}.png")).convert_alpha()
                # Map filenames to asset keys
                asset_key = name
                if name == "warrior_bash post": asset_key = "warrior_bash_post"
                if name == "warror_slash": asset_key = "warrior_slash"  # Fix typo in filename
                if name == "warrior_HIT": asset_key = "warrior_hit"
                self.assets[asset_key] = pygame.transform.scale(img, (260, 260))
                print(f"✓ Loaded {name} as '{asset_key}'")
            except Exception as e:
                print(f"Failed to load {name}: {e}")
                self.assets.setdefault("warrior", pygame.Surface((260, 260)))
        
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
        
        # Load mage_attack sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "mage", "mage_attack.png")).convert_alpha()
            self.assets["mage_attack"] = pygame.transform.scale(img, (260, 260))
            print(f"✓ Loaded mage_attack.png")
        except Exception as e:
            print(f"Failed to load mage_attack: {e}")
        
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
        
        # Load Fah!! animation sprite
        try:
            img = pygame.image.load(os.path.join(asset_dir, "shesh", "FAHH!!!.png")).convert_alpha()
            self.assets["somesh_fah"] = pygame.transform.scale(img, (290, 290))
            print(f"✓ Loaded fahh!!.png as 'somesh_fah'")
        except Exception as e:
            print(f"Failed to load fahh!!: {e}")
        
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
        
        # Load sound effects
        try:
            self.sounds["fah"] = pygame.mixer.Sound(os.path.join(asset_dir, "shesh", "fah!!.mp3"))
            print(f"✓ Loaded fah!!.mp3")
        except Exception as e:
            print(f"Failed to load fah!!.mp3: {e}")

    def change_scene(self, scene_name):
        if scene_name == "START": self.current_scene = StartScene(self)
        elif scene_name == "SELECT": self.current_scene = SelectScene(self)
        elif scene_name == "MULTIPLAYER": self.current_scene = MultiplayerScene(self)
        elif scene_name == "LOBBY": self.current_scene = LobbyScene(self, self.game_id)

    def start_battle(self, p_team, ai_team):
        self.current_scene = BattleScene(self, p_team, ai_team)

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
                
                # Sync stats
                char.hp = m_data["hp"]
                char.max_hp = m_data["max_hp"]
                char.resource = m_data["resource"]
                # ... other stats if needed
                members.append(char)
            return members

        t1_members = create_team(state["t1"])
        t2_members = create_team(state["t2"])
        
        # If I am player 1 (Joiner), I am t2. But BattleScene expects t1 to be "me".
        # Actually BattleScene logic assumes t1 is player and t2 is enemy.
        # So if I am player_idx 1 (Joiner), I should swap them?
        # The server says: t1 is Host, t2 is Joiner.
        # If I am Host (0): t1 is me, t2 is enemy.
        # If I am Joiner (1): t2 is me, t1 is enemy.
        
        # However, BattleScene hardcodes "t1" as the player's team (left side).
        # So if I am Joiner, I should pass t2 as "my team" (first arg) and t1 as "enemy team" (second arg).
        
        if self.mode == "JOIN": # Joiner is player 1
             self.current_scene = BattleScene(self, t2_members, t1_members, multiplayer=True, player_idx=1, game_id=self.game_id)
        else: # Host is player 0
             self.current_scene = BattleScene(self, t1_members, t2_members, multiplayer=True, player_idx=0, game_id=self.game_id)

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
