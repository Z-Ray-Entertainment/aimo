# aimo — Immersives KI-Rollenspiel im modernen RPG-Design

> [!IMPORTANT]
> **Hinweis zur KI-gestützten Entwicklung (Human-in-the-Loop-Prinzip):**
> - **Architektur:** Entworfen von Menschen (*Architecture designed by human*)
> - **Qualitätssicherung:** Code geprüft und getestet von Menschen (*Code reviewed and tested by human*)
> - **Implementierung:** Großteil des Codes geschrieben von KI (*Most code written by AI*)

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

# Server starten
python wsgi.py
# Läuft auf http://localhost:5000
```

---

## 📖 Dokumentation & Handbücher

Ausführliche Anleitungen für alle Aspekte der Anwendung findest du im Ordner [`docs/`](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/README.md):

- [**Ersteinrichtung & First-Boot-Wizard**](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/first_boot.md): Super-User-Anlage und Ollama-Konfiguration.
- [**Das Hub-Dashboard**](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/hub.md): 3-Tab-Navigation (Charaktere 👤, Lorebooks 📜, WorldInfo 🌐) und Filter.
- [**Spieler-Personas**](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/personas.md): Rollenspiel-Identitäten & automatische Vision-Aussehensanalyse.
- [**KI-Charaktere & Designer**](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/characters.md): Erstellung, Sprites, Varianten und 9:16-Galerien.
- [**Lorebooks & Enzyklopädien**](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/lorebooks.md): Thematisches Wissen & vektorloses Tag-RAG.
- [**Welten, Orte & Ereignisse (WorldInfo)**](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/worldinfo.md): 16:9-Hintergründe und Zufalls-Event-Mechanik.
- [**Chat- & Rollenspiel-Interface**](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/chat.md): Streaming, Übersetzung, Textadventure-Ortswechsel & ComfyUI.
- [**Administration & Modell-Management**](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/admin.md): Rechte-Presets, Ollama Pull/Delete und System-Prompts.

---

## 🏛️ Architektur & Entwickler-Richtlinien

- **Architekturregeln für Coding Assistants:** [AGENTS.md](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/AGENTS.md)
- **Implementierungs-Fahrplan (Atomare Tasks):** [tasks/](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/tasks/README.md)

### Schichtenmodell (Domain-Driven Design)
```
aimo/
├── domain/            # Reine Geschäftslogik (kein I/O, kein HTTP, kein DB)
├── infrastructure/    # SQLite WAL, Repositories, Modulare Provider (Ollama, ComfyUI, TTS)
├── application/       # Views, Formulare, Decorators & REST-API (/api/...)
├── shared/            # Config via Env, bcrypt, Tag-Overlap-Helper, Exceptions
├── static/            # Modernes RPG-Theme CSS (theme.css), JS (SSE Stream, Countdown)
├── templates/         # Jinja2-HTML-Templates (Modulare Templates)
├── tasks/             # Atomare Implementierungs-Tasks (001 bis 022)
└── docs/              # Ausführliche Endbenutzer-Dokumentation
```

---

## 📜 Lizenz

MIT License — siehe LICENSE-Datei.
