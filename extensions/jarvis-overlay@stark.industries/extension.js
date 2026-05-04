import St from 'gi://St';
import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';
import Pango from 'gi://Pango';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

const PangoWrapMode = Pango?.WrapMode?.WORD_CHAR ?? 0;

const AssistantIfaceXML = `
<node>
  <interface name="org.jarvis.Assistant">
    <method name="Ask">
        <arg type="s" direction="in" name="text"/>
        <arg type="s" direction="out" name="response"/>
    </method>
    <method name="Toggle"></method>
    <method name="Clear"></method>
    <property name="IsThinking" type="b" access="read"/>
    <signal name="Toggled"></signal>
    <signal name="NotifySignal">
        <arg type="s" name="message"/>
    </signal>
  </interface>
</node>`;

const AssistantProxy = Gio.DBusProxy.makeProxyWrapper(AssistantIfaceXML);

const JarvisOverlay = GObject.registerClass(
class JarvisOverlay extends St.BoxLayout {
    _init(extension) {
        try {
            super._init({
                style_class: 'jarvis-dock',
                vertical: false,
                visible: false,
                reactive: true,
                can_focus: true,
                track_hover: true,
            });
            this.extension = extension;
            this._history = [];
            this._thinkingMsg = null;
            this._thinkingStep = 0;
            this._thinkingTimeoutId = 0;
            this._needsScrollToBottom = false;
            this._state = 'idle';
            this._pulseStep = 0;
            this._isMini = false;
            
            // 1. MUST build UI first so references like this._entry exist even if effects fail
            this._buildUI();
            this._setupDBus();

            // 2. Safely apply Glassmorphism effect
            try {
                this._blurEffect = new Shell.BlurEffect();
                this._blurEffect.brightness = 0.75; // Darker for better legibility (Apple style)
                this._blurEffect.mode = Shell.BlurMode.BACKGROUND;
                
                let radius = 35; // Tighter, more precise blur
                if ('blur_radius' in this._blurEffect) {
                    this._blurEffect.blur_radius = radius;
                } else if ('radius' in this._blurEffect) {
                    this._blurEffect.radius = radius;
                }
                
                this.add_effect(this._blurEffect);
            } catch (e) {
                console.warn(`J.A.R.V.I.S.: Glassmorphism blur could not be applied: ${e.message}`);
            }

            // Position the dock at bottom center initially
            this._updatePosition();
            
            // Key safety: Escape to close
            this.connect('key-press-event', (actor, event) => {
                if (event.get_key_symbol() === Clutter.KEY_Escape) {
                    this.hide();
                    return Clutter.EVENT_STOP;
                }
                return Clutter.EVENT_PROPAGATE;
            });

            // Focus safety: clicking the dock grabs focus
            this.connect('button-press-event', () => {
                this._entry.grab_key_focus();
                return Clutter.EVENT_PROPAGATE;
            });

            // Handle monitor changes
            this._monitorsChangedId = Main.layoutManager.connect('monitors-changed', () => this._updatePosition());

        } catch (e) {
            console.error(`J.A.R.V.I.S. Redesign Error during _init: ${e.message}`);
        }
    }

    _updatePosition() {
        Meta.later_add(Meta.LaterType.BEFORE_REDRAW, () => {
            if (!this.visible || !this.get_stage()) return;

            let monitor = Main.layoutManager.primaryMonitor;
            if (!monitor) monitor = Main.layoutManager.get_primary_monitor();
            
            let width = 640; 
            this.set_size(width, -1);
            let [minH, natH] = this.get_preferred_height(width);
            
            this.set_position(
                monitor.x + (monitor.width - width) / 2,
                monitor.y + monitor.height - natH - 60
            );
        });
    }

    _mdToPango(text) {
        if (!text) return '';
        // Escape existing markup characters
        let escaped = text.replace(/&/g, '&amp;')
                          .replace(/</g, '&lt;')
                          .replace(/>/g, '&gt;');
        
        return escaped
            // Triple bold/italic (***text***)
            .replace(/\*\*\*(.*?)\*\*\*/g, '<b><i>$1</i></b>')
            // Bold (**text**)
            .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
            .replace(/__(.*?)__/g, '<b>$1</b>')
            // Italic (*text*)
            .replace(/\*(.*?)\*/g, '<i>$1</i>')
            .replace(/_(.*?)_/g, '<i>$1</i>')
            // Code (`text`)
            .replace(/`(.*?)`/g, '<tt>$1</tt>')
            // Horizontal rule (--- or ***)
            .replace(/^(\s*[-*_]){3,}\s*$/gm, '────────────────────────────────');
    }

    _setState(state) {
        if (this._state === state && state !== 'response') return;
        this._state = state;

        if (state === 'thinking') {
            this._startPulse();
        } else if (state === 'response') {
            this._stopPulse();
            // Sharp Gold for execution/completion
            let glow = 'border-color: rgba(255, 195, 80, 0.6); box-shadow: 0 0 15px rgba(255, 195, 80, 0.2);';
            this.set_style(glow);
            this._miniDock.set_style(glow);
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
                if (this._state === 'response') this._setState('idle');
                return GLib.SOURCE_REMOVE;
            });
        } else {
            this._stopPulse();
            this.set_style(''); 
            this._miniDock.set_style('');
        }
    }

    _startPulse() {
        if (this._pulseId) return;
        this._pulseStep = 0;
        this._pulseId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 50, () => {
            this._pulseStep += 0.1;
            let opacity = 0.2 + 0.3 * Math.abs(Math.sin(this._pulseStep));
            // Deep Indigo pulse
            let glow = `border-color: rgba(90, 70, 220, ${opacity}); box-shadow: 0 0 20px rgba(90, 70, 220, ${opacity * 0.3});`;
            this.set_style(glow);
            this._miniDock.set_style(glow);
            return GLib.SOURCE_CONTINUE;
        });
    }

    _stopPulse() {
        if (this._pulseId) {
            GLib.source_remove(this._pulseId);
            this._pulseId = 0;
        }
    }

    _safeSet(actor, prop, value) {
        try {
            if (typeof actor[prop] === 'function') {
                actor[prop](value);
            } else {
                actor[prop] = value;
            }
        } catch (e) {
            console.warn(`J.A.R.V.I.S. safeSet warning (${prop}): ${e.message}`);
        }
    }

    _buildUI() {
        try {
            // 1. Initialize core containers
            this._historyScroll = new St.ScrollView({
                style_class: 'jarvis-history-scroll',
            });
            this._safeSet(this._historyScroll, 'hscrollbar_policy', St.PolicyType.NEVER);
            this._safeSet(this._historyScroll, 'vscrollbar_policy', St.PolicyType.AUTOMATIC);
            this._safeSet(this._historyScroll, 'x_expand', true);
            this._safeSet(this._historyScroll, 'y_expand', true);

            this._historyBox = new St.BoxLayout({
                vertical: true,
                style_class: 'jarvis-history-box',
            });
            this._safeSet(this._historyBox, 'x_expand', true);
            this._safeSet(this._historyBox, 'set_spacing', 12);
            this._safeSet(this._historyBox, 'spacing', 12);

            // Pre-initialize Thinking Indicator (Hidden)
            this._thinkingMsg = new St.Label({
                text: 'Thinking',
                style_class: 'jarvis-thinking',
                x_expand: true,
                visible: false,
            });
            this._historyBox.add_child(this._thinkingMsg);

            this._historyScroll.add_child(this._historyBox);
            
            // Auto-scroll: signal-driven via notify::upper
            try {
                this._scrollAdjustment = this._historyScroll.get_vscroll_bar().get_adjustment();
                this._scrollAdjustment.connect('notify::upper', () => {
                    if (this._needsScrollToBottom) {
                        this._scrollToBottom();
                    }
                });
            } catch (e) { console.warn("J.A.R.V.I.S. Scroll init fail"); }

            // 2. The CRITICAL Entry
            this._entry = new St.Entry({
                style_class: 'jarvis-dock-entry',
                hint_text: 'Ask J.A.R.V.I.S. anything...',
                can_focus: true,
                x_expand: true,
            });
            
            this._entry.clutter_text.connect('activate', () => {
                let text = this._entry.get_text();
                if (text.trim()) this._processInput(text);
            });

            this._entry.clutter_text.connect('text-changed', () => {
                let hasText = this._entry.get_text().trim().length > 0;
                this._sendBtn.ease({
                    opacity: hasText ? 255 : 0,
                    duration: 200,
                    mode: Clutter.AnimationMode.EASE_OUT_QUAD,
                });
            });

            // 3. Buttons and Dock Area
            this._recordBtn = new St.Button({ style_class: 'jarvis-icon-button' });
            this._recordBtn.set_child(new St.Icon({ icon_name: 'audio-input-microphone-symbolic', icon_size: 16 }));

            this._sendBtn = new St.Button({ 
                style_class: 'jarvis-icon-button jarvis-send-btn',
                opacity: 0, // Hidden by default (Zero-UI)
            });
            this._sendBtn.set_child(new St.Icon({ icon_name: 'mail-send-symbolic', icon_size: 16 }));
            this._sendBtn.connect('clicked', () => {
                let text = this._entry.get_text();
                if (text.trim()) this._processInput(text);
            });

            this._btnsRight = new St.BoxLayout({ style_class: 'jarvis-dock-right' });
            this._safeSet(this._btnsRight, 'set_spacing', 4);
            this._btnsRight.add_child(this._sendBtn);
            this._btnsRight.add_child(this._recordBtn);

            // Hairline Divider
            this._divider = new St.Widget({
                style_class: 'jarvis-divider',
                height: 1,
                x_expand: true,
            });

            this._inputDock = new St.BoxLayout({ style_class: 'jarvis-input-dock' });
            this._safeSet(this._inputDock, 'set_spacing', 8);

            this._inputDock.add_child(this._entry);
            this._inputDock.add_child(this._btnsRight);

            // 4. The "Orb" (Mini Dock)
            this._miniDock = new St.Button({
                style_class: 'jarvis-mini-dock',
                visible: false,
                reactive: true,
            });
            this._miniDock.set_child(new St.Icon({
                icon_name: 'view-app-grid-symbolic',
                icon_size: 20
            }));
            
            // Drag logic for the Orb
            let dragAction = new Clutter.DragAction();
            dragAction.connect('drag-end', () => {
                let [x, y] = this._miniDock.get_position();
                this._miniX = x;
                this._miniY = y;
            });
            this._miniDock.add_action(dragAction);
            
            this._miniDock.connect('clicked', () => this._toggleMiniMode());

            // Minimize Button in main dock
            this._minimizeBtn = new St.Button({
                style_class: 'jarvis-minimize-btn',
                x_align: St.Align.END,
            });
            this._minimizeBtn.set_child(new St.Icon({
                icon_name: 'window-minimize-symbolic',
                icon_size: 14
            }));
            this._minimizeBtn.connect('clicked', () => this._toggleMiniMode());

            // Assembly
            this.add_child(this._minimizeBtn); // Top-right minimize
            this.add_child(this._historyScroll);
            this.add_child(this._divider);
            this.add_child(this._inputDock);
            
            // Add miniDock to stage (top level)
            Main.layoutManager.addTopChrome(this._miniDock);

        } catch (e) {
            console.error(`J.A.R.V.I.S. Redesign Error during _buildUI: ${e.message}`);
        }
    }

    _setupDBus() {
        this._proxy = new AssistantProxy(
            Gio.DBus.session,
            'org.jarvis.Assistant',
            '/org/jarvis/Assistant'
        );
        
        // Listen for proactive messages
        this._proxy.connectSignal('NotifySignal', (proxy, senderName, [message]) => {
            if (message) {
                this._addMessage('jarvis', message);
                
                // Instead of the full dock, surface the Orb as an ambient indicator
                if (!this.visible && !this._miniDock.visible) {
                    this._isMini = true;
                    this._miniDock.visible = true;
                    this._miniDock.opacity = 0;
                    
                    let monitor = Main.layoutManager.primaryMonitor;
                    if (!monitor) monitor = Main.layoutManager.get_primary_monitor();
                    
                    // Position it at the bottom center
                    this._miniDock.set_position(
                        monitor.x + (monitor.width / 2) - 25,
                        monitor.y + monitor.height - 100
                    );
                    this._miniDock.ease({
                        opacity: 255,
                        duration: 400,
                        mode: Clutter.AnimationMode.EASE_OUT_QUAD
                    });
                }
                
                // Pulse to get attention
                this._setState('thinking'); 
            }
        });
    }

    _processInput(text) {
        this._addMessage('user', text);
        this._entry.set_text('');
        this._setState('thinking');
        this._showThinking();

        this._proxy.get_connection().call(
            this._proxy.get_name(),
            this._proxy.get_object_path(),
            'org.jarvis.Assistant',
            'Ask',
            new GLib.Variant('(s)', [text]),
            null,
            Gio.DBusCallFlags.NONE,
            300000,
            null,
            (connection, result) => {
                this._hideThinking();
                try {
                    let reply = connection.call_finish(result);
                    let [response] = reply.recursiveUnpack();
                    if (response) {
                        this._setState('response');
                        this._addMessage('jarvis', response);
                    } else {
                        this._setState('idle');
                    }
                } catch (e) {
                    this._setState('idle');
                    this._addMessage('jarvis', `System Error: ${e.message}`);
                }
            }
        );
    }

    _showThinking() {
        this._thinkingMsg.visible = true;
        this._updatePosition();
        
        // Start dot animation
        if (this._thinkingTimeoutId) return;
        
        this._thinkingStep = 0;
        this._thinkingTimeoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => {
            if (!this._thinkingMsg.visible) {
                 this._thinkingTimeoutId = 0;
                 return GLib.SOURCE_REMOVE;
            }
            this._thinkingStep = (this._thinkingStep + 1) % 4;
            let dots = '.'.repeat(this._thinkingStep);
            this._thinkingMsg.set_text(`Thinking${dots}`);
            return GLib.SOURCE_CONTINUE;
        });
    }

    _scrollToBottom() {
        if (!this._scrollAdjustment) return;

        let upper = this._scrollAdjustment.get_upper();
        let pageSize = this._scrollAdjustment.get_page_size();
        let endValue = upper - pageSize;

        if (endValue > 0) {
            this._scrollAdjustment.ease({
                value: endValue,
                duration: 350,
                mode: Clutter.AnimationMode.EASE_OUT_CUBIC,
            });
        }
    }

    _hideThinking() {
        this._thinkingMsg.visible = false;
        if (this._thinkingTimeoutId) {
            GLib.source_remove(this._thinkingTimeoutId);
            this._thinkingTimeoutId = 0;
        }
        // Move thinking indicator to the end of the history box for next time
        this._historyBox.remove_child(this._thinkingMsg);
        this._historyBox.add_child(this._thinkingMsg);
        
        this._updatePosition();
    }

    _addMessage(sender, text) {
        let msgBox = new St.BoxLayout({
            style_class: `jarvis-msg-bubble jarvis-msg-${sender}`,
            vertical: true,
            x_expand: true,
        });
        
        let label = new St.Label({
            style_class: 'jarvis-msg-text',
            x_expand: true,
        });
        
        // Markdown rendering with Pango Markup
        label.clutter_text.use_markup = true;
        label.clutter_text.selectable = true; // Allow text selection
        
        // Set selection colors in JS to match "Invisible Intelligence" palette
        try {
            let selectionBg = new Clutter.Color({ red: 120, green: 160, blue: 255, alpha: 60 });
            label.clutter_text.selection_color = selectionBg;
        } catch (e) {}

        label.clutter_text.set_markup(this._mdToPango(text));
        
        // Anti-truncation logic
        label.clutter_text.line_wrap = true;
        label.clutter_text.line_wrap_mode = Pango.WrapMode.WORD_CHAR;
        label.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
        
        msgBox.add_child(label);
        
        // Add before the thinking indicator
        let pos = this._historyBox.get_children().indexOf(this._thinkingMsg);
        this._historyBox.insert_child_at_index(msgBox, pos);
        
        this._needsScrollToBottom = true;
        this._updatePosition();
        this._scrollToBottom();
    }

    show() {
        this.visible = true;
        this._updatePosition();
        this._entry.grab_key_focus();
        
        // Surfacing Animation: emergence from the OS
        this.opacity = 0;
        this.scale_y = 0.96;
        this.translation_y = 20; 

        this.ease({
            opacity: 255,
            scale_y: 1.0,
            translation_y: 0,
            duration: 400,
            mode: Clutter.AnimationMode.EASE_OUT_CUBIC,
        });
    }

    hide() {
        this._setState('idle');
        this.ease({
            opacity: 0,
            scale_y: 0.98,
            translation_y: 10,
            duration: 200,
            mode: Clutter.AnimationMode.EASE_IN_QUAD,
            onComplete: () => {
                this.visible = false;
            }
        });
    }

    _toggleMiniMode() {
        this._isMini = !this._isMini;
        
        if (this._isMini) {
            // Shrink main dock into the Orb
            this.ease({
                opacity: 0,
                scale_x: 0.1,
                scale_y: 0.1,
                duration: 300,
                mode: Clutter.AnimationMode.EASE_IN_QUAD,
                onComplete: () => {
                    this.visible = false;
                    this._miniDock.visible = true;
                    this._miniDock.opacity = 0;
                    this._miniDock.set_position(
                        this.x + this.width / 2 - 25,
                        this.y + this.height - 25
                    );
                    this._miniDock.ease({
                        opacity: 255,
                        duration: 200,
                        mode: Clutter.AnimationMode.EASE_OUT_QUAD,
                    });
                }
            });
        } else {
            // Expand Orb back into main dock
            this._miniDock.ease({
                opacity: 0,
                duration: 200,
                mode: Clutter.AnimationMode.EASE_IN_QUAD,
                onComplete: () => {
                    this._miniDock.visible = false;
                    this.visible = true;
                    this.opacity = 0;
                    this.scale_x = 0.1;
                    this.scale_y = 0.1;
                    this.ease({
                        opacity: 255,
                        scale_x: 1.0,
                        scale_y: 1.0,
                        duration: 350,
                        mode: Clutter.AnimationMode.EASE_OUT_CUBIC,
                    });
                    this._entry.grab_key_focus();
                }
            });
        }
    }

    toggle() {
        if (this._isMini) {
            this._toggleMiniMode();
        } else {
            if (this.visible) this.hide();
            else this.show();
        }
    }

    destroy() {
        if (this._monitorsChangedId) {
            Main.layoutManager.disconnect(this._monitorsChangedId);
        }
        super.destroy();
    }
});

