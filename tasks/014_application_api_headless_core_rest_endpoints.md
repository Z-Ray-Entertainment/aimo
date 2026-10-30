# Task 014: REST-API Endpunkte (Headless Core)

## 🎯 Ziel & Umfang
Bereitstellung der zentralen REST-API (`/api/...`), um das System als autarken Hintergrund-Dienst ("Headless Core") zu steuern. Ermöglicht den konsistenten Zugriff für das Web-UI sowie alternative Frontends (wie eine native GTK4/Libadwaita-App für Flathub).

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `application/api/`
- **Dateien:**
  - `application/api/chat.py`
  - `application/api/characters.py`
  - `application/api/personas.py`
  - `application/api/worldinfo.py`
  - `application/api/lorebooks.py`
  - `application/api/admin.py`

## 🔗 Abhängigkeiten
- `tasks/013_infrastructure_repositories.md`
- `tasks/012_domain_chat_sessions_messages_and_prompt_builder.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. `application/api/chat.py`
- `POST /api/chat/<id>/messages`:
  - Nimmt Benutzer-Nachricht entgegen (optional mit Bild-Upload).
  - Übersetzt Nachricht ins Englische.
  - Prüft Cooldown & triggert ggf. Event aus einheitlichem Pool.
  - Assembliert 7-Stufen-Prompt.
  - Gibt SSE-Stream (`/api/chat/<id>/stream`) zurück:
    - Event `token`: Rohe englische Tokens für Live-Streaming.
    - Event `generation_done`: Generierung beendet.
    - **Nachgelagerter Klassifikations-Call:** Ermittelt Emotion und Ortswechsel.
    - **Übersetzung:** Übersetzt englische Antwort in Nutzersprache.
    - Event `message_complete`: Liefert lokalisierten Text, Sprite-Auswahl und ggf. Ortswechsel-Vorschlag.
    - **Asynchroner Background-Task:** Memory-Prüfung alle 10 Nachrichten.
- `POST /api/chat/<id>/switch-location`: Bestätigt Ortswechsel, schaltet Hintergrund um.
- `POST /api/chat/<id>/cancel-image`: Bricht laufende ComfyUI-Bildgenerierung ab.
- `POST /api/chat/<id>/fork`: Erstellt Chat-Kopie ab `fork_point_idx`.
- `DELETE /api/chat/<id>/messages/<idx>`: Löscht Nachricht und Folgende kaskadierend.

### 2. `application/api/characters.py` & Co.
- `GET /api/characters`: Liste aller sichtbaren Charaktere mit Beziehungsstand und Nachrichtenanzahl.
- `POST /api/characters`: Erstellung (inkl. Sprites und Galerie).
- `GET /api/personas`, `POST /api/personas`: Persona-CRUD & Vision-Trigger.
- `GET /api/worldinfo`, `POST /api/worldinfo/events`: Welten, Orte, Events.
- `GET /api/lorebooks`: Lorebook-Verwaltung.

## ✅ Akzeptanzkriterien
- [ ] SSE-Streaming liefert Roh-Tokens, gefolgt von nachgelagerter Klassifikation und Übersetzung.
- [ ] Alle wesentlichen Core-Funktionen sind über reine JSON-/REST-Endpunkte erreichbar.
- [ ] Vollständige Entkopplung für alternative Frontends (GTK4/Flathub).
