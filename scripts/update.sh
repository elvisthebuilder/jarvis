#!/usr/bin/env bash
# ──────────────────────────────────────────────────────
# J.A.R.V.I.S. Production Updater
# ──────────────────────────────────────────────────────
set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
BOLD='\033[1m'

TARGET_DIR="$HOME/.local/share/jarvis"

if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${RED}Error: J.A.R.V.I.S. is not installed in $TARGET_DIR${NC}"
    exit 1
fi

cd "$TARGET_DIR"

echo -e "${CYAN}${BOLD}Initiating Production Update...${NC}"

# 1. Pull latest code
echo -e "${YELLOW}  󰚰 Synchronizing with core repository...${NC}"
git pull origin main -q

# 2. Update environment
echo -e "${YELLOW}  󰏗 Refreshing neural environment...${NC}"
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e "." -q

# 3. Update Extension
echo -e "${YELLOW}  󰔦 Synchronizing UI Overlay...${NC}"
bash scripts/install-extension.sh > /dev/null

# 4. Refresh & Restart services
echo -e "${YELLOW}  󰓦 Synchronizing background services...${NC}"
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
EnvironmentFile=-${TARGET_DIR}/.env
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user restart jarvis

echo ""
echo -e "${GREEN}${BOLD}  ✦ Update synchronized successfully, Sir!${NC}"
echo ""
