#!/usr/bin/env bash
# =============================================================================
# cron_publish.sh — Stage B: Daily cron-driven deployment
#
# This script is intended to be run daily via cron. It:
#   1. Checks if Stage A has completed (presence of staged PDF + meta)
#   2. Runs publisher.py --stage=B to push to GitHub
#   3. Triggers Cloudflare Pages deployment
#   4. Updates recently_published.json for topic diversity tracking
#
# Crontab example:
#   0 8 * * * cd /path/to/reports-pipeline && bash cron_publish.sh >> publish.log 2>&1
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="${PYTHON:-python3}"
STAGE_A_FLAG="../static/reports/.last_stage_a"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; }

# -------------------------------------------------------------------------
# Check if Stage A completed
# -------------------------------------------------------------------------
if [ ! -f "$STAGE_A_FLAG" ]; then
    warn "No Stage A staging found (missing .last_stage_a)"
    warn "Run 'bash run.sh' first to generate and stage a report."
    exit 0
fi

# Check if staging is fresh (within last 24 hours)
STAGE_AGE=$(($(date +%s) - $(stat -c %Y "$STAGE_A_FLAG" 2>/dev/null || stat -f %m "$STAGE_A_FLAG" 2>/dev/null || echo 0)))
if [ "$STAGE_AGE" -gt 86400 ]; then
    warn "Stage A staging is older than 24 hours ($STAGE_AGE seconds). Skipping."
    exit 0
fi

log "Stage A staging found (age: ${STAGE_AGE}s), proceeding with Stage B publish"

# -------------------------------------------------------------------------
# Check for staged files
# -------------------------------------------------------------------------
STAGED_PDFS=$(ls -t ../static/reports/*.pdf 2>/dev/null | head -3 || echo "")
if [ -z "$STAGED_PDFS" ]; then
    err "No staged PDFs found in static/reports/"
    exit 1
fi

log "Staged PDFs found:"
echo "$STAGED_PDFS" | while read -r pdf; do
    echo "  - $pdf"
done

# -------------------------------------------------------------------------
# Stage B: Publish
# -------------------------------------------------------------------------
log "Running publisher.py --stage=B"
COMMIT_MSG="publish: weekly report $(date +%Y-%m-%d)"
$PYTHON publisher.py --stage=B --message="$COMMIT_MSG"

# -------------------------------------------------------------------------
# Update recently_published.json for diversity tracking
# -------------------------------------------------------------------------
log "Updating recently_published.json"
$PYTHON -c "
import json, sys
from pathlib import Path
from datetime import datetime

reports_json = Path('../static/reports/reports.json')
recent_json = Path('recently_published.json')

if reports_json.exists():
    data = json.loads(reports_json.read_text())
    recent = []
    for r in data.get('reports', [])[:5]:
        recent.append({
            'name': r.get('title', ''),
            'category': r.get('category', ''),
            'date': r.get('date', ''),
        })
    recent_json.write_text(json.dumps(recent, indent=2))
    print(f'  Updated with {len(recent)} recent reports')
"

# -------------------------------------------------------------------------
# Done
# -------------------------------------------------------------------------
log ""
log "=========================================="
log "  Stage B publish complete!"
log "  $(date)"
log "=========================================="