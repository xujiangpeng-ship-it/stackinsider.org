#!/bin/bash
# Oracle VPS deployment script for StackInsider Reports Pipeline
# Usage: bash deploy.sh
# Tested: Oracle Linux 8/9, Ubuntu 22.04, 1GB RAM

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[x]${NC} $1"; exit 1; }

echo "============================================"
echo " StackInsider Reports Pipeline Deploy"
echo "============================================"
echo ""

# --- Check OS ---
if [ -f /etc/os-release ]; then
    . /etc/os-release
    log "Detected: $NAME"
else
    warn "Cannot detect OS, assuming generic Linux"
fi

# --- Install system dependencies ---
log "Installing system dependencies..."

if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3 python3-pip python3-venv git curl \
        libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
        libffi-dev libcairo2 libcairo2-dev 2>/dev/null || true
elif command -v dnf &>/dev/null; then
    sudo dnf install -y -q python3 python3-pip git curl \
        pango cairo cairo-gobject gdk-pixbuf2 \
        libffi-devel 2>/dev/null || true
elif command -v yum &>/dev/null; then
    sudo yum install -y -q python3 python3-pip git curl \
        pango cairo cairo-gobject gdk-pixbuf2 \
        libffi-devel 2>/dev/null || true
fi

# --- Create project directory ---
PROJECT_DIR="$HOME/stackinsider-pipeline"
log "Creating project directory: $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"

# --- Clone if not exists, else pull ---
if [ -d "$PROJECT_DIR/.git" ]; then
    log "Repository exists, pulling latest..."
    cd "$PROJECT_DIR"
    git reset --hard
    git pull origin main
else
    log "Cloning repository..."
    git clone --depth 1 --filter=blob:none --sparse \
        https://github.com/xujiangpeng-ship-it/stackinsider.org.git "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    git sparse-checkout set reports-pipeline
fi

cd "$PROJECT_DIR/reports-pipeline"

# --- Setup Python virtualenv ---
log "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q 2>&1 | tail -1

# --- Verify critical dependencies ---
log "Verifying dependencies..."
python -c "import scrapling; print('  scrapling', scrapling.__version__)" || warn "scrapling import failed"
python -c "import weasyprint; print('  weasyprint OK')" || warn "weasyprint import failed (PDF will be skipped)"
python -c "import matplotlib; print('  matplotlib', matplotlib.__version__)" || warn "matplotlib import failed (charts disabled)"
python -c "import requests; print('  requests OK')" || warn "requests import failed"

deactivate

# --- Environment variables ---
log "Checking environment variables..."
ENV_FILE="$PROJECT_DIR/reports-pipeline/.env"

if [ ! -f "$ENV_FILE" ]; then
    warn ".env file not found. Creating template..."
    cat > "$ENV_FILE" << 'EOF'
# StackInsider Reports Pipeline — Environment Variables
# Copy from 1Password or password manager, fill in real values

# Mistral AI API Key (for generator_v2.py, topic_picker.py)
MISTRAL_API_KEY=your_mistral_api_key_here

# GitHub Token (for publisher.py to push and trigger Cloudflare Pages deploy)
# Needs repo scope + workflow scope
GITHUB_TOKEN=your_github_token_here

# Optional: path to stackinsider.org local clone for publisher.py
STACKINSIDER_REPO=$HOME/stackinsider-pipeline
EOF
    warn ".env template created at $ENV_FILE"
    warn "Please edit $ENV_FILE and add your real API keys before running the pipeline."
else
    log ".env file exists"
fi

# --- Setup cron ---
log "Setting up cron jobs..."
CRON_TMP=$(mktemp)

# Stage A: Weekly report generation — Saturday 08:00 UTC (16:00 Beijing)
echo "0 8 * * 6 cd $PROJECT_DIR/reports-pipeline && bash run.sh >> $PROJECT_DIR/logs/stage-a.log 2>&1" >> "$CRON_TMP"

# Stage B: Daily publish check — 09:30, 14:45, 20:15 UTC+8 (Beijing time)
echo "30 1 * * * cd $PROJECT_DIR/reports-pipeline && bash cron_publish.sh >> $PROJECT_DIR/logs/stage-b.log 2>&1" >> "$CRON_TMP"
echo "45 6 * * * cd $PROJECT_DIR/reports-pipeline && bash cron_publish.sh >> $PROJECT_DIR/logs/stage-b.log 2>&1" >> "$CRON_TMP"
echo "15 12 * * * cd $PROJECT_DIR/reports-pipeline && bash cron_publish.sh >> $PROJECT_DIR/logs/stage-b.log 2>&1" >> "$CRON_TMP"

crontab "$CRON_TMP"
rm -f "$CRON_TMP"

# Create log directory
mkdir -p "$PROJECT_DIR/logs"

log "Cron jobs installed:"
crontab -l | grep stackinsider

# --- Final summary ---
echo ""
echo "============================================"
echo " Deployment Complete"
echo "============================================"
echo ""
echo " Project:     $PROJECT_DIR/reports-pipeline"
echo " Python:      $(python3 --version)"
echo " Cron:        $(crontab -l | grep -c stackinsider) jobs active"
echo ""
echo " Next steps:"
echo "  1. Edit .env:  vi $ENV_FILE"
echo "  2. Test crawl: cd $PROJECT_DIR/reports-pipeline && source venv/bin/activate && python crawler.py --max-sources 3"
echo "  3. Manual run: bash $PROJECT_DIR/reports-pipeline/run.sh"
echo "  4. View logs:  tail -f $PROJECT_DIR/logs/stage-a.log"
echo ""
echo " Cron schedule:"
echo "  Stage A (generate): Sat 08:00 UTC"
echo "  Stage B (publish):  Daily at 09:30, 14:45, 20:15 Beijing time"
echo "============================================"
