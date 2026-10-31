# aimo — Immersives KI-Rollenspiel im modernen RPG-Design

> [!IMPORTANT]
> **Hinweis zur KI-gestützten Entwicklung (Human-in-the-Loop-Prinzip):**
> - **Architektur:** Entworfen von Menschen (*Architecture designed by human*)
> - **Qualitätssicherung:** Code geprüft und getestet von Menschen (*Code reviewed and tested by human*)
> - **Implementierung:** Großteil des Codes geschrieben von KI (*Most code written by AI*)
>
> THIS IS STILL WIP, WHILE IT WORKS IT IS STILL ALPHA

`aimo` ist eine modulare, lokale Rollenspiel-Plattform für interaktives KI-Storytelling und Textadventure-Abenteuer. Das System verbindet modernste lokale Sprach- und Vision-Modelle (Ollama) sowie generative Bild-Pipelines (ComfyUI) mit einem atmosphärischen Tabletop-RPG-Interface.

---

## 🌟 Highlights & Kernfunktionen

- **🎭 Lebendige KI-Charaktere:**
  - 28 differenzierte Emotionen mit transparenten Sprites und Varianten-Auswahl.
  - KI-Schreibassistent ✨ (Sparkle-Button) zur Verfeinerung von Charakterbeschreibungen.
  - Freischaltbare 9:16-Galeriebilder gekoppelt an dynamische Beziehungswerte (-100 bis +100).
- **💬 Reiner Rollenspiel-Kontext (Zero-Control-Tags):**
  - Das Roleplay-Modell schreibt zu 100 % immersive Fließtexte und Dialoge ohne technische Steuercodes.
  - Metadaten (Emotionen, Ortswechsel) werden über einen autarken, nachgelagerten Klassifikations-Schritt ermittelt.
  - Verbindliches 7-Stufen-Prompt-Layout mit geschlossenen Segment-Begrenzern.
- **🧭 Textadventure-Mechanik & Lebendige Welten:**
  - Interaktiver Ortswechsel mit animiertem 60-Sekunden-Countdown.
  - Einheitlicher Event-Pool (Welt- und Orts-Events) mit Cooldown-Zähler-Kreislauf (10–100 Nachrichten).
  - Multimodale Features: Bild-Uploads mit automatischer Vision-ALT-Text-Generierung und ComfyUI-Bildgenerierung via Zauberstab ✨.
- **🎨 Modernes RPG-Theme:**
  - Halbtransparenter Hintergrund mit atmosphärischem Cover-Image.
  - Warme, hellbraune Holzrahmen mit abgerundeten Ecken für alle Eingabefelder und Kacheln.
  - Lederoptik-Buttons mit feinem Goldrand und monochrome Icons mit farbigen Status-Herzen (💔 bis 💖).
- **🔒 Local-First & Headless Core:**
  - Vollständige Persistenz in lokaler SQLite-Datenbank mit WAL-Modus (keine externe DB nötig).
  - Bereitstellung einer konsistenten REST-API (`/api/...`) — Web-UI und alternative Frontends (z. B. eine native GTK4/Libadwaita-App für Flathub) nutzen dieselben Core-Dienste.
  - Modulare Provider-Schnittstellen für LLM (Ollama), Bildgenerierung (ComfyUI) und Voice-TTS.

---

## 🚀 Schnellstart

### Option A: Direktstart mit Podman (Rootless User-Container)

Das Projekt verfügt über ein optimiertes `Containerfile` für unprivilegierte Container:

```bash
# 1. Container-Image bauen
podman build -t aimo -f Containerfile .

# 2. Container im User-Space starten (Port 5000, persistente Volumes)
podman run -d \
  --name aimo \
  -p 5000:5000 \
  -v aimo-data:/app/data:Z,U \
  -v aimo-uploads:/app/uploads:Z,U \
  aimo

# 3. Im Browser aufrufen: http://localhost:5000
```
*Beim ersten Start erscheint automatisch der Setup-Wizard zur Einrichtung des Administrators.*

---

### Option B: Lokale Entwicklung

