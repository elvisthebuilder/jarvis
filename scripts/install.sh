#!/usr/bin/env bash
# ──────────────────────────────────────────────────────
# J.A.R.V.I.S. One-Click Production Installer
# ──────────────────────────────────────────────────────
set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

TARGET_DIR="$HOME/.local/share/jarvis"
REPO_URL="https://github.com/elvisthebuilder/jarvis.git"

echo -e "${CYAN}${BOLD}"
echo "     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗"
echo "     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝"
echo "     ██║███████║██████╔╝██║   ██║██║███████╗"
echo "██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║"
echo "╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║"
echo " ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝"
echo -e "${NC}"
echo -e "${CYAN}  Production Rollout — J.A.R.V.I.S. 2.0${NC}"
echo ""

# ── Step 1: Clone Repository ─────────────────────────

if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${YELLOW}[1/6]${NC} Initializing core repository..."
    git clone "$REPO_URL" "$TARGET_DIR" -q
    echo -e "${GREEN}  ✓ Repository initialized at $TARGET_DIR${NC}"
else
    echo -e "${GREEN}  ✓ Repository already exists at $TARGET_DIR${NC}"
fi

cd "$TARGET_DIR"

# ── Step 2: System Dependencies ──────────────────────

echo -e "${YELLOW}[2/6]${NC} Installing system dependencies..."

sudo apt update -qq
sudo apt install -y -qq \
    python3-venv \
    python3-dev \
    wl-clipboard \
    playerctl \
    wmctrl \
    libnotify-bin \
    portaudio19-dev \
    ffmpeg \
    git \
    2>/dev/null

echo -e "${GREEN}  ✓ System dependencies installed${NC}"

# ── Step 3: Python Environment ───────────────────────

echo -e "${YELLOW}[3/6]${NC} Synchronizing Python environment..."

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip -q
pip install -e "." -q

echo -e "${GREEN}  ✓ Neural environment synced${NC}"

# ── Step 4: GNOME Extension ──────────────────────────

echo -e "${YELLOW}[4/6]${NC} Linking Neural Overlay (GNOME Extension)..."
bash scripts/install-extension.sh > /dev/null
echo -e "${GREEN}  ✓ UI Overlay linked${NC}"

# ── Step 5: Background Service ───────────────────────

echo -e "${YELLOW}[5/6]${NC} Registering background service..."

mkdir -p "$HOME/.config/systemd/user"
SERVICE_FILE="$HOME/.config/systemd/user/jarvis.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=J.A.R.V.I.S. — Intelligent Desktop Assistant
After=graphical-session.target

[Service]
Type=simple
ExecStart=${TARGET_DIR}/.venv/bin/python -m jarvis.daemon --daemon
WorkingDirectory=${TARGET_DIR}
EnvironmentFile=${TARGET_DIR}/.env
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
echo -e "${GREEN}  ✓ Background service registered${NC}"

# ── Step 6: Launch Onboarding ─────────────────────────

echo -e "${YELLOW}[6/6]${NC} Initiating Neural Handshake..."
echo ""

# We run the daemon in CLI mode, which will trigger onboarding because .env hasn't been set up
.venv/bin/python -m jarvis.daemon

echo ""
echo -e "${GREEN}${BOLD}  ✦ Production installation complete, Sir!${NC}"
echo -e "  You can now enable the background service with:"
echo -e "    ${CYAN}systemctl --user enable --now jarvis${NC}"
echo ""
