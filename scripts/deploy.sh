#!/bin/bash
# Deploy Russian Portfolio Dashboard to GitHub Pages
# Runs the dashboard generator, then pushes output HTML to gh-pages branch.
#
# Usage: ./scripts/deploy.sh
# Cron:  0 5 * * 0  cd /Users/iibot/Documents/ppppp/workspace/portfolio-dashboard-v2 && ./scripts/deploy.sh >> logs/deploy.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
OUTPUT_DIR="$PROJECT_DIR/output"
TIMESTAMP=$(date '+%Y-%m-%d_%H%M')

mkdir -p "$LOG_DIR"

echo "═══════════════════════════════════════════"
echo "🇷🇺 Dashboard Deploy — $TIMESTAMP"
echo "═══════════════════════════════════════════"

cd "$PROJECT_DIR"

# Step 1: Generate dashboard
echo "Step 1: Generating dashboard..."
python3 -m src.dashboard -o "$OUTPUT_DIR/index.html"

if [ ! -f "$OUTPUT_DIR/index.html" ]; then
    echo "❌ Dashboard generation failed — no output file"
    exit 1
fi

echo "  ✅ Dashboard generated ($(du -h "$OUTPUT_DIR/index.html" | cut -f1))"

# Step 2: Deploy to GitHub Pages using gh-pages branch
echo "Step 2: Deploying to GitHub Pages..."

DEPLOY_DIR=$(mktemp -d)
cd "$DEPLOY_DIR"

git init -q
git remote add origin https://github.com/lopushokbot/ru-portfolio-dashboard.git

# Copy output
cp "$OUTPUT_DIR/index.html" index.html

# Add SEO files
cat > robots.txt << 'ROBOTS'
User-agent: *
Allow: /
Sitemap: https://lopushokbot.github.io/ru-portfolio-dashboard/sitemap.xml
ROBOTS

cat > sitemap.xml << SITEMAP
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://lopushokbot.github.io/ru-portfolio-dashboard/</loc>
    <lastmod>$(date '+%Y-%m-%d')</lastmod>
    <changefreq>weekly</changefreq>
  </url>
</urlset>
SITEMAP

git add -A
git commit -q -m "Dashboard update $TIMESTAMP"
git branch -M gh-pages
git push -f origin gh-pages 2>&1

cd "$PROJECT_DIR"
rm -rf "$DEPLOY_DIR"

echo "  ✅ Deployed to https://lopushokbot.github.io/ru-portfolio-dashboard/"
echo ""
echo "Done."
