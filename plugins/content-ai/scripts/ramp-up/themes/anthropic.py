"""
Anthropic brand theme for PPTX generation.
Colors, fonts, and layout constants.
"""

from pptx.dml.color import RGBColor
from pptx.util import Pt


# --- Brand Colors ---
ANTHRACITE = RGBColor(0x19, 0x19, 0x2B)
CLAUDE_ORANGE = RGBColor(0xDA, 0x7A, 0x3C)
CLAUDE_CREAM = RGBColor(0xF5, 0xF0, 0xE8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK_TEXT = RGBColor(0x1A, 0x1A, 0x2E)
LIGHT_GRAY = RGBColor(0x6B, 0x6B, 0x80)
ACCENT_BLUE = RGBColor(0x4A, 0x90, 0xD9)
ACCENT_GREEN = RGBColor(0x3D, 0xA3, 0x6E)
ACCENT_RED = RGBColor(0xD9, 0x4A, 0x4A)
BG_LIGHT = RGBColor(0xF8, 0xF6, 0xF3)
SECTION_BG = RGBColor(0x2D, 0x2D, 0x44)
ALT_ROW = RGBColor(0xF0, 0xED, 0xE8)

# --- Theme dict (passed to engine) ---
THEME = {
    "name": "anthropic",
    # Backgrounds
    "title_bg": ANTHRACITE,
    "section_bg": SECTION_BG,
    "content_bg": BG_LIGHT,
    # Accent
    "accent": CLAUDE_ORANGE,
    "accent_bar_height": Pt(4),
    # Text colors
    "title_text": WHITE,
    "subtitle_text": CLAUDE_CREAM,
    "heading_text": DARK_TEXT,
    "body_text": DARK_TEXT,
    "muted_text": LIGHT_GRAY,
    # Table
    "table_header_bg": ANTHRACITE,
    "table_header_text": WHITE,
    "table_row_even": WHITE,
    "table_row_odd": ALT_ROW,
    # Side stripe
    "stripe_color": CLAUDE_ORANGE,
    # Footer
    "footer_text": LIGHT_GRAY,
}
