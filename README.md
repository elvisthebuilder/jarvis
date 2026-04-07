```text
   
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
   Just A Rather Very Intelligent System

```

# J.A.R.V.I.S. 2.0 — Just A Rather Very Intelligent System

> *"The Pulse of Your Digital Life."*

**J.A.R.V.I.S.** is a high-performance, system-integrated artificial intelligence assistant designed specifically for the modern Linux workstation. Built with a "Stark Industries" aesthetic and a dual-brain neural architecture, Jarvis bridges the gap between natural language intent and native system execution.

---

## ⚡ The Dual-Brain Architecture

Jarvis utilizes a synchronized neural pipeline to balance extreme reasoning with real-time accuracy:

*   **Primary Core (Reasoning):** [Ollama Cloud / Gemma 4] handles the heavy lifting—complex reasoning, context management, and philosophical alignment (Ikigai).
*   **Secondary Core (Grounding):** [Gemini 2.5 Flash] provides the "Neural OSINT Sync" and real-time search capabilities, ensuring Jarvis is always briefed on the latest data.

---

## 🌌 Core Features

### 🧠 Neural OSINT Synchronization (The Stark Interview)
Upon first boot, Jarvis initiates a multi-phase "Stark Interview" to synchronize with his primary user. This includes a proactive intelligence crawl (OSINT) to gather your professional milestones, projects (like **APPBAI**), and digital footprint, ensuring a deeply personalized experience from second one.

### 🖥️ Native GNOME System Control (The Overlay)
Jarvis doesn't just talk; he *acts*. Integrated via GNOME D-Bus and native Linux tooling:
- **Media Mastery:** Full MPRIS2 integration (Spotify, VLC, Browser).
- **System Internals:** Real-time controls for brightness, volume, power, and thermal monitoring.
- **App Orchestration:** Launch, manage, and monitor system processes with a simple phrase.

### 🛠️ Extensible Tool-Calling System
Jarvis possesses a growing library of "Skills" allowing him to interact with the web, the filesystem, and third-party APIs with high-precision tool calling.

---

## 🚀 One-Liner Installation

Deploy Jarvis to your system with a single command:

```bash
curl -sSL https://raw.githubusercontent.com/elvisthebuilder/jarvis/main/scripts/install.sh | bash
```

### Manual Handshake
1.  **Clone:** `git clone https://github.com/elvisthebuilder/jarvis.git`
2.  **Initialize:** `./scripts/install.sh`
3.  **Credentials:** Update your `.env` with `OLLAMA_API_KEY` and `GEMINI_API_KEY`.
4.  **Boot:** `python -m jarvis.daemon`

---

## 🛠️ Management Suite

Maintain and synchronize your production system with these dedicated utility scripts:

| Command | Action | Description |
|---|---|---|
| **Update** | `bash scripts/update.sh` | Pull latest core code and re-sync the neural environment. |
| **Uninstall** | `bash scripts/uninstall.sh` | Decommission J.A.R.V.I.S. cleanly and choose how to handle your memory. |

---

## 🎹 CLI Orchestration

| Command | Action |
|---|---|
| `/status` | Vital signs and neural synchronization data. |
| `/tools` | List all available system capabilities. |
| `/clear` | Purge current conversation buffer. |
| `exit` | Hibernate Jarvis. |

---

## 📝 License & Identity

**Maintainer:** elvisthebuilder (Elvis Baidoo)  
**Philosophy:** Built for builders, engineers, and philosophers.  
**License:** [MIT](LICENSE)

---

> [!TIP]
> Use **Super + Shift + J** (configured via Gnome Shortcut) to summon the Jarvis Overlay at any time once the daemon is active.
