# Task 018: Character Designer (Info-Tab, Sparkle ✨, Sprites)

## 🎯 Ziel & Umfang
Umsetzung des Charakter-Designers (`/characters/new` und `/characters/<id>/edit`) mit oberer Aktionsleiste, Tab 1 (Hauptinformationen, KI-Sparkle-Button, freischaltbare Galeriebilder) und Tab 2 (Emotionale Sprites im Stackview mit Augen-Popup).

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `application/characters/`, `templates/characters/`
- **Dateien:**
  - `application/characters/views.py`
  - `application/characters/forms.py`
  - `templates/characters/creator.html`

## 🔗 Abhängigkeiten
- `tasks/009_domain_characters_and_emotional_sprites.md`
- `tasks/013_infrastructure_repositories.md`
- `tasks/015_ui_theme_static_assets_and_base_template.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. Header & Aktionsleiste
- Zurück-Button (`←`) zur Übersicht.
- Obere Aktionsleiste:
  - Sichtbarkeit: Dropdown (`Privat` / `Öffentlich`).
  - Speichern: Validiert und persistiert den Charakter.
  - Kopieren: Dupliziert den Charakter als neuen Entwurf.
  - Löschen: Entfernt den Charakter (inkl. Bestätigungsabfrage).

### 2. Tab 1: Hauptinformationen
- Name, Geschlecht (`male`, `female`, `non-binary`).
- Primary Portrait (Pflicht-Upload).
- Beschreibung mit Sparkle-Button ✨:
  - Asynchroner Aufruf des Assistant-Modells mit System-Prompt: *"Du bist ein professioneller Autor und entwirfst eine Charakterbeschreibung auf Basis der gegebenen Vorlage: {bisherige Beschreibung}"*.
  - Schreibt das verbesserte Ergebnis direkt in die Textarea.
- Gesprächsbeispiele (`list[str]`), First Message & Initialort.
- Verknüpfte Lorebooks (Multi-Select) und empfohlene WorldInfo (Dropdown).
- Ortspräferenzen (bevorzugt / gemieden).
- Freischaltbare 9:16-Galeriebilder:
  - Liste von Bildern mit Schwellenwert-Feld (-100 bis +100).
  - Add-Kachel (`+`) zum Hochladen weiterer 9:16-Bilder.
  - Löschen-Overlay über jedem Bild.

### 3. Tab 2: Emotionale Sprites
- Grid-Ansicht aller 28 Emotionen (`Emotion`-Enum); Name der Emotion steht unten im Bild.
- Klick auf leere Kachel öffnet Upload-Dialog (transparentes PNG/WEBP).
- **Varianten & Stackview:**
  - Bei existierendem Sprite: Kleiner Button mit **Papier-Plus-Symbol** (📄➕) zum Upload weiterer Varianten.
  - Bei mehreren Sprites: Gestapelte Ansicht (**Stackview**).
  - **Augen-Button (👁️):** Erscheint nur bei mehreren Varianten. Klick öffnet modales Popup mit allen Bildern dieser Emotion und Löschen-Buttons über jedem Bild.
  - Bei Einzelsprite: Löschen-Button direkt als Overlay über dem Bild.

## ✅ Akzeptanzkriterien
- [x] Sparkle-Button ✨ optimiert Textarea-Inhalt via KI-Autor-Prompt.
- [x] Galeriebilder besitzen konfigurierbare Schwellenwerte (-100 bis +100).
- [x] Sprite-Grid unterstützt Upload, Papier-Plus für Varianten, Stackview und Augen-Modal.
- [x] Formularvalidierung erzwingt Name, Geschlecht und Primary Portrait.
