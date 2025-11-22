"""
Screen Effects Module
Provides visual controllers for camera shake, slow motion, color filters, zoom, and motion blur.
"""

import pygame
import random
import math


class ScreenShakeController:
    """Manages camera shake with variable intensity and decay."""
    
    def __init__(self):
        self.shakes = []  # List of active shake effects
    
    def add_shake(self, intensity, duration, direction=None):
        """
        Add a shake effect.
        
        Args:
            intensity: Maximum offset in pixels (e.g., 5 for light, 15 for heavy)
            duration: Number of frames to shake
            direction: Optional (dx, dy) tuple for directional shake, None for omni
        """
        self.shakes.append({
            'intensity': intensity,
            'duration': duration,
            'max_duration': duration,
            'direction': direction
        })
    
    def update(self):
        """Update all active shakes, removing expired ones."""
        for shake in self.shakes[:]:
            shake['duration'] -= 1
            if shake['duration'] <= 0:
                self.shakes.remove(shake)
    
    def get_offset(self):
        """Get current camera offset as (x, y) tuple."""
        if not self.shakes:
            return (0, 0)
        
        total_x = 0
        total_y = 0
        
        for shake in self.shakes:
            # Calculate decay (shake reduces as duration decreases)
            decay = shake['duration'] / shake['max_duration']
            current_intensity = shake['intensity'] * decay
            
            if shake['direction']:
                # Directional shake
                dx, dy = shake['direction']
                total_x += dx * current_intensity
                total_y += dy * current_intensity
            else:
                # Random shake
                total_x += random.uniform(-current_intensity, current_intensity)
                total_y += random.uniform(-current_intensity, current_intensity)
        
        return (int(total_x), int(total_y))


class SlowMotionController:
    """Manages time dilation effects for dramatic moments."""
    
    def __init__(self):
        self.time_scale = 1.0
        self.target_scale = 1.0
        self.duration = 0
        self.transition_speed = 0.1
    
    def trigger(self, speed_factor, duration):
        """
        Trigger slow motion effect.
        
        Args:
            speed_factor: Time scale (0.1 = 10% speed, 1.0 = normal)
            duration: Number of frames to maintain slow motion
        """
        self.target_scale = speed_factor
        self.duration = duration
    
    def update(self):
        """Update time scale, smoothly transitioning."""
        if self.duration > 0:
            # Transitioning to slow motion
            self.time_scale += (self.target_scale - self.time_scale) * self.transition_speed
            self.duration -= 1
        else:
            # Return to normal speed
            self.time_scale += (1.0 - self.time_scale) * self.transition_speed
            if abs(self.time_scale - 1.0) < 0.01:
                self.time_scale = 1.0
    
    def get_time_scale(self):
        """Get current time scale multiplier."""
        return self.time_scale
    
    def is_active(self):
        """Check if slow motion is currently active."""
        return self.time_scale < 0.99


class ScreenFlashController:
    """Manages full-screen color flashes."""
    
    def __init__(self):
        self.flashes = []
    
    def flash(self, color, duration, intensity=255):
        """
        Trigger a screen flash.
        
        Args:
            color: RGB tuple (e.g., (255, 0, 0) for red)
            duration: Number of frames
            intensity: Maximum alpha (0-255)
        """
        self.flashes.append({
            'color': color,
            'duration': duration,
            'max_duration': duration,
            'max_intensity': intensity
        })
    
    def update(self):
        """Update all active flashes."""
        for flash in self.flashes[:]:
            flash['duration'] -= 1
            if flash['duration'] <= 0:
                self.flashes.remove(flash)
    
    def draw(self, surface):
        """Draw all active flashes to the surface."""
        for flash in self.flashes:
            # Calculate fade (intensity decreases over time)
            fade = flash['duration'] / flash['max_duration']
            alpha = int(flash['max_intensity'] * fade)
            
            # Create flash surface
            flash_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            flash_surf.fill((*flash['color'], alpha))
            surface.blit(flash_surf, (0, 0))


class VignetteEffect:
    """Dynamic vignette that intensifies based on character HP."""
    
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        self.intensity = 0.0
        self.target_intensity = 0.0
        self.color = (0, 0, 0)  # Default black vignette
        self.pulse_phase = 0
    
    def set_intensity(self, intensity, color=(0, 0, 0)):
        """
        Set vignette target intensity.
        
        Args:
            intensity: 0.0 (none) to 1.0 (full coverage)
            color: RGB tuple for vignette color
        """
        self.target_intensity = intensity
        self.color = color
    
    def update(self):
        """Update vignette, smoothly transitioning."""
        # Smooth transition
        self.intensity += (self.target_intensity - self.intensity) * 0.1
        
        # Pulse effect when active
        if self.intensity > 0.1:
            self.pulse_phase += 0.1
    
    def draw(self, surface):
        """Draw vignette overlay."""
        if self.intensity < 0.01:
            return
        
        # Create radial gradient vignette
        vignette_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        
        center_x = self.width // 2
        center_y = self.height // 2
        max_radius = math.hypot(center_x, center_y)
        
        # Pulse effect
        pulse = 1.0 + math.sin(self.pulse_phase) * 0.1 * self.intensity
        
        # Draw radial gradient (darker at edges)
        for radius_step in range(20):
            radius = (radius_step / 20) * max_radius * 1.2
            alpha = int((radius_step / 20) ** 2 * 200 * self.intensity * pulse)
            pygame.draw.ellipse(
                vignette_surf,
                (*self.color, alpha),
                (center_x - radius, center_y - radius, radius * 2, radius * 2)
            )
        
        surface.blit(vignette_surf, (0, 0))


