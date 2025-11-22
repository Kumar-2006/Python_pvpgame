"""Battle Legends - Main Menu (CustomTkinter)

Modern, futuristic main menu for the fantasy RPG "Battle Legends".
Implements dark neon theme, 900x600 centered window, optional background
with fallback, glow-hover buttons, and fade-in effect.

Dependencies: customtkinter, pillow (PIL).
"""

import os
from typing import Tuple

try:
    import customtkinter as ctk
except Exception:
    print("Missing dependency: customtkinter. Install with: pip install customtkinter")
    raise

try:
    from PIL import Image, ImageDraw, ImageFilter
except Exception:
    print("Missing dependency: pillow. Install with: pip install pillow")
    raise

WIDTH, HEIGHT = 900, 600
BG_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "arena_bg.png")

NEON_CYAN = "#00F0FF"
NEON_BLUE = "#0AB7FF"
GOLD = "#D4AF37"
GOLD_HOVER = "#FFEA00"
CRIMSON = "#DC143C"
CRIMSON_HOVER = "#FF3030"
PURPLE = "#7B2CBF"
VIOLET_HOVER = "#9B5DE5"
SUBTITLE_GRAY = "#A6A6A6"
DARK_BG = "#05060A"
OVERLAY = "#071025"

TITLE_FONT = ("Orbitron", 36, "bold")
SUBTITLE_FONT = ("Rajdhani", 14)
BUTTON_FONT = ("Rajdhani", 16, "bold")
FOOTER_FONT = ("Helvetica", 9)

def load_background_photo(path: str, size: Tuple[int, int]) -> ctk.CTkImage:
    """Load the arena background or synthesize a neon gradient fallback."""
    width, height = size
    if os.path.exists(path):
        img = Image.open(path).convert("RGBA")
        img = img.resize((width, height), Image.LANCZOS)
    else:
        img = Image.new("RGBA", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)
        for y in range(height):
            t = y / max(1, height - 1)
            r = int(6 + (12 - 6) * t)
            g = int(8 + (30 - 8) * t)
            b = int(12 + (60 - 12) * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.ellipse((-width // 2, height // 4, width + width // 2, height), fill=(0, 140, 220, 35))
        glow = glow.filter(ImageFilter.GaussianBlur(90))
        img = Image.alpha_composite(img, glow)

    return ctk.CTkImage(light_image=img, dark_image=img, size=(width, height))


class BattleMenu:
    """CustomTkinter-based landing page for Battle Legends."""

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        root.title("Battle Legends")
        root.geometry(f"{WIDTH}x{HEIGHT}")
        root.resizable(False, False)

        self._center_window()
        root.attributes("-alpha", 0.0)

        self._apply_background()
        self._build_content()
        self._fade_in(650)

    def _center_window(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        offset_x = (screen_w - WIDTH) // 2
        offset_y = (screen_h - HEIGHT) // 2
        self.root.geometry(f"{WIDTH}x{HEIGHT}+{offset_x}+{offset_y}")

    def _apply_background(self) -> None:
        photo = load_background_photo(BG_IMAGE_PATH, (WIDTH, HEIGHT))
        self._bg_image = photo
        bg_label = ctk.CTkLabel(self.root, image=photo, text="")
        bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        overlay = ctk.CTkFrame(self.root, width=WIDTH, height=HEIGHT, fg_color=OVERLAY, corner_radius=0)
        overlay.place(relx=0.5, rely=0.5, anchor="center")
        self.overlay = overlay

    def _build_content(self) -> None:
        content = ctk.CTkFrame(self.overlay, width=720, height=460, fg_color="transparent", corner_radius=12)
        content.place(relx=0.5, rely=0.47, anchor="center")

        title = ctk.CTkLabel(content, text="⚔️ BATTLE LEGENDS ⚔️", font=TITLE_FONT, text_color=NEON_CYAN)
        title.pack(pady=(20, 6))

        subtitle = ctk.CTkLabel(
            content,
            text="Strategic Fantasy Combat Reimagined",
            font=SUBTITLE_FONT,
            text_color=SUBTITLE_GRAY,
        )
        subtitle.pack(pady=(0, 24))

        buttons = ctk.CTkFrame(content, fg_color="transparent")
        buttons.pack(pady=(8, 12))

        self._start_btn = self._glow_button(buttons, "Start Battle", NEON_BLUE, NEON_CYAN, self._on_start)
        self._howto_btn = self._glow_button(buttons, "How to Play", GOLD, GOLD_HOVER, self._on_howto)
        self._board_btn = self._glow_button(buttons, "Leaderboard", PURPLE, VIOLET_HOVER, self._on_board)
        self._quit_btn = self._glow_button(buttons, "Quit", CRIMSON, CRIMSON_HOVER, self._on_quit)

        footer = ctk.CTkLabel(
            self.root,
            text="© 2025 Battle Legends Studio - All Rights Reserved.",
            font=FOOTER_FONT,
            text_color=SUBTITLE_GRAY,
        )
        footer.place(relx=0.5, rely=0.97, anchor="s")

    def _glow_button(
        self,
        container: ctk.CTkFrame,
        text: str,
        base_color: str,
        hover_color: str,
        command,
    ) -> ctk.CTkButton:
        glow = ctk.CTkFrame(container, fg_color=base_color, corner_radius=18)
        glow.pack(pady=10)

        button = ctk.CTkButton(
            glow,
            text=text,
            fg_color=base_color,
            hover_color=hover_color,
            text_color="#020204",
            font=BUTTON_FONT,
            corner_radius=16,
            width=440,
            height=52,
            command=command,
            border_width=2,
            border_color=base_color,
        )
        button.pack(padx=6, pady=6)

        button.bind("<Enter>", lambda _e, btn=button, color=hover_color: btn.configure(fg_color=color))
        button.bind("<Leave>", lambda _e, btn=button, color=base_color: btn.configure(fg_color=color))
        return button

    def _on_start(self) -> None:
        print("Start Battle Clicked!")

    def _on_howto(self) -> None:
        print("How to Play Clicked!")

    def _on_board(self) -> None:
        print("Leaderboard Clicked!")

    def _on_quit(self) -> None:
        print("Quit Clicked!")
        self.root.destroy()

    def _fade_in(self, duration_ms: int) -> None:
        steps = 22
        delay = max(1, duration_ms // steps)

        def step(i: int = 0) -> None:
            self.root.attributes("-alpha", i / steps)
            if i < steps:
                self.root.after(delay, lambda: step(i + 1))

        step()


def main() -> None:
    app = ctk.CTk()
    BattleMenu(app)
    app.mainloop()


if __name__ == "__main__":
    main()
