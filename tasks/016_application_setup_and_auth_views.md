# Task 016: First-Boot Wizard & Login Controllers

## 🎯 Goal & Scope
Implement the first-boot setup wizard (`/setup`), active only when no users exist in the database, and the central login portal (`/login`). No public registration endpoint (`/register` is locked/disabled).

## 📂 Affected Layer & Files
- **Layer:** `application/setup/`, `application/auth/`, `templates/setup/`, `templates/auth/`
- **Files:**
  - `application/setup/views.py`
  - `application/setup/forms.py`
  - `application/auth/views.py`
  - `application/auth/forms.py`
  - `application/auth/decorators.py`
  - `templates/setup/first_boot.html`
  - `templates/auth/login.html`

## 🔗 Dependencies
- `tasks/003_domain_auth_and_permissions.md`
- `tasks/013_infrastructure_repositories.md`
- `tasks/015_ui_theme_static_assets_and_base_template.md`

## 📝 Functional Specifications & Requirements

### 1. First-Boot Wizard (`/setup`)
- **Condition:** Accessible strictly when `UserRepository.count_users() == 0`. Otherwise redirects to `/login`.
- **Form Inputs:**
  - Initial Administrator: Username, email, password.
  - External Services: Ollama URL (mandatory), SearXNG URL (optional), ComfyUI URL (optional).
- **Submission Actions:**
  - Creates Super User with `is_initial_admin = True`.
  - Assigns `Preset.ADMIN` via `PermissionService`.
  - Persists service settings into `SettingsRepository`.
  - Automatically authenticates administrator session and redirects to Hub Dashboard.

### 2. Login & Session Management (`/login`, `/logout`)
- **Login View (`templates/auth/login.html`):** Email and password.
- Authenticates via `AuthService.authenticate_user()`.
- Stores `user_id` in Flask `session`.
- **Protected Endpoints & Decorators (`decorators.py`):**
  - `@require_auth`: Redirects unauthenticated visitors to `/login` with `next` parameter.
  - `@require_permission(permission_name)`: Checks functional permissions via `PermissionService.has_permission()`. Emits HTTP 403 on permission denial.

## ✅ Acceptance Criteria
- [x] First-Boot locks itself permanently following the successful creation of the first user.
- [x] Initial admin receives non-revocable Super User privileges.
- [x] No public self-registration; login form securely validates credentials.
- [x] Unauthenticated requests reliably redirect to `/login`.
