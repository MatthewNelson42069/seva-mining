#!/bin/sh
# download-fonts.sh — Download Inter TTF fonts for the chart renderer.
#
# Called during Docker build (after npm ci) to fetch Inter-Regular.ttf and Inter-Bold.ttf.
# Fonts are NOT committed to the repo — they are downloaded at build time.
# resvg-js requires TTF format (not WOFF2).
#
# Font source: Official Inter GitHub releases (rsms/inter)
# Version: 4.0 — stable release from Dec 2023, widely available.

set -e

mkdir -p fonts

echo "[download-fonts] Downloading Inter 4.0 TTF fonts..."

curl -L --fail --retry 3 \
  "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip" \
  -o /tmp/inter.zip

echo "[download-fonts] Extracting Inter-Regular.ttf and Inter-Bold.ttf..."

# The zip contains fonts in "extras/ttf/" subdirectory (Inter 4.0 layout)
unzip -j /tmp/inter.zip \
  "extras/ttf/Inter-Regular.ttf" \
  "extras/ttf/Inter-Bold.ttf" \
  -d fonts/

rm /tmp/inter.zip

echo "[download-fonts] Done. Fonts available:"
ls -lh fonts/*.ttf
