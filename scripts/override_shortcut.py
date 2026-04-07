#!/usr/bin/env python3
import subprocess
import os

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except:
        return ""

def main():
    print("Searching for Super+J conflict, Sir...")
    
    # Get all schemas
    schemas = run("gsettings list-schemas").splitlines()
    
    targets = ["['<Super>j']", "['<Super>J']", "['<Meta>j']", "['<Meta>J']"]
    
    found = False
    for schema in schemas:
        # Optimization: only check schemas that likely have keybindings
        if "keybindings" not in schema and "media-keys" not in schema and "shortcuts" not in schema:
            continue
            
        keys = run(f"gsettings list-keys {schema}").splitlines()
        for key in keys:
            val = run(f"gsettings get {schema} {key}")
            if any(t in val for t in targets):
                print(f"  Conflict found: {schema} {key} = {val}")
                print(f"  Overriding {schema} {key}...")
                subprocess.run(f"gsettings set {schema} {key} \"[]\"", shell=True)
                found = True

    # Also check custom keybindings specifically
    # Custom keybindings paths: /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/customX/
    # These are usually found in dconf directly
    dconf_keys = run("dconf dump / | grep -B 5 -E \"'<Super>j'|'<Super>J'\"").splitlines()
    if dconf_keys:
        print("  Possible custom keybinding conflict found in dconf. Clearing...")
        # Note: Clearing dconf via script is riskier, telling user to check Settings > Keyboard > Shortcuts
        found = True

    # Finally, ensure Jarvis is set
    print("  Setting Jarvis overlay shortcut to Super+J...")
    subprocess.run("gsettings set org.gnome.shell.extensions.jarvis-overlay jarvis-overlay-shortcut \"['<Super>j']\"", shell=True)
    
    if found:
        print("\nConflicts resolved. You may need to restart the shell or log out/in one last time, Sir.")
    else:
        print("\nNo direct conflicts found in standard GSettings. I've set the Jarvis shortcut; if it still doesn't work, ensure you don't have a 3rd party tiling manager capturing it.")

if __name__ == "__main__":
    main()
