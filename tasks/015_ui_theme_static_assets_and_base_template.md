# Task 015: Modernes RPG-Theme CSS, Scripts & Base Template

## 🎯 Ziel & Umfang
Umsetzung des verbindlichen Design-Systems für die Web-Oberfläche: Modernes RPG-Interface mit warmen Holzrahmen, abgerundeten Ecken, goldenen Button-Rahmen, monochromen Icons, farbigen Status-Herzen und semi-transparentem Cover-Hintergrund.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `static/`, `templates/`
- **Dateien:**
  - `static/css/theme.css`
  - `static/js/main.js`
  - `static/js/stream.js`
  - `static/js/modals.js`
  - `templates/base.html`

## 🔗 Abhängigkeiten
- `tasks/001_foundation_config_and_shared_utils.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. `static/css/theme.css` (Design-Tokens & Styling)
- **Hintergrund:**
  - `background-image` mit Cover-Image.
  - Abgedunkeltes, semi-transparentes Overlay (`backdrop-filter: blur(8px); background: rgba(20, 16, 12, 0.85);`).
- **Rahmen (Borders) & Rundungen:**
  - Hellbraune Holztöne (`--border-wood: #A77445;`, `--border-wood-dark: #8B5A2B;`).
  - Abgerundete Ecken (`border-radius: 10px - 14px;`).
  - Anwendung auf Textfelder (`input`), Textareas (`textarea`), Modale (`.modal-frame`), Kacheln (`.card-tile`) und Porträt-Rahmen.
- **Buttons:**
  - Hintergrund: Warmer Hellbraun-/Leder-Ton (`background: #6E472A;`).
  - Abgerundete Ecken (`border-radius: 8px - 12px;`).
  - Feiner goldener Rahmen (`border: 1px solid #D4AF37;`), warmer Glow-Effekt bei `:hover`.
- **Icons:**
  - Monochrom als Standard für Navigation und Tools (Pfeile, Tabs, Müll, Plus, Stifte).
  - Spezielle Icons in Farbe:
    - Herzen: Farbverlauf von Dunkelrot (💔 bei -100) bis Rosa (💖 bei +100).
    - Sparkles ✨ in leuchtendem Gold/Violett.

### 2. Client-Skripte (`static/js/`)
- `stream.js`: SSE-Streaming-Client für `/api/chat/<id>/stream`. Verwaltet:
  - *"Denkt nach..."*-Zustand.
  - Ausgegraute, verkleinerte Darstellung der englischen Roh-Tokens.
  - Einblenden des Übersetzungs-Spinners.
  - Nahtloser Austausch durch die deutsche Übersetzung.
  - Ortswechsel-Countdown mit rotem schrumpfendem Fortschrittsbalken (60 Sekunden).
- `modals.js`: Generische, barrierefreie Modale für Persona-Manager, Sprite-Augen-View, Lorebook- & Orts-Overlays.

### 3. `templates/base.html`
- Responsives HTML5-Skelett mit Einbindung von `theme.css`, Meta-Tags, Flash-Messages und flexiblen Template-Blöcken (`{% block content %}`).

## ✅ Akzeptanzkriterien
- [x] Theme entspricht exakt den RPG-Vorgaben (Holztöne, Goldrahmen, Rundungen, Cover-Hintergrund).
- [x] SSE-Streaming-Skript ersetzt ausgegrauten englischen Text nahtlos nach Übersetzung.
- [x] 60-Sekunden-Countdown-Balken für Ortswechsel funktioniert zuverlässig.
- [x] Monochrome Standard-Icons und farbige Status-Herzen korrekt gestylt.
