import St from 'gi://St';
import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';
import Pango from 'gi://Pango';
import GLib from 'gi://GLib';
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
                vertical: true,
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
            
            // 1. MUST build UI first so references like this._entry exist even if effects fail
            this._buildUI();
            this._setupDBus();

            // 2. Safely apply Glassmorphism effect
            try {
                this._blurEffect = new Shell.BlurEffect();
                this._blurEffect.brightness = 0.6;
                this._blurEffect.mode = Shell.BlurMode.BACKGROUND;
                
                // Handle different shell versions for the blur radius property
                if ('blur_radius' in this._blurEffect) {
                    this._blurEffect.blur_radius = 40;
                } else if ('radius' in this._blurEffect) {
                    this._blurEffect.radius = 40;
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
        // Use a tiny delay to ensure children have calculated their preferred height
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 10, () => {
            if (!this.visible) return GLib.SOURCE_REMOVE;
            
            let monitor = Main.layoutManager.primaryMonitor;
            let width = 640; 
            let [minH, height] = this.get_preferred_height(width);
            
            this.set_size(width, -1);
            this.set_position(
                monitor.x + (monitor.width - width) / 2,
                monitor.y + monitor.height - height - 40
            );
            return GLib.SOURCE_REMOVE;
        });
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
            
            // Auto-scroll logic
            try {
                let scrollbar = this._historyScroll.get_vscroll_bar();
                scrollbar.connect('changed', () => {
                    let adjustment = scrollbar.get_adjustment();
                    adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size());
                });
            } catch (e) { console.warn("J.A.R.V.I.S. Scroll logic fail"); }

            // 2. The CRITICAL Entry - define it early!
            this._entry = new St.Entry({
                style_class: 'jarvis-dock-entry',
            });
            this._safeSet(this._entry, 'hint_text', 'Ask J.A.R.V.I.S. anything...');
            this._safeSet(this._entry, 'can_focus', true);
            this._safeSet(this._entry, 'x_expand', true);
            
            this._entry.clutter_text.connect('activate', () => {
                let text = this._entry.get_text();
                if (text.trim()) this._processInput(text);
            });

            // 3. Buttons and Dock Area
            this._plusBtn = new St.Button({ style_class: 'jarvis-icon-button' });
            this._plusBtn.set_child(new St.Icon({ icon_name: 'list-add-symbolic', icon_size: 20 }));

            this._recordBtn = new St.Button({ style_class: 'jarvis-icon-button' });
            this._recordBtn.set_child(new St.Icon({ icon_name: 'audio-input-microphone-symbolic', icon_size: 20 }));

            this._sendBtn = new St.Button({ style_class: 'jarvis-icon-button jarvis-send-btn' });
            this._sendBtn.set_child(new St.Icon({ icon_name: 'mail-send-symbolic', icon_size: 20 }));
            this._sendBtn.connect('clicked', () => {
                let text = this._entry.get_text();
                if (text.trim()) this._processInput(text);
            });

            this._btnsRight = new St.BoxLayout({ style_class: 'jarvis-dock-right' });
            this._safeSet(this._btnsRight, 'set_spacing', 4);
            this._safeSet(this._btnsRight, 'spacing', 4);
            
            this._btnsRight.add_child(this._sendBtn);
            this._btnsRight.add_child(this._recordBtn);

            this._inputDock = new St.BoxLayout({ style_class: 'jarvis-input-dock' });
            this._safeSet(this._inputDock, 'vertical', false);
            this._safeSet(this._inputDock, 'set_spacing', 8);
            this._safeSet(this._inputDock, 'spacing', 8);

            this._inputDock.add_child(this._plusBtn);
            this._inputDock.add_child(this._entry);
            this._inputDock.add_child(this._btnsRight);

            // Assembly
            this.add_child(this._historyScroll);
            this.add_child(this._inputDock);

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
            }
        });
    }

    _processInput(text) {
        this._addMessage('user', text);
        this._entry.set_text('');
        
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
                        this._addMessage('jarvis', response);
                    }
                } catch (e) {
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
            text: text,
            style_class: 'jarvis-msg-text',
            x_expand: true,
        });
        
        // Anti-truncation logic
        label.clutter_text.line_wrap = true;
        label.clutter_text.line_wrap_mode = Pango.WrapMode.WORD_CHAR;
        label.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
        
        msgBox.add_child(label);
        
        // Add before the thinking indicator
        let pos = this._historyBox.get_children().indexOf(this._thinkingMsg);
        this._historyBox.insert_child_at_index(msgBox, pos);
        
        this._updatePosition();
    }

    show() {
        this.visible = true;
        this._updatePosition();
        this._entry.grab_key_focus();
        
        // Animation
        this.opacity = 0;
        this.ease({
            opacity: 255,
            duration: 300,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
        });
    }

    hide() {
        this.ease({
            opacity: 0,
            duration: 200,
            mode: Clutter.AnimationMode.EASE_IN_QUAD,
            onComplete: () => {
                this.visible = false;
            }
        });
    }

    toggle() {
        if (this.visible) {
            this.hide();
        } else {
            this.show();
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
    enable() {
        this._overlay = null;
        
        // Subscribe directly to the Toggled signal on the session bus
        // This works even if the Python daemon connects/disconnects arbitrarily.
        this._signalId = Gio.DBus.session.signal_subscribe(
            null, // sender
            'org.jarvis.Assistant', // interface name
            'Toggled', // signal name
            '/org/jarvis/Assistant', // object path
            null, // arg0
            Gio.DBusSignalFlags.NONE,
            (connection, sender, objectPath, interfaceName, signalName, parameters) => {
                this._toggleOverlay();
            }
        );
        
        console.log('J.A.R.V.I.S. Assistant enabled. Listening for D-Bus Toggle signal.');
    }

    disable() {
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
        } finally {
            this._isToggling = false;
        }
    }
}
