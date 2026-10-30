# Task 003: Authentifizierung & Funktionales Rechtemodell

## 🎯 Ziel & Umfang
Implementierung der reinen Geschäftslogik für Benutzerverwaltung, Passwortvalidierung und funktionale Berechtigungen. Keine Rollenhierarchie (RBAC), sondern feingranulare Funktions-Flags mit Presets und unentziehbarem Schutz für den initialen Administrator.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `domain/auth/`, `domain/permissions/`
- **Dateien:**
  - `domain/auth/models.py`
  - `domain/auth/services.py`
  - `domain/auth/exceptions.py`
  - `domain/permissions/models.py`
  - `domain/permissions/services.py`
  - `domain/permissions/exceptions.py`

## 🔗 Abhängigkeiten
- `tasks/001_foundation_config_and_shared_utils.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. `domain/auth/`
- **`User` (Entity/Dataclass):**
  - `id: int | None`
  - `username: str`
  - `email: str`
  - `password_hash: str`
  - `is_initial_admin: bool = False` (kennzeichnet den unantastbaren Super-User)
  - `created_at: datetime`
- **`AuthService`:**
  - `create_user(username: str, email: str, password: str, is_initial_admin: bool = False) -> User` (hashed Passwort via `shared.utils.hash_password`).
  - `authenticate_user(user: User, password: str) -> bool` (Prüfung via `shared.utils.verify_password`).
  - `change_password(user: User, new_password: str) -> None`.
- **Exceptions:** `AuthError`, `DuplicateEmailError`, `InvalidCredentialsError`.

### 2. `domain/permissions/`
- **`FunctionPermission` (Enum oder Value Object):**
  - `ADMIN_ACCESS`: Voller Zugriff auf Einstellungen und Benutzerverwaltung.
  - `CHARACTER_CREATE`, `CHARACTER_EDIT`, `CHARACTER_DELETE`
  - `LOREBOOK_CREATE`, `LOREBOOK_EDIT`, `LOREBOOK_DELETE`
  - `WORLDINFO_CREATE`, `WORLDINFO_EDIT`, `WORLDINFO_DELETE`
  - `CHAT_ACCESS`: Teilnahme an interaktiven Rollenspielen.
  - `PERSONA_MANAGE`: Eigene Personas anlegen und pflegen.
- **`UserPermissions` (Entity):**
  - `user_id: int`
  - `permissions: set[str]` (Menge aktiver Permissions)
- **Presets:**
  - `Preset.ADMIN`: Alle existierenden Flags.
  - `Preset.CREATOR`: Erstellung und Bearbeitung von Content (`CHARACTER_*`, `LOREBOOK_*`, `WORLDINFO_*`, `PERSONA_MANAGE`, `CHAT_ACCESS`).
  - `Preset.USER`: `CHAT_ACCESS`, `PERSONA_MANAGE`.
- **`PermissionService` & Unentziehbare Rechte:**
  - `assign_preset(user: User, user_perms: UserPermissions, preset: str) -> None`
  - `grant_permission(user: User, user_perms: UserPermissions, permission: str) -> None`
  - `revoke_permission(user: User, user_perms: UserPermissions, permission: str) -> None`:
    - **Schutzregel:** Ist `user.is_initial_admin == True`, darf **keine** Berechtigung entzogen oder deaktiviert werden (`SuperAdminProtectionError`).
  - `has_permission(user_perms: UserPermissions, permission: str) -> bool`.
- **Exceptions:** `PermissionDeniedError`, `SuperAdminProtectionError`.

## ✅ Akzeptanzkriterien
- [ ] Reine Domain-Logik ohne Datenbank-Imports oder Flask-Abhängigkeiten.
- [ ] Passwort-Hashing und -Validierung funktionieren sicher.
- [ ] Initialer Admin kann sich weder Rechte entziehen noch deaktiviert werden.
- [ ] Presets (`Admin`, `Creator`, `User`) weisen die definierten Flag-Mengen korrekt zu.
