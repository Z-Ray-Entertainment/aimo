# Task 001: Base Configuration & Shared Utilities

## 🎯 Goal & Scope
Provide foundational configuration, global utility functions, and exception classes for the entire project. No hardcoded secrets; clean separation of development and production environments via environment variables.

## 📂 Affected Layer & Files
- **Layer:** `shared/` & Root
- **Files:**
  - `requirements.txt`
  - `shared/config.py`
  - `shared/utils.py`
  - `shared/exceptions.py`

## 🔗 Dependencies
- None (Foundation Task).

## 📝 Functional Specifications & Requirements

### 1. `requirements.txt`
Define minimal PyPI dependencies:
- `Flask>=3.0.0`
- `Werkzeug>=3.0.0`
- `SQLAlchemy>=2.0.0`
- `bcrypt>=4.1.0`
- `requests>=2.31.0`
- `python-dotenv>=1.0.0`

### 2. `shared/config.py`
- Loads environment variables via `dotenv`.
- Resolves project paths (`BASE_DIR`, `DATA_DIR`, `UPLOAD_DIR`).
- Automatic directory creation for data and uploads.
- Central configuration class `Config`:
  - `SECRET_KEY`: Loaded via `AIMO_SECRET_KEY` (default value for development only).
  - `DATABASE_PATH`: SQLite file path in `DATA_DIR / "aimo.db"`.
  - `DATABASE_URI`: `sqlite:///{DATABASE_PATH}`.
  - `UPLOAD_PATH`: Path to the uploads directory (`uploads/`).
  - Default service URLs: `DEFAULT_OLLAMA_URL` (port 11434), `DEFAULT_COMFYUI_URL` (port 8188), `DEFAULT_SEARXNG_URL` (port 8080).

### 3. `shared/utils.py`
- `hash_password(password: str) -> str`: Secure password hashing via `bcrypt`.
- `verify_password(password: str, hashed_password: str) -> bool`: Password verification.
- `parse_tags(raw: str | list[str]) -> list[str]`: Splits comma-/semicolon-separated strings into cleaned, lowercased, deduplicated tag lists without whitespace.
- `tags_overlap(tags_a: list[str], tags_b: list[str]) -> bool`: Verifies whether at least 1 tag matches (`>= 1`, case-insensitive). Essential for vectorless RAG.
- `sanitize_filename(filename: str) -> str`: Cleans filenames of special characters and umlauts.

### 4. `shared/exceptions.py`
- Base exception: `AimoError(Exception)`.
- Layer exceptions: `DomainError`, `InfrastructureError`, `ApplicationError`.

## ✅ Acceptance Criteria
- [x] `requirements.txt` defines all core dependencies without unnecessary bloat packages.
- [x] `shared/config.py` strictly reads settings from environment variables.
- [x] `shared/utils.py` contains working hashing, tag parsing, and overlap routines.
- [x] `shared/exceptions.py` provides the standardized exception hierarchy.
