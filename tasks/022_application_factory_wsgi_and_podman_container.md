# Task 022: App-Fabrik, WSGI-Entry & Podman Rootless Image

## 🎯 Ziel & Umfang
Erstellung der zentralen Flask-App-Fabrik (`app.py`), des WSGI-Einstiegspunkts (`wsgi.py`) und des optimierten `Containerfile` für unprivilegierte (rootless) Podman-Container. Abschließende Überprüfung des Gesamtsystems.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** Root & Orchestrierung
- **Dateien:**
  - `app.py`
  - `wsgi.py`
  - `Containerfile`

## 🔗 Abhängigkeiten
- Alle vorherigen Tasks (`tasks/001_...` bis `tasks/021_...`).

## 📝 Fachliche Vorgaben & Spezifikation

### 1. `app.py` (Flask Application Factory)
- `create_app(config_class=Config) -> Flask`:
  - Initialisiert Konfiguration aus `shared.config.Config`.
  - Stellt sicher, dass SQLite-Tabellen via `infrastructure.database.init_db()` bereitstehen.
  - Registriert alle Blueprints mit klaren URL-Präfixen:
    - `/setup` (`application.setup.views`)
    - `/` & `/auth` (`application.auth.views`)
    - `/characters` & `/overview` (`application.overview.views`, `application.characters.views`)
    - `/personas` (`application.personas.views`)
    - `/lorebooks` (`application.lorebooks.views`)
    - `/worldinfo` (`application.worldinfo.views`)
    - `/chat` (`application.chat.views`)
    - `/admin` (`application.admin.views`)
    - `/api` (`application.api` Blueprints für REST-Core)
  - Registriert statische Ordner (`static/`) und Jinja2-Template-Pfade.
  - Initialisiert Before-Request-Hooks (z. B. Weiterleitung auf `/setup`, wenn keine Benutzer existieren).

### 2. `wsgi.py`
- Exponiert die WSGI-Instanz `application = create_app()`.
- Ermöglicht Direktstart via `python wsgi.py` auf Port 5000 (`host="0.0.0.0"`).

### 3. `Containerfile`
- Rootless User-Space Podman Container:
  - Base Image: `python:3.12-slim`.
  - Non-Root Benutzer `aimo` (UID 1000).
  - Installiert Abhängigkeiten aus `requirements.txt`.
  - Mounts für persistente Daten: Volume `/app/data` und `/app/uploads`.
  - Exponiert Port 5000.
  - `CMD ["python", "wsgi.py"]`.

## ✅ Akzeptanzkriterien
- [ ] `create_app()` startet sauber und bindet alle Blueprints ein.
- [ ] Automatische Weiterleitung auf `/setup` beim Erststart ohne Benutzer.
- [ ] Rootless Podman Containerfile baut fehlerfrei und startet ohne Root-Rechte.
- [ ] Gesamtsystem arbeitet als in sich geschlossener, modularer Monolith mit getrennter REST-API.
