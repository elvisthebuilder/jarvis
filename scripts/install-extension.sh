#!/bin/bash
# Install Jarvis Assistant GNOME Shell Extension

UUID="jarvis-overlay@stark.industries"
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/$UUID"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Installing $UUID to $EXT_DIR..."

# Create directory
mkdir -p "$EXT_DIR"

# Copy files
cp -r "$PROJECT_ROOT/extensions/$UUID/"* "$EXT_DIR/"

# Compile schemas
glib-compile-schemas "$EXT_DIR/schemas/"

echo "Registering Jarvis Summon in GNOME Keyboard Settings..."
# Get current custom keybindings
CURRENT_BINDINGS=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings)
JARVIS_BINDING="'/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/jarvis/'"

# If jarvis isn't in bindings, append it
if [[ "$CURRENT_BINDINGS" != *"$JARVIS_BINDING"* ]]; then
    if [ "$CURRENT_BINDINGS" = "@as []" ] || [ "$CURRENT_BINDINGS" = "[]" ]; then
        NEW_BINDINGS="[$JARVIS_BINDING]"
    else
        NEW_BINDINGS=$(echo "$CURRENT_BINDINGS" | sed "s/]$/, $JARVIS_BINDING]/")
    fi
    gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$NEW_BINDINGS"
fi

# Configure the Jarvis shortcut entry
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/jarvis/ name "Jarvis Assistant"
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/jarvis/ command "$PROJECT_ROOT/.venv/bin/python -m jarvis.daemon --toggle"

# Only set default binding if it's currently empty (don't overwrite user's custom choice on upgrade)
CURRENT_KEY=$(gsettings get org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/jarvis/ binding)
if [ "$CURRENT_KEY" = "''" ]; then
    gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/jarvis/ binding "<Super><Shift>j"
fi

echo "--------------------------------------------------------"
echo "Installation complete, Sir."
echo ""
echo "1. Log out and log back in (strongly recommended for Wayland)."
echo "2. Open 'Extensions' or 'Extension Manager' app."
echo "3. Enable 'J.A.R.V.I.S. Assistant'."
echo "4. Press Super+J to summon me."
echo "--------------------------------------------------------"
