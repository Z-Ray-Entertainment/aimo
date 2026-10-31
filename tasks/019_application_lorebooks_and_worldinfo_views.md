# Task 019: Lorebook- & WorldInfo-Editoren (Places & Events)

## 🎯 Ziel & Umfang
Umsetzung der Editoren für Lorebooks und WorldInfo inklusive modalem Eintrags-Editor, 16:9-Orts-Upload mit Vision-ALT-Erweiterungsabfrage und Tab 2 für Events mit Zugehörigkeits-Badges.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `application/lorebooks/`, `application/worldinfo/`, `templates/lorebooks/`, `templates/worldinfo/`
- **Dateien:**
  - `application/lorebooks/views.py`
  - `application/lorebooks/forms.py`
  - `templates/lorebooks/detail.html`
  - `application/worldinfo/views.py`
  - `application/worldinfo/forms.py`
  - `templates/worldinfo/detail.html`

## 🔗 Abhängigkeiten
- `tasks/007_domain_lorebooks_and_entries.md`
- `tasks/008_domain_worldinfo_locations_and_events.md`
- `tasks/013_infrastructure_repositories.md`
- `tasks/015_ui_theme_static_assets_and_base_template.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. Lorebook-Editor (`templates/lorebooks/detail.html`)
- Name des Lorebooks (editierbar).
- Kachelansicht aller Einträge:
  - **Erste Kachel:** Platzhalter mit Plus-Symbol (`+`) zum Hinzufügen.
  - Kacheln mit Titel, Tags und Textvorschau.
- **Modaler Overlay-Frame für Einträge:**
  - Titel (`str`), Tags (`list[str]`), Beschreibung / Fließtext (`textarea`).
  - Speichern und Löschen.

### 2. WorldInfo-Editor (`templates/worldinfo/detail.html`)
- Name der Welt, Icon-Upload / Symbol (`icon`).
- **Tab 1: Places (Orte):**
  - Kachelansicht aller zugehörigen Orte; erste Kachel ist Add-Kachel (`+`).
  - **Modaler Overlay-Frame für Orte:**
    - Name, Tags, Beschreibung.
    - Bildupload im Querformat 16:9 (PNG, JPG, WEBP).
    - **Vision-ALT & Erweiterungsabfrage:** Nach Upload generiert das Vision-Modell einen ALT-Text; Dialog fragt: *"Möchtest du die Ortsbeschreibung um die KI-generierte Bildbeschreibung erweitern?"*.
    - Event-Zuordnung (Liste der Events an diesem Ort).
- **Tab 2: Events (Ereignisse):**
  - Grid-Ansicht aller Events; erste Kachel ist Add-Kachel (`+`).
  - Kacheln zeigen Titel, Wahrscheinlichkeit (0–100%), One-Shot-Status und deutlich ein **Zugehörigkeits-Badge** (konkreter Ort oder *"Gesamte Welt"*).
  - **Modaler Overlay-Frame für Events:**
    - Titel, Wahrscheinlichkeit (`0 - 100%`), One-Shot-Checkbox.
    - Zugehörigkeit: Dropdown ("Gesamte Welt" oder Ort aus dieser WorldInfo). **Regel:** Entweder Welt oder konkreter Ort.
    - Szenische Beschreibung des Ereignisses.

## ✅ Akzeptanzkriterien
- [x] Add-Kachel an erster Stelle in allen Grids.
- [x] 16:9-Hintergrunderweiterung mit interaktiver Vision-ALT-Abfrage.
- [x] Events zeigen Zugehörigkeits-Badges und sind exklusiv der Welt oder einem Ort zugeordnet.
