#!/bin/sh
# download-fonts.sh — Download TTF fonts for the chart renderer.
#
# Called during Docker build (after npm ci) to fetch the fonts used by the
# a16z-style theme (theme.js):
#   - Inter-Regular.ttf, Inter-Bold.ttf  — body, axis ticks, values, source
#   - DMSerifDisplay-Regular.ttf         — serif display titles + hero stat values
#
# Fonts are NOT committed to the repo — they are downloaded at build time.
# resvg-js requires TTF format (not WOFF2).
#
# Sources:
#   - Inter 4.0 from official rsms/inter GitHub releases
#   - DM Serif Display from google/fonts monorepo (SIL OFL license)
#
# Why DM Serif Display (not Playfair Display): Google only ships Playfair as
# a variable-wght TTF (PlayfairDisplay[wght].ttf), which resvg-js 2.6.x does
# not resolve reliably. DM Serif Display ships as a static TTF and renders
# correctly through the resvg-js `fontFiles` loader. It's also a higher-
# contrast, heavier display serif — a better match for the a16z aesthetic.

set -e

mkdir -p fonts

# -------- Inter (body + labels) --------
echo "[download-fonts] Downloading Inter 4.0 TTF fonts..."
curl -L --fail --retry 3 \
  "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip" \
  -o /tmp/inter.zip

echo "[download-fonts] Extracting Inter-Regular.ttf and Inter-Bold.ttf..."
# Inter 4.0 layout places TTFs under extras/ttf/ (-o: overwrite without prompting)
unzip -jo /tmp/inter.zip \
  "extras/ttf/Inter-Regular.ttf" \
  "extras/ttf/Inter-Bold.ttf" \
  -d fonts/

rm /tmp/inter.zip

# -------- DM Serif Display (display titles) --------
# Static Regular weight only — the face is heavy by design and doesn't need a
# separate Bold for editorial headlines.
echo "[download-fonts] Downloading DM Serif Display Regular TTF..."
curl -L --fail --retry 3 \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/dmserifdisplay/DMSerifDisplay-Regular.ttf" \
  -o "fonts/DMSerifDisplay-Regular.ttf"

echo "[download-fonts] Done. Fonts available:"
ls -lh fonts/*.ttf
