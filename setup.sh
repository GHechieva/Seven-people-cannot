#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# TripBot — one-click local setup
# Usage: bash setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✔]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✘]${NC} $1"; exit 1; }

echo ""
echo "  ✈️  TripBot Setup"
echo "  ────────────────────────────────────"
echo ""

# ── 1. Check Python 3.12 ────────────────────────────────────────────────────
if command -v python3.12 &>/dev/null; then
    PYTHON=python3.12
elif command -v python3 &>/dev/null; then
    VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [[ "$VER" < "3.10" ]]; then
        error "Python 3.10+ required, found $VER"
    fi
    PYTHON=python3
else
    error "Python 3 not found. Install from https://python.org"
fi
info "Python: $($PYTHON --version)"

# ── 2. Create .env from example ─────────────────────────────────────────────
if [ ! -f .env ]; then
    cp .env.example .env
    warn ".env created from .env.example"
    echo ""
    echo -e "  ${YELLOW}➤ Open .env and paste your BOT_TOKEN before continuing.${NC}"
    echo "    Get it from @BotFather on Telegram."
    echo ""
    read -p "  Press ENTER when you've added the token to .env... " _
else
    info ".env already exists, skipping"
fi

# ── 3. Validate BOT_TOKEN ────────────────────────────────────────────────────
BOT_TOKEN=$(grep '^BOT_TOKEN=' .env | cut -d= -f2 | tr -d ' ')
if [[ -z "$BOT_TOKEN" || "$BOT_TOKEN" == "123456789:ABC"* ]]; then
    error "BOT_TOKEN in .env is still the placeholder. Add your real token."
fi
info "BOT_TOKEN looks good"

# ── 4. Virtual environment ───────────────────────────────────────────────────
if [ ! -d .venv ]; then
    info "Creating virtual environment..."
    $PYTHON -m venv .venv
fi
source .venv/bin/activate
info "Virtual environment active"

# ── 5. Install dependencies ──────────────────────────────────────────────────
info "Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
info "Dependencies installed"

# ── 6. Create data dir ───────────────────────────────────────────────────────
mkdir -p data
info "Data directory ready"

# ── 7. Done ──────────────────────────────────────────────────────────────────
echo ""
echo "  ────────────────────────────────────"
echo -e "  ${GREEN}✅  Setup complete!${NC}"
echo ""
echo "  To start the bot:"
echo "    source .venv/bin/activate"
echo "    python main.py"
echo ""
echo "  Or with Docker:"
echo "    docker compose up --build"
echo ""
