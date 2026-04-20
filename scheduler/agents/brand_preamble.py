"""Seva Mining brand preamble for claude.ai artifact prompts.

Concatenated verbatim at the start of every image_prompt emitted by the content agent
for infographic and quote post types. Centralizing the visual spec keeps prompts DRY
and makes brand updates a one-line change.

Target: claude.ai artifacts / cowork. Operator pastes the full image_prompt into claude.ai
and receives a finished HTML artifact they can screenshot for social.
"""

BRAND_PREAMBLE = """You are building a Seva Mining editorial social asset as a single self-contained HTML artifact. The operator will screenshot the rendered artifact for Twitter/X.

BRAND PALETTE (use exactly these hex codes):
- Cream background: #F0ECE4
- Deep navy primary: #0C1B32
- Lighter navy secondary: #1E3A5F
- Teal secondary: #4A7FA5
- Muted blue-gray text: #5A6B7A
- Gold accent: #D4AF37 (reserved for hero stats only — use sparingly)
- Warm gridlines: #D8D2C8 (horizontal-only, subtle)

TYPOGRAPHY:
- Titles: DM Serif Display (or a high-contrast editorial serif like Playfair Display as fallback)
- Body and data labels: Inter (or a clean modern sans-serif)

LAYOUT (a16z editorial):
- Large serif title, sans subtitle beneath
- Horizontal-only gridlines for any charts
- Uniform solid bars, no gradients, value labels at bar tips
- "SEVA MINING" wordmark bottom-right in small caps, muted blue-gray
- Source attribution bottom-left, smaller still
- Generous whitespace, no decorative elements

DIMENSIONS: 1200x675 (16:9, Twitter card friendly).

FORMAT: Produce as a single self-contained HTML artifact I can screenshot. Inline all CSS. No external fonts, images, or scripts — use system serif/sans fallbacks if DM Serif Display / Inter are not available in your runtime.
"""
