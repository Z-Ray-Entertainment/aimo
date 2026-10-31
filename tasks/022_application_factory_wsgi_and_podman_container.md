# Task 022: App Factory, WSGI Entry & Podman Rootless Image

## 🎯 Goal & Scope
Creation of the central Flask application factory (`app.py`), WSGI entry point (`wsgi.py`), and optimized `Containerfile` for unprivileged (rootless) Podman containers. Comprehensive final review of the system.

## 📂 Affected Layer & Files
- **Layer:** Root & Orchestration
- **Files:**
  - `app.py`
  - `wsgi.py`
  - `Containerfile`

## 🔗 Dependencies
- All preceding tasks (`tasks/001_...` through `tasks/021_...`).

## 📝 Functional Specifications & Requirements

### 1. `app.py` (Flask Application Factory)
- `create_app(config_class=Config) -> Flask`:
  - Initializes configuration from `shared.config.Config`.
  - Ensures SQLite tables are created via `infrastructure.database.init_db()`.
  - Registers all blueprints with clean URL prefixes:
    - `/setup` (`application.setup.views`)
    - `/` & `/auth` (`application.auth.views`)
    - `/characters` & `/overview` (`application.overview.views`, `application.characters.views`)
    - `/personas` (`application.personas.views`)
    - `/lorebooks` (`application.lorebooks.views`)
    - `/worldinfo` (`application.worldinfo.views`)
    - `/chat` (`application.chat.views`)
    - `/admin` (`application.admin.views`)
    - `/api` (`application.api` blueprints for REST Core)
  - Registers static directories (`static/`) and Jinja2 template search paths.
  - Registers before-request hooks (e.g., redirecting to `/setup` if no users exist).

### 2. `wsgi.py`
- Exposes WSGI instance `application = create_app()`.
- Allows direct start via `python wsgi.py` on port 5000 (`host="0.0.0.0"`).

### 3. `Containerfile`
- Rootless user-space Podman container:
  - Base Image: `python:3.12-slim`.
  - Non-root user `aimo` (UID 1000).
  - Installs dependencies from `requirements.txt`.
  - Mounts for persistent data: volumes `/app/data` and `/app/uploads`.
  - Exposes port 5000.
  - `CMD ["python", "wsgi.py"]`.

## ✅ Acceptance Criteria
- [x] `create_app()` boots cleanly and registers all blueprints.
- [x] Automatic redirection to `/setup` on initial launch when no users exist.
- [x] Rootless Podman Containerfile builds cleanly and runs without root privileges.
- [x] Overall system operates as a self-contained, modular monolith with separated REST API.
