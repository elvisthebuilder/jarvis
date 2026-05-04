import Gio from 'gi://Gio';
import Adw from 'gi://Adw';
import Gtk from 'gi://Gtk';
import Gdk from 'gi://Gdk';
import GLib from 'gi://GLib';
import { ExtensionPreferences } from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class JarvisPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const page = new Adw.PreferencesPage();
        window.add(page);

        // --- General Settings ---
        const group = new Adw.PreferencesGroup({
            title: 'General Settings',
            description: 'Configure your J.A.R.V.I.S. experience',
        });
        page.add(group);

        // --- Shortcut Setting ---
        const shortcutGroup = new Adw.PreferencesGroup({
            title: 'Keyboard Shortcut',
            description: 'The key combination used to toggle the Jarvis overlay',
        });
        page.add(shortcutGroup);

        const settings = this.getSettings();
        const shortcutRow = new Adw.ActionRow({
            title: 'Toggle Jarvis',
            subtitle: 'Click to record a new shortcut',
        });
        shortcutGroup.add(shortcutRow);

        const shortcutLabel = new Gtk.ShortcutLabel({
            accelerator: settings.get_strv('jarvis-overlay-shortcut')[0] || '',
            valign: Gtk.Align.CENTER,
        });
        shortcutRow.add_suffix(shortcutLabel);

        const editBtn = new Gtk.Button({
            icon_name: 'document-edit-symbolic',
            valign: Gtk.Align.CENTER,
            css_classes: ['flat'],
        });
        shortcutRow.add_suffix(editBtn);

        editBtn.connect('clicked', () => {
            editBtn.sensitive = false;
            shortcutRow.subtitle = 'Press any key combination... (Esc to cancel)';
            
            const controller = new Gtk.EventControllerKey();
            window.add_controller(controller);

            const signalId = controller.connect('key-pressed', (ctrl, keyval, keycode, state) => {
                const mask = state & Gtk.accelerator_get_default_mod_mask();
                const name = Gtk.accelerator_name(keyval, mask);

                if (keyval === Gdk.KEY_Escape) {
                    // Cancel
                } else if (name) {
                    settings.set_strv('jarvis-overlay-shortcut', [name]);
                    shortcutLabel.accelerator = name;
                }

                shortcutRow.subtitle = 'Click to record a new shortcut';
                editBtn.sensitive = true;
                window.remove_controller(controller);
                return Gdk.EVENT_STOP;
            });
        });

        // --- Debug Logs ---
        const logGroup = new Adw.PreferencesGroup({
            title: 'Debugging Tools',
            description: 'View and share GNOME Shell logs related to the Jarvis extension',
        });
        page.add(logGroup);

        const logRow = new Adw.ExpanderRow({
            title: 'Extension System Logs',
        });
        logGroup.add(logRow);

        const scrolledWindow = new Gtk.ScrolledWindow({
            min_content_height: 300,
            propagate_natural_height: true,
        });
        
        const textView = new Gtk.TextView({
            editable: false,
            cursor_visible: false,
            monospace: true,
            margin_start: 12,
            margin_end: 12,
            margin_top: 12,
            margin_bottom: 12,
        });
        scrolledWindow.set_child(textView);

        const actionsBox = new Gtk.Box({
            orientation: Gtk.Orientation.HORIZONTAL,
            spacing: 12,
            margin_top: 12,
            margin_bottom: 12,
            margin_start: 12,
            margin_end: 12,
        });

        const refreshBtn = new Gtk.Button({ label: 'Refresh Logs' });
        const copyBtn = new Gtk.Button({ label: 'Copy to Clipboard' });
        actionsBox.append(refreshBtn);
        actionsBox.append(copyBtn);

        const contentBox = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL
        });
        contentBox.append(actionsBox);
        contentBox.append(scrolledWindow);

        logRow.add_row(contentBox);

        const refreshLogs = () => {
            try {
                let combinedLogs = "=== EXTENSION LOGS (journalctl) ===\n";
                const [, stdout, stderr, status] = GLib.spawn_command_line_sync('journalctl -n 200 /usr/bin/gnome-shell');
                if (status === 0) {
                    const text = new TextDecoder('utf-8').decode(stdout);
                    combinedLogs += text.split('\n')
                                         .filter(line => line.toLowerCase().includes('jarvis'))
                                         .slice(-50)
                                         .join('\n');
                }

                combinedLogs += "\n\n=== DAEMON LOGS (local file) ===\n";
                const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
                const logPath = `${GLib.get_home_dir()}/.local/share/jarvis/logs/jarvis_${dateStr}.log`;
                
                if (GLib.file_test(logPath, GLib.FileTest.EXISTS)) {
                    const [ok, contents] = GLib.file_get_contents(logPath);
                    if (ok) {
                        const daemonText = new TextDecoder('utf-8').decode(contents);
                        combinedLogs += daemonText.split('\n').slice(-100).join('\n');
                    }
                } else {
                    combinedLogs += `No daemon log found at: ${logPath}`;
                }

                textView.get_buffer().set_text(combinedLogs, -1);
            } catch (e) {
                console.error(e);
                textView.get_buffer().set_text(`Failed to get logs: ${e.message}`, -1);
            }
        };

        refreshBtn.connect('clicked', refreshLogs);
        
        copyBtn.connect('clicked', () => {
            const buffer = textView.get_buffer();
            const text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), false);
            textView.get_clipboard().set_text(text);
        });

        // Load logs initially when setting page opens
        refreshLogs();
    }
}