export default class JarvisExtension extends Extension {
    _setupHotkey() {
        this._removeHotkey();
        const shortcut = this._settings.get_strv('jarvis-overlay-shortcut');
        
        Main.wm.addKeybinding(
            'jarvis-overlay-shortcut',
            this._settings,
            Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.ALL,
            () => this._toggleJarvis()
        );
    }

    async _toggleJarvis() {
        try {
            if (!this._proxy) {
                this._proxy = new AssistantProxy(
                    Gio.DBus.session,
                    'org.jarvis.Assistant',
                    '/org/jarvis/Assistant'
                );
            }
            // Use the remote toggle to ensure daemon awareness
            await this._proxy.ToggleRemote();
        } catch (e) {
            // Fallback to local toggle if daemon is unreachable
            this._toggleOverlay();
        }
    }

    _removeHotkey() {
        Main.wm.removeKeybinding('jarvis-overlay-shortcut');
    }

    enable() {
        this._overlay = null;
        this._settings = this.getSettings('org.gnome.shell.extensions.jarvis-overlay');
        
        this._proxy = new AssistantProxy(
            Gio.DBus.session,
            'org.jarvis.Assistant',
            '/org/jarvis/Assistant'
        );

        // Listen for the Toggled signal directly from the proxy
        this._proxy.connectSignal('Toggled', () => {
            Main.notify('J.A.R.V.I.S.', 'Signal Received: Toggling Overlay');
            this._toggleOverlay();
        });

        this._setupHotkey();
        
        this._settings.connect('changed::jarvis-overlay-shortcut', () => {
            this._setupHotkey();
        });

        console.log('J.A.R.V.I.S. Assistant enabled.');
    }

    disable() {
        this._removeHotkey();

        if (this._signalId) {
            Gio.DBus.session.signal_unsubscribe(this._signalId);
            this._signalId = null;
        }
        if (this._overlay) {
            this._overlay.destroy();
            this._overlay = null;
        }
        console.log('J.A.R.V.I.S. Assistant disabled.');
    }

    _toggleOverlay() {
        if (this._isToggling) return;
        this._isToggling = true;
        
        try {
            if (!this._overlay) {
                this._overlay = new JarvisOverlay(this);
                Main.layoutManager.addTopChrome(this._overlay);
            }
            this._overlay.toggle();
        } catch (e) {
            console.error(`[Jarvis] Toggle error: ${e.message}`);
        } finally {
            this._isToggling = false;
        }
    }
}
