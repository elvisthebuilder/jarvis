#!/usr/bin/env bash
# ──────────────────────────────────────────────────────
# J.A.R.V.I.S. Production Uninstaller
# ──────────────────────────────────────────────────────
set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

UUID="jarvis-overlay@stark.industries"
TARGET_DIR="$HOME/.local/share/jarvis"

echo -e "${RED}${BOLD}Initiating J.A.R.V.I.S. Decommissioning Protocol...${NC}"
echo ""

# 1. Stop and Disable Service
echo -e "${YELLOW}[1/4]${NC} Stopping background services..."
systemctl --user stop jarvis 2>/dev/null || true
systemctl --user disable jarvis 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/jarvis.service"
systemctl --user daemon-reload
echo -e "${GREEN}  ✓ Services decommissioned.${NC}"

# 2. Remove GNOME Extension and Shortcut
echo -e "${YELLOW}[2/4]${NC} Removing UI Overlay and Shortcuts..."
rm -rf "$HOME/.local/share/gnome-shell/extensions/$UUID"

# Remove from gsettings custom-keybindings list
CURRENT_BINDINGS=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings)
JARVIS_BINDING="'/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/jarvis/'"

if [[ "$CURRENT_BINDINGS" == *"$JARVIS_BINDING"* ]]; then
    # Use sed to remove the binding and clean up any double commas or leading/trailing commas
    NEW_BINDINGS=$(echo "$CURRENT_BINDINGS" | sed "s/ $JARVIS_BINDING//g; s/$JARVIS_BINDING //g; s/$JARVIS_BINDING//g; s/\[,/\[/g; s/, ,/,/g; s/,,/,/g; s/,]/]/g")
    gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$NEW_BINDINGS"
fi
# Reset the specific path
gsettings reset-recursively org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/jarvis/

echo -e "${GREEN}  ✓ UI components removed.${NC}"

# 3. Clean up Filesystem
echo -e "${YELLOW}[3/4]${NC} Removing production binaries..."
# We preserve the directory for the db question
find "$TARGET_DIR" -maxdepth 1 ! -name "data" -exec rm -rf {} + 2>/dev/null || true
echo -e "${GREEN}  ✓ System files purged.${NC}"

# 4. Optional Memory Deletion
echo -e "${YELLOW}[4/4]${NC} Final Memory Protocol..."
echo -en "${CYAN}Should J.A.R.V.I.S. purge his long-term memory (jarvis.db)? [y/N]: ${NC}"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    rm -rf "$TARGET_DIR/data"
    echo -e "${RED}  ✓ Long-term memory purged.${NC}"
else
    echo -e "${GREEN}  ✓ Memory preserved at $TARGET_DIR/data${NC}"
fi

# Finally remove the target dir if empty
rmdir "$TARGET_DIR" 2>/dev/null || true

echo ""
echo -e "${GREEN}${BOLD}  ✦ Decommissioning complete, Sir. J.A.R.V.I.S. is offline.${NC}"
echo ""
