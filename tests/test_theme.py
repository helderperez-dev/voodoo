import pytest
from voodoo.theme import Theme, ThemeColors, set_theme, default_theme

def test_default_theme():
    assert default_theme.mode == "dark"
    assert default_theme.colors.primary == "#007AFF"

def test_custom_theme():
    custom_colors = ThemeColors(primary="#FF0000", extra={"custom": "#00FF00"})
    theme = Theme(mode="light", colors=custom_colors)
    
    assert theme.mode == "light"
    assert theme.colors.primary == "#FF0000"
    
    css_vars = theme.to_css_variables()
    assert "--color-primary: #FF0000;" in css_vars
    assert "--color-custom: #00FF00;" in css_vars
    
    tw_config = theme.to_tailwind_config()
    assert '"primary": "#FF0000"' in tw_config
    assert '"custom": "#00FF00"' in tw_config

def test_set_theme():
    original_theme = default_theme
    try:
        new_theme = Theme(mode="light")
        set_theme(new_theme)
        
        # In voodoo.theme namespace, default_theme should be updated
        import voodoo.theme
        assert voodoo.theme.default_theme.mode == "light"
    finally:
        set_theme(original_theme)
