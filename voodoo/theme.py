import json
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ThemeColors(BaseModel):
    """Modern color palette for the theme."""
    primary: str = "#007AFF" # Apple blue
    secondary: str = "#5856D6" # Violet
    
    # Dark mode
    background: str = "#0A0A0A" # Charcoal
    surface: str = "rgba(255, 255, 255, 0.05)" # Glass surface
    text: str = "#F3F4F6"
    text_muted: str = "#9CA3AF"
    border: str = "rgba(255, 255, 255, 0.1)"
    
    # Light mode
    light_background: str = "#F9FAFB"
    light_surface: str = "rgba(0, 0, 0, 0.05)"
    light_text: str = "#111827"
    light_text_muted: str = "#4B5563"
    light_border: str = "rgba(0, 0, 0, 0.1)"
    
    # Allow extra colors
    extra: Dict[str, str] = Field(default_factory=dict)

class ThemeFonts(BaseModel):
    """Typography settings."""
    sans: str = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
    mono: str = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace'

class Theme(BaseModel):
    """
    Core Theme configuration for Voodoo.
    Designed for modern macOS 'glass' aesthetic.
    """
    mode: str = "dark" # dark, light, system
    colors: ThemeColors = Field(default_factory=ThemeColors)
    fonts: ThemeFonts = Field(default_factory=ThemeFonts)
    
    def to_tailwind_config(self) -> str:
        """Generates the Tailwind configuration script."""
        
        # Build the colors dictionary for Tailwind
        tw_colors = {
            "primary": self.colors.primary,
            "secondary": self.colors.secondary,
            "background": self.colors.background,
            "surface": self.colors.surface,
            "text": self.colors.text,
            "text-muted": self.colors.text_muted,
            "border": self.colors.border,
        }
        tw_colors.update(self.colors.extra)

        config = {
            "darkMode": 'class',
            "theme": {
                "extend": {
                    "colors": {
                        "voodoo": tw_colors
                    },
                    "fontFamily": {
                        "sans": [self.fonts.sans],
                        "mono": [self.fonts.mono]
                    }
                }
            }
        }
        return json.dumps(config)

    def to_css_variables(self) -> str:
        """Generates global CSS variables for the theme."""
        dark_vars = [
            f"--color-primary: {self.colors.primary};",
            f"--color-secondary: {self.colors.secondary};",
            f"--color-background: {self.colors.background};",
            f"--color-surface: {self.colors.surface};",
            f"--color-text: {self.colors.text};",
            f"--color-text-muted: {self.colors.text_muted};",
            f"--color-border: {self.colors.border};",
            f"--font-sans: {self.fonts.sans};",
            f"--font-mono: {self.fonts.mono};",
        ]
        light_vars = [
            f"--color-primary: {self.colors.primary};",
            f"--color-secondary: {self.colors.secondary};",
            f"--color-background: {self.colors.light_background};",
            f"--color-surface: {self.colors.light_surface};",
            f"--color-text: {self.colors.light_text};",
            f"--color-text-muted: {self.colors.light_text_muted};",
            f"--color-border: {self.colors.light_border};",
            f"--font-sans: {self.fonts.sans};",
            f"--font-mono: {self.fonts.mono};",
        ]
        
        for k, v in self.colors.extra.items():
            dark_vars.append(f"--color-{k}: {v};")
            light_vars.append(f"--color-{k}: {v};")
            
        return (
            ":root {\n    " + "\n    ".join(light_vars) + "\n}\n" +
            ".dark {\n    " + "\n    ".join(dark_vars) + "\n}"
        )

# Global default theme
default_theme = Theme()

def set_theme(theme: Theme):
    """Sets the global default theme."""
    global default_theme
    default_theme = theme