```bash
# Virtuelle Umgebung erstellen und aktivieren
python3 -m venv venv
source venv/bin/activate

# Abhängigkeiten installieren
pip install -r requirements.txt

# Variante 1: Kombi-Start via Wrapper (generiert automatisch einen UUID4 CLIENT_KEY,
# startet den Core auf Port 5001 und anschließend die Flask Web-UI auf Port 5000)
python aimo_flask.py

# Variante 2: Core und Flask Web-UI getrennt als Standalone-Services starten
# Terminal 1 — Headless Core starten (CLIENT_KEY ist Pflicht):
export CLIENT_KEY="$(uuidgen)"
python core/wsgi.py

# Terminal 2 — Flask Web-UI mit demselben CLIENT_KEY starten:
export CLIENT_KEY="<derselbe-client-key>"
python flask/wsgi.py
```

---

## 📖 Dokumentation & Handbücher

Ausführliche Anleitungen für alle Aspekte der Anwendung findest du im Ordner [`docs/`](docs/README.md):

- [**Ersteinrichtung & First-Boot-Wizard**](docs/first_boot.md): Super-User-Anlage und Ollama-Konfiguration.
- [**Das Hub-Dashboard**](docs/hub.md): 3-Tab-Navigation (Charaktere 👤, Lorebooks 📜, WorldInfo 🌐) und Filter.
- [**Spieler-Personas**](docs/personas.md): Rollenspiel-Identitäten & automatische Vision-Aussehensanalyse.
- [**KI-Charaktere & Designer**](docs/characters.md): Erstellung, Sprites, Varianten und 9:16-Galerien.
- [**Lorebooks & Enzyklopädien**](docs/lorebooks.md): Thematisches Wissen & vektorloses Tag-RAG.
- [**Welten, Orte & Ereignisse (WorldInfo)**](docs/worldinfo.md): 16:9-Hintergründe und Zufalls-Event-Mechanik.
- [**Chat- & Rollenspiel-Interface**](docs/chat.md): Streaming, Übersetzung, Textadventure-Ortswechsel & ComfyUI.
- [**Administration & Modell-Management**](docs/admin.md): Rechte-Presets, Ollama Pull/Delete und System-Prompts.

---

## 🏛️ Architektur & Entwickler-Richtlinien

- **Architekturregeln für Coding Assistants:** [AGENTS.md](AGENTS.md)
- **Implementierungs-Fahrplan (Atomare Tasks):** [tasks/](tasks/README.md)

### Schichtenmodell (Domain-Driven Design)
```
aimo/
├── core/                  # Standalone Headless Core Service (erfordert CLIENT_KEY)
│   ├── domain/            # Reine Geschäftslogik (kein I/O, kein HTTP, kein DB)
│   ├── infrastructure/    # SQLite WAL, Repositories, Modulare Provider (Ollama, ComfyUI, TTS)
│   ├── application/api/   # REST-API Endpunkte (/api/...) gesichert via CLIENT_KEY
│   ├── shared/            # Config via Env, bcrypt, Tag-Overlap-Helper, Exceptions
│   ├── app.py             # Core Application Factory
│   └── wsgi.py            # Core Standalone Entry Point
├── flask/                 # Standalone Flask Web-UI Service
│   ├── application/       # Web-Views, Formulare, Decorators & Core-API-Proxy
│   ├── static/            # Modernes RPG-Theme CSS (theme.css), JS (SSE Stream, Countdown)
│   ├── templates/         # Jinja2-HTML-Templates (Modulare Templates)
│   ├── app.py             # Web-UI Application Factory
│   └── wsgi.py            # Web-UI Standalone Entry Point
├── aimo_flask.py          # Wrapper-Script (erzeugt UUID4 CLIENT_KEY, startet Core & Web-UI)
├── tasks/                 # Atomare Implementierungs-Tasks (001 bis 022)
└── docs/                  # Ausführliche Endbenutzer-Dokumentation
```

---

## 📜 Lizenz

MIT License — siehe LICENSE-Datei.
