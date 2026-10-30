# Task 001: Basiskonfiguration & Shared Utilities

## 🎯 Ziel & Umfang
Bereitstellung der grundlegenden Konfiguration, globalen Hilfsfunktionen und Ausnahmeklassen für das gesamte Projekt. Keine hardcodierten Secrets, saubere Trennung von Entwicklungs- und Produktionsumgebungen über Umgebungsvariablen.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `shared/` & Root
- **Dateien:**
  - `requirements.txt`
  - `shared/config.py`
  - `shared/utils.py`
  - `shared/exceptions.py`

## 🔗 Abhängigkeiten
- Keine (Basis-Task).

## 📝 Fachliche Vorgaben & Spezifikation

### 1. `requirements.txt`
Minimale PyPI-Abhängigkeiten festschreiben:
- `Flask>=3.0.0`
- `Werkzeug>=3.0.0`
- `SQLAlchemy>=2.0.0`
- `bcrypt>=4.1.0`
- `requests>=2.31.0`
- `python-dotenv>=1.0.0`

### 2. `shared/config.py`
- Lädt Umgebungsvariablen mittels `dotenv`.
- Bestimmt Projektpfade (`BASE_DIR`, `DATA_DIR`, `UPLOAD_DIR`).
- Automatische Verzeichniserstellung für Daten und Uploads.
- Zentrale Konfigurationsklasse `Config`:
  - `SECRET_KEY`: Geladen via `AIMO_SECRET_KEY` (Standardwert nur für Development).
  - `DATABASE_PATH`: SQLite-Dateipfad in `DATA_DIR / "aimo.db"`.
  - `DATABASE_URI`: `sqlite:///{DATABASE_PATH}`.
  - `UPLOAD_PATH`: Pfad zum Upload-Ordner (`uploads/`).
  - Standard-Service-URLs: `DEFAULT_OLLAMA_URL` (Port 11434), `DEFAULT_COMFYUI_URL` (Port 8188), `DEFAULT_SEARXNG_URL` (Port 8080).

### 3. `shared/utils.py`
- `hash_password(password: str) -> str`: Sicheres Password-Hashing via `bcrypt`.
- `verify_password(password: str, hashed_password: str) -> bool`: Überprüfung von Passwörtern.
- `parse_tags(raw: str | list[str]) -> list[str]`: Zerlegt Komma-/Semikolon-getrennte Strings in bereinigte, kleingeschriebene, deduplizierte Tag-Listen ohne Leerzeichen.
- `tags_overlap(tags_a: list[str], tags_b: list[str]) -> bool`: Prüft, ob mindestens 1 Tag übereinstimmt (`>= 1`, case-insensitive). Essentiell für das vektorlose RAG.
- `sanitize_filename(filename: str) -> str`: Bereinigt Dateinamen von Sonderzeichen und Umlauten.

### 4. `shared/exceptions.py`
- Basis-Ausnahme: `AimoError(Exception)`.
- Schicht-Ausnahmen: `DomainError`, `InfrastructureError`, `ApplicationError`.

## ✅ Akzeptanzkriterien
- [ ] `requirements.txt` definiert alle Kernabhängigkeiten ohne unnötige Bloat-Pakete.
- [ ] `shared/config.py` liest Einstellungen strikt aus Umgebungsvariablen.
- [ ] `shared/utils.py` enthält funktionierende Hashing-, Tag-Parsing- und Overlap-Routinen.
- [ ] `shared/exceptions.py` stellt die standardisierte Ausnahme-Hierarchie bereit.