class ZoomController:
    """Manages dynamic camera zoom effects."""
    
    def __init__(self):
        self.zoom_level = 1.0
        self.target_zoom = 1.0
        self.transition_speed = 0.05
    
    def set_zoom(self, level):
        """Set target zoom level (1.0 = normal, 1.2 = 20% closer)."""
        self.target_zoom = level
    
    def update(self):
        """Update zoom, smoothly transitioning."""
        self.zoom_level += (self.target_zoom - self.zoom_level) * self.transition_speed
    
    def get_zoom(self):
        """Get current zoom level."""
        return self.zoom_level
    
    def apply_zoom(self, surface, screen_width, screen_height):
        """
        Apply zoom to a surface.
        
        Returns:
            Zoomed and centered surface
        """
        if abs(self.zoom_level - 1.0) < 0.01:
            return surface
        
        # Calculate new size
        new_w = int(screen_width * self.zoom_level)
        new_h = int(screen_height * self.zoom_level)
        
        # Scale surface
        zoomed = pygame.transform.scale(surface, (new_w, new_h))
        
        # Center crop to original size
        crop_x = (new_w - screen_width) // 2
        crop_y = (new_h - screen_height) // 2
        
        result = pygame.Surface((screen_width, screen_height))
        result.blit(zoomed, (-crop_x, -crop_y))
        
        return result


class MotionBlurTrail:
    """Creates motion blur effect by tracking entity positions."""
    
    def __init__(self, max_positions=5):
        self.positions = []
        self.max_positions = max_positions
        self.enabled = False
    
    def enable(self):
        """Enable motion blur tracking."""
        self.enabled = True
    
    def disable(self):
        """Disable and clear motion blur."""
        self.enabled = False
        self.positions.clear()
    
    def add_position(self, x, y, image=None):
        """Add a position to the trail."""
        if not self.enabled:
            return
        
        self.positions.append({'x': x, 'y': y, 'image': image})
        
        # Keep only recent positions
        if len(self.positions) > self.max_positions:
            self.positions.pop(0)
    
    def draw(self, surface):
        """Draw motion blur trail with fading opacity."""
        if not self.enabled or len(self.positions) < 2:
            return
        
        for i, pos in enumerate(self.positions[:-1]):  # Skip last (current) position
            # Calculate opacity (older = more transparent)
            alpha = int((i / len(self.positions)) * 120)
            
            if pos['image']:
                # Draw with alpha
                img_copy = pos['image'].copy()
                img_copy.set_alpha(alpha)
                surface.blit(img_copy, (int(pos['x']), int(pos['y'])))


class ColorFilterController:
    """Manages full-screen color filter overlays."""
    
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        self.filters = []
    
    def add_filter(self, filter_type, intensity):
        """
        Add a color filter effect.
        
        Args:
            filter_type: 'desaturate', 'red_tint', 'golden_glow'
            intensity: 0.0 to 1.0
        """
        self.filters.append({
            'type': filter_type,
            'intensity': intensity
        })
    
    def clear_filters(self):
        """Remove all active filters."""
        self.filters.clear()
    
    def draw(self, surface):
        """Apply all active filters."""
        for filter_data in self.filters:
            intensity = filter_data['intensity']
            
            if filter_data['type'] == 'desaturate':
                # Grayscale overlay
                gray_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                gray_surf.fill((128, 128, 128, int(180 * intensity)))
                surface.blit(gray_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            
            elif filter_data['type'] == 'red_tint':
                # Red overlay
                red_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                red_surf.fill((255, 100, 100, int(100 * intensity)))
                surface.blit(red_surf, (0, 0))
            
            elif filter_data['type'] == 'golden_glow':
                # Golden overlay
                gold_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                gold_surf.fill((255, 215, 0, int(50 * intensity)))
                surface.blit(gold_surf, (0, 0))


class RainEffect:
    """Manages rain particles and rendering."""
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        self.drops = []
        self.intensity = 1.0 # 0.0 to 1.0
        
        # Pre-generate some drops
        for _ in range(100):
            self.add_drop(random.randint(0, self.height))

    def add_drop(self, start_y=0):
        x = random.randint(0, self.width)
        y = start_y
        length = random.randint(10, 20)
        speed = random.randint(15, 25)
        self.drops.append([x, y, length, speed])

    def update(self):
        # Add new drops based on intensity
        if random.random() < self.intensity:
            for _ in range(int(5 * self.intensity)):
                self.add_drop(-20)
        
        # Update existing drops
        for drop in self.drops:
            drop[1] += drop[3] # y += speed
        
        # Remove drops off screen
        self.drops = [d for d in self.drops if d[1] < self.height]

    def draw(self, surface):
        for drop in self.drops:
            x, y, length, speed = drop
            # Draw rain drop (light blue/gray line)
            start_pos = (x, y)
            end_pos = (x, y + length)
            color = (200, 200, 255, 150) # Semi-transparent
            pygame.draw.line(surface, color, start_pos, end_pos, 1)
