import Gio from 'gi://Gio';
import Adw from 'gi://Adw';
import Gtk from 'gi://Gtk';
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

        const row = new Adw.ActionRow({
            title: 'Summon Shortcut',
            subtitle: 'Configure globally in System Settings -> Keyboard -> Custom Shortcuts',
        });
        
        const button = new Gtk.Button({
            label: 'Open Settings',
            valign: Gtk.Align.CENTER,
        });

        button.connect('clicked', () => {
            try {
                Gio.AppInfo.create_from_commandline(
                    'gnome-control-center keyboard',
                    null,
                    Gio.AppInfoCreateFlags.NONE
                ).launch([], null);
            } catch (e) {
                console.error('Failed to launch settings:', e);
            }
        });

        row.add_suffix(button);
        row.activatable_widget = button;
        group.add(row);

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
