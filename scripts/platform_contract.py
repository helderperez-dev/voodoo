"""Small cross-platform import/render contract used by CI."""

from voodoo.ui import Button
from voodoo.ui.styles.theme import default_theme

html = Button("Platform", render_key="platform-contract").render()
assert 'type="button"' in html
assert 'id="vd-button-' in html
assert "--vd-space-sm" in default_theme.to_css_variables()
print("platform contract passed")
