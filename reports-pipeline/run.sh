#!/usr/bin/env bash
# =============================================================================
# run.sh — Stage A: Six-step weekly report pipeline (full generation)
#
# Steps:
#   1. Crawl sources with crawler.py --weekly
#   2. Pick topic with topic_picker.py
#   3. Generate report with generator_v2.py
#   4. De-AI with deai.py
#   5. Citation check with citation_check.py
#   6. Render PDF with pdf_engine.py
#   7. Stage for publishing with publisher.py --stage=A
#
# Usage:
#   bash run.sh                    # interactive mode
#   bash run.sh --topic="CRM Trends"  # specify topic
#   bash run.sh --skip-crawl          # skip crawling (use cached data)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
PYTHON="${PYTHON:-python3}"
TOPIC="${TOPIC:-}"
SKIP_CRAWL="${SKIP_CRAWL:-false}"
OUTPUT_DIR="${SCRIPT_DIR}/output"
TIMESTAMP=$(date +%Y-%m-%d)

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse CLI args
for arg in "$@"; do
    case $arg in
        --topic=*)  TOPIC="${arg#*=}" ;;
        --skip-crawl) SKIP_CRAWL=true ;;
        *) ;;
    esac
done

mkdir -p "$OUTPUT_DIR"

# =============================================================================
# Step 1: Crawl sources
# =============================================================================
if [ "$SKIP_CRAWL" != "true" ]; then
    log "Step 1/7: Crawling sources (--weekly mode)"
    $PYTHON crawler.py --weekly --output "$OUTPUT_DIR/scraped_items.json"
else
    warn "Skipping crawl (--skip-crawl flag)"
    if [ ! -f "$OUTPUT_DIR/scraped_items.json" ]; then
        err "No cached scraped items found. Run without --skip-crawl first."
        exit 1
    fi
fi

# =============================================================================
# Step 2: Pick topic
# =============================================================================
log "Step 2/7: Picking report topic"
if [ -n "$TOPIC" ]; then
    warn "Using user-specified topic: $TOPIC"
    echo "{\"topic\": \"$TOPIC\"}" > "$OUTPUT_DIR/selected_topic.json"
else
    $PYTHON topic_picker.py -n 1 -o "$OUTPUT_DIR/selected_topic.json"
    TOPIC=$(python3 -c "import json; data=json.load(open('$OUTPUT_DIR/selected_topic.json')); print(data[0]['topic'])")
    log "Selected topic: $TOPIC"
fi

# =============================================================================
# Step 3: Generate report
# =============================================================================
log "Step 3/7: Generating report draft"
REPORT_MD="$OUTPUT_DIR/${TIMESTAMP}-report-draft.md"
$PYTHON generator_v2.py "$TOPIC"
# generator_v2 writes to output/ by default; find the file
GENERATED_MD=$(ls -t "$OUTPUT_DIR"/*report*.md 2>/dev/null | head -1 || echo "")
if [ -z "$GENERATED_MD" ]; then
    GENERATED_MD=$(ls -t "$OUTPUT_DIR"/*.md 2>/dev/null | head -1 || echo "")
fi

if [ -z "$GENERATED_MD" ]; then
    err "No generated report found in $OUTPUT_DIR"
    exit 1
fi
log "  Generated: $GENERATED_MD"

# =============================================================================
# Step 4: De-AI processing
# =============================================================================
log "Step 4/7: De-AI post-processing"
DEAI_MD="$OUTPUT_DIR/${TIMESTAMP}-report-deai.md"
$PYTHON deai.py "$GENERATED_MD" -o "$DEAI_MD"
log "  Output: $DEAI_MD"

# =============================================================================
# Step 5: Citation check
# =============================================================================
log "Step 5/7: Citation verification"
CITATION_OUT="$OUTPUT_DIR/${TIMESTAMP}-citations.json"
if $PYTHON citation_check.py "$DEAI_MD" -o "$CITATION_OUT" --max-unmatched 3; then
    log "  Citation check PASSED"
else
    warn "  Citation check found issues (see $CITATION_OUT)"
fi

# =============================================================================
# Step 6: Render PDF
# =============================================================================
log "Step 6/7: Rendering PDF"
REPORT_PDF="$OUTPUT_DIR/${TIMESTAMP}-report.pdf"
CHART_DATA="$OUTPUT_DIR/chart_data.json"

# Generate chart data from scraped items
$PYTHON -c "
import json, sys
data = json.load(open('$OUTPUT_DIR/scraped_items.json'))
sentiment = {'positive': 0, 'negative': 0, 'neutral': 0}
vendors = {}
for item in data:
    e = item.get('extracted', {})
    for s in e.get('sentiment', []):
        s = s.lower()
        if s in ('positive', 'improved', 'grew'): sentiment['positive'] += 1
        elif s in ('negative', 'declined', 'dropped'): sentiment['negative'] += 1
        else: sentiment['neutral'] += 1
    for v in e.get('vendor', []):
        vendors[v] = vendors.get(v, 0) + 1
json.dump({'sentiment': sentiment, 'vendor_mentions': vendors}, open('$CHART_DATA', 'w'))
" 2>/dev/null || echo '{"sentiment":{},"vendor_mentions":{}}' > "$CHART_DATA"

$PYTHON pdf_engine.py "$DEAI_MD" -o "$REPORT_PDF" --charts-data "$CHART_DATA"
log "  PDF: $REPORT_PDF"

# =============================================================================
# Step 7: Stage for publishing
# =============================================================================
log "Step 7/7: Staging for publication"

# Generate meta JSON
META_JSON="$OUTPUT_DIR/${TIMESTAMP}-meta.json"
$PYTHON -c "
import json
meta = {
    'title': '$TOPIC',
    'date': '$TIMESTAMP',
    'summary': 'Weekly deep-dive on B2B software trends. Original research from StackInsider.org.',
    'series': 'weekly-digest',
    'category': 'B2B Software',
}
json.dump(meta, open('$META_JSON', 'w'))
"

$PYTHON publisher.py --stage=A --report "$REPORT_PDF" --meta "$META_JSON"

# =============================================================================
# Summary
# =============================================================================
log ""
log "=========================================="
log "  Stage A complete!"
log "  Report PDF : $REPORT_PDF"
log "  Meta       : $META_JSON"
log "  Staged at  : static/reports/"
log ""
log "  Run Stage B to publish:"
log "    bash cron_publish.sh"
log "=========================================="