# Task 020: Chat-Oberfläche, SSE-Streaming, Countdown & ComfyUI

## 🎯 Ziel & Umfang
Umsetzung des vollständigen Chat-Interfaces: Multi-Chat-Seitenleiste links, 3-Reiter-Container (Chat, Medien, Erinnerungen), SSE-Live-Streaming mit Übersetzungs-Swap, interaktiver Textadventure-Ortswechsel mit 60s-Countdown, Klammer-Upload (Vision-ALT) und ComfyUI-Bildgenerierung mit Eingabespeere und Abbrechen-Button.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `application/chat/`, `templates/chat/`
- **Dateien:**
  - `application/chat/views.py`
  - `application/chat/forms.py`
  - `templates/chat/session.html`
  - `templates/chat/select_worldinfo.html`

## 🔗 Abhängigkeiten
- `tasks/012_domain_chat_sessions_messages_and_prompt_builder.md`
- `tasks/014_application_api_headless_core_rest_endpoints.md`
- `tasks/015_ui_theme_static_assets_and_base_template.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. Initialer Start & Welcome Message ("First Chat")
- Beim Öffnen ohne Chat: Automatische Anlage der Session und sofortige Anzeige der `first_message` des Charakters am Initialort.
- **Vorgelagerte Dialog-Auswahl:**
  - Hat der Benutzer > 1 Persona: Dialog zur Festlegung der Persona für diesen Chat. (Bei 1 Persona automatische Zuweisung).
  - WorldInfo-Auswahl: Dropdown mit Option "Ohne WorldInfo" (Default vorausgewählt).
- **Persona-Sperre:** Nach der 1. User-Nachricht unveränderlich fixiert.
- **WorldInfo-Wechsel:** Stift-Symbol in rechter Info-Box mit Warnung (*"Ein Wechsel kann zu Inkonsistenzen bei früheren Erinnerungen führen"*).

### 2. Layout & Drei-Reiter-Navigation
- **Seitenleiste links (bei mehreren Chats):** Liste aller Sessions mit dynamischen Titeln (aktualisiert nach Memories).
- **Drei-Reiter-Container oben:**
  - **Tab 1: Chat:** Sprechblasen-Historie (KI links mit Portrait/Sprite, Spieler rechts mit Persona).
  - **Tab 2: Medien:** Freigeschaltete 9:16-Bilder, Uploads und ComfyUI-Generierungen.
  - **Tab 3: Erinnerungen:** Übersicht und manuelle Korrektur aller Memories.

### 3. Live-Streaming, Ortswechsel & ComfyUI
- **Streaming:**
  - Nach Absenden: *"Denkt nach..."*.
  - Englischer Rohstream live ausgegraut und verkleinert.
  - Nach Fertigstellung: Spinner neben Bubble, nahtloser Austausch durch deutsche Übersetzung.
- **Ortswechsel-Meldung:**
  - Nachgelagerter Modell-Scan blendet Bestätigungsdialog ein (*"Zu [Ort] wechseln? [Ja] [Nein]"*).
  - Roter Countdown-Balken (60 Sekunden); verfällt bei Nichtreaktion.
  - Bei "Ja": Schaltet Ort und 16:9-Hintergrund um; zeigt zentrierte Systemmeldung (*"Ihr seid nach {ort} gegangen"*), die **nicht** in den LLM-Kontext aufgenommen wird.
- **ComfyUI-Bildgenerierung (Zauberstab ✨):**
  - Zeigt zentrierte Systemmeldung: *"Bild wird generiert..."*.
  - **Texteingabefeld des Nutzers ist gesperrt**.
  - **Abbrechen-Button** erlaubt vorzeitiges Beenden und entsperrt das Eingabefeld wieder.
- **Klammer-Button (Bild-Upload):** Vision-Modell generiert ALT-Text; nur dieser landet im LLM-Kontext.
- **Rechte Info-Box:** Beziehungsbalken (-100 bis +100 mit dynamischen Herzen), WorldInfo, Persona, Checkbox "Events aktivieren/deaktivieren".

## ✅ Akzeptanzkriterien
- [x] Welcome Message wird beim ersten Chat sofort geladen.
- [x] SSE-Streaming mit ausgegrautem Vorab-Text und Übersetzungstausch funktioniert flüssig.
- [x] 60s Countdown für Ortswechsel läuft mit rotem Balken ab.
- [x] Bildgenerierung sperrt Texteingabe und besitzt funktionierenden Abbrechen-Button.
- [x] Systemmeldungen ("Ihr seid nach...") tauchen niemals im LLM-Prompt auf.
