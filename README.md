# aimo — Immersive AI Roleplay with Modern RPG Design

> [!IMPORTANT]
> **Notice on AI-Assisted Development (Human-in-the-Loop Principle):**
> - **Architecture:** Designed by human
> - **Quality Assurance:** Code reviewed and tested by human
> - **Implementation:** Most code written by AI
>
> THIS IS STILL WIP, WHILE IT WORKS IT IS STILL ALPHA

`aimo` is a modular, local-first roleplaying platform for interactive AI storytelling and text adventures. The system bridges state-of-the-art local language and vision models (Ollama) and generative image pipelines (ComfyUI) with an atmospheric tabletop RPG interface.

---

## 🌟 Highlights & Core Features

- **🎭 Living AI Characters:**
  - 28 distinct emotions with transparent sprites and variant selection.
  - AI Writing Assistant ✨ (Sparkle button) for refining character descriptions.
  - Unlockable 9:16 portrait gallery images tied to dynamic relationship values (-100 to +100).
- **💬 Pure Roleplay Context (Zero-Control-Tags):**
  - The roleplay model produces 100% immersive prose and dialogue without technical control codes.
  - Metadata (emotions, location changes) is detected via an autonomous, downstream classification step.
  - Mandatory 7-stage prompt layout with enclosed segment delimiters.
- **🧭 Text Adventure Mechanics & Dynamic Worlds:**
  - Interactive location transitions with an animated 60-second countdown.
  - Unified event pool (world and location events) with a cooldown counter cycle (10–100 messages).
  - Multimodal features: Image uploads with automatic Vision ALT-text generation and ComfyUI image generation via Magic Wand ✨.
- **🎨 Modern RPG Theme:**
  - Semi-transparent background with atmospheric cover image.
  - Warm light brown wood frames with rounded corners for all input fields and tiles.
  - Leather-style buttons with a delicate gold border and monochrome icons with colored relationship status hearts (💔 to 💖).
- **🔒 Local-First & Headless Core:**
  - Full persistence in a local SQLite database with WAL mode (no external database required).
  - Exposure of a consistent REST API (`/api/...`) — Web UI and alternative frontends (e.g., a native GTK4/Libadwaita Flathub app) share the exact same core services.
  - Modular provider interfaces for LLM (Ollama), image generation (ComfyUI), and voice TTS.

---

## 🚀 Quickstart

### Option A: Direct Run with Podman (Rootless User Container)

The project includes an optimized `Containerfile` for unprivileged containers:

```bash
# 1. Build the container image
podman build -t aimo -f Containerfile .

# 2. Run the container in user space (Port 5000, persistent volumes)
podman run -d \
  --name aimo \
  -p 5000:5000 \
  -v aimo-data:/app/data:Z,U \
  -v aimo-uploads:/app/uploads:Z,U \
  aimo

# 3. Open in your browser: http://localhost:5000
```
*On first boot, the setup wizard will launch automatically to set up the administrator account.*

---

### Option B: Local Development

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Option 1: Combined start via wrapper (automatically generates a UUID4 CLIENT_KEY,
# starts the Core on port 5001 and then the Flask Web UI on port 5000)
python aimo_flask.py

# Option 2: Start Core and Flask Web UI separately as standalone services
# Terminal 1 — Start Headless Core (CLIENT_KEY is mandatory):
export CLIENT_KEY="$(uuidgen)"
python core/wsgi.py

# Terminal 2 — Start Flask Web UI with the same CLIENT_KEY:
export CLIENT_KEY="<the-same-client-key>"
python flask/wsgi.py
```

---

## 📖 Documentation & Guides

Comprehensive guides for all aspects of the application are located in [`docs/`](docs/README.md):

- [**Initial Setup & First-Boot Wizard**](docs/first_boot.md): Super-user creation and Ollama configuration.
- [**The Hub Dashboard**](docs/hub.md): 3-tab navigation (Characters 👤, Lorebooks 📜, WorldInfo 🌐) and filtering.
- [**Player Personas**](docs/personas.md): Roleplay identities & automated vision appearance extraction.
- [**AI Characters & Designer**](docs/characters.md): Creation, sprites, variants, and 9:16 galleries.
- [**Lorebooks & Encyclopedias**](docs/lorebooks.md): Thematic knowledge & vectorless tag-based RAG.
- [**Worlds, Places & Events (WorldInfo)**](docs/worldinfo.md): 16:9 backgrounds and random event mechanics.
- [**Chat & Roleplay Interface**](docs/chat.md): Streaming, translation, text adventure location changes & ComfyUI.
- [**Administration & Model Management**](docs/admin.md): Permission presets, Ollama pull/delete, and system prompts.

---

## 🏛️ Architecture & Developer Guidelines

- **Architecture Rules for Coding Assistants:** [AGENTS.md](AGENTS.md)
- **Implementation Roadmap (Atomic Tasks):** [tasks/](tasks/README.md)

### Layer Architecture (Domain-Driven Design)
```
aimo/
├── core/                  # Standalone Headless Core Service (requires CLIENT_KEY)
│   ├── domain/            # Pure business logic (no I/O, no HTTP, no DB)
│   ├── infrastructure/    # SQLite WAL, Repositories, Modular Providers (Ollama, ComfyUI, TTS)
│   ├── application/api/   # REST API endpoints (/api/...) secured via CLIENT_KEY
│   ├── shared/            # Config via Env, bcrypt, Tag-Overlap-Helper, Exceptions
│   ├── app.py             # Core Application Factory
│   └── wsgi.py            # Core Standalone Entry Point
├── flask/                 # Standalone Flask Web-UI Service
│   ├── application/       # Web views, forms, decorators & Core API proxy
│   ├── static/            # Modern RPG theme CSS (theme.css), JS (SSE Stream, countdown)
│   ├── templates/         # Modular Jinja2 HTML templates
│   ├── app.py             # Web-UI Application Factory
│   └── wsgi.py            # Web-UI Standalone Entry Point
├── aimo_flask.py          # Wrapper script (generates UUID4 CLIENT_KEY, runs Core & Web-UI)
├── tasks/                 # Atomic implementation tasks (001 to 022)
└── docs/                  # Detailed end-user documentation
```

---

## 📜 License

MIT License — see LICENSE file.
