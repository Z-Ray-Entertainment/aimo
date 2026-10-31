# Task 017: Hub-Dashboard (3-Tab-Navigation & Persona-Modal)

## 🎯 Ziel & Umfang
Umsetzung der zentralen Hauptübersicht nach dem Login mit Persona-Avatar-Button im Header, modalem Persona-Manager und dem 3-Tab-Container (Charaktere 👤, Lorebooks 📜, WorldInfo 🌐).

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `application/overview/`, `templates/overview/`
- **Dateien:**
  - `application/overview/views.py`
  - `templates/overview/index.html`

## 🔗 Abhängigkeiten
- `tasks/006_domain_personas_and_vision_analysis.md`
- `tasks/007_domain_lorebooks_and_entries.md`
- `tasks/008_domain_worldinfo_locations_and_events.md`
- `tasks/009_domain_characters_and_emotional_sprites.md`
- `tasks/015_ui_theme_static_assets_and_base_template.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. Header & Default-Persona-Button
- Zeigt oben rechts/mittig das Porträt der aktuellen Standard-Persona des Benutzers.
- Klick öffnet ein **modales Overlay zur Persona-Verwaltung**:
  - Grid-Ansicht aller eigenen Personas.
  - Neuanlage-Kachel (`+`).
  - Bearbeiten und Löschen (Lösch-Button deaktiviert mit Hinweis, wenn Persona in Chats verwendet wird).

### 2. Tab 1: KI-Charaktere (`👤`)
- **Erste Kachel (Neuer Charakter):** Platzhalter mit grünem Plus-Symbol (`+`) im selben Fluss wie Porträts (nur sichtbar bei Berechtigung `character_create`). Klick führt zu `/characters/new`.
- **Charakter-Kacheln:**
  - Primary Portrait als Kachelhintergrund.
  - **Scrollender Overlay-Text:** Zeigt die Persönlichkeitsbeschreibung im Porträtrahmen an.
  - **Sprechblasen-Icon (unten links):** Zeigt Gesamtanzahl ausgetauschter Nachrichten dieses Benutzers mit dem Charakter (nur bei Nachrichten > 0).
  - **Beziehungsstatus-Balken (-100 bis +100):**
    - Zeigt den besten Beziehungswert aller Chats dieses Benutzers.
    - Dynamische Farb- und Icon-Steuerung: -100 dunkelrot mit zerbrochenem Herz (💔), +100 rosa mit funkelndem Herz (💖).
  - **Filter & Sortierung:** Neue Charaktere, Geschlecht (`Gender`), sortieren nach "bereits gechattet / noch nicht gechattet".
  - Klick öffnet die Chat-Ansicht für den Charakter.

### 3. Tab 2: Lorebooks (`📜`)
- Grid-Ansicht aller Lorebooks.
- Erste Kachel: Add-Kachel (`+`) zum Anlegen eines neuen Lorebooks (bei Recht `lorebook_create`).
- Kacheln mit Titel, Tags und Eintragsanzahl. Klick öffnet `/lorebooks/<id>`.

### 4. Tab 3: WorldInfo (`🌐`)
- Grid-Ansicht aller Welten.
- Erste Kachel: Add-Kachel (`+`) zum Anlegen (bei Recht `worldinfo_create`).
- Kacheln mit Icon (`icon`), Titel und Ortsanzahl. Klick öffnet `/worldinfo/<id>`.

## ✅ Akzeptanzkriterien
- [x] 3-Tab-Container mit Icons (`👤`, `📜`, `🌐`) schaltet ohne Seiten-Reload reibungslos um.
- [x] Erste Kachel mit Plus-Symbol prüft Berechtigungen (`character_create` etc.).
- [x] Scrollender Beschreibungstext und Beziehungsbalken mit dynamischen Herzen im Charakter-Porträt.
- [x] Persona-Modal ermöglicht Wechsel, Neuanlage und respektiert die Lösch-Sperre.
