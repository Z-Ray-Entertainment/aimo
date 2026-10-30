# Task 016: First-Boot Wizard & Login-Controller

## 🎯 Ziel & Umfang
Umsetzung des Erststart-Wizards (`/setup`), wenn noch keine Benutzer in der Datenbank existieren, und der zentralen Login-Maske (`/login`). Kein öffentlicher Registrierungspfad (`/register` gesperrt/deaktiviert).

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `application/setup/`, `application/auth/`, `templates/setup/`, `templates/auth/`
- **Dateien:**
  - `application/setup/views.py`
  - `application/setup/forms.py`
  - `application/auth/views.py`
  - `application/auth/forms.py`
  - `application/auth/decorators.py`
  - `templates/setup/first_boot.html`
  - `templates/auth/login.html`

## 🔗 Abhängigkeiten
- `tasks/003_domain_auth_and_permissions.md`
- `tasks/013_infrastructure_repositories.md`
- `tasks/015_ui_theme_static_assets_and_base_template.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. First-Boot Wizard (`/setup`)
- **Bedingung:** Nur aufrufbar, wenn `UserRepository.count_users() == 0`. Andernfalls Weiterleitung auf `/login`.
- **Eingabefelder:**
  - Initialer Administrator: Benutzername, E-Mail, Passwort.
  - Externe Services: Ollama-URL (Pflichtfeld), SearXNG-URL (optional), ComfyUI-URL (optional).
- **Aktionen beim Absenden:**
  - Erstellt Super-User mit `is_initial_admin = True`.
  - Weist via `PermissionService` das `Preset.ADMIN` zu.
  - Speichert Service-Einstellungen in `SettingsRepository`.
  - Loggt den Administrator automatisch ein und leitet zum Hub-Dashboard weiter.

### 2. Login & Session-Management (`/login`, `/logout`)
- **Login-Maske (`templates/auth/login.html`):** E-Mail und Passwort.
- Authentifizierung via `AuthService.authenticate_user()`.
- Speichert `user_id` in Flask `session`.
- **Geschützte Bereiche & Decorators (`decorators.py`):**
  - `@require_auth`: Leitet unauthentifizierte Nutzer mit `next`-Parameter auf `/login` um.
  - `@require_permission(permission_name)`: Prüft funktionale Berechtigung via `PermissionService.has_permission()`. Wirft 403 bei fehlender Berechtigung.

## ✅ Akzeptanzkriterien
- [ ] First-Boot sperrt sich nach erfolgreicher Erstellung des ersten Benutzers dauerhaft.
- [ ] Initialer Admin erhält unentziehbare Super-User-Rechte.
- [ ] Keine öffentliche Registrierung; Login-Maske validiert Passwörter sicher.
- [ ] Ungeschützte Zugriffe leiten verlässlich auf `/login` weiter.
