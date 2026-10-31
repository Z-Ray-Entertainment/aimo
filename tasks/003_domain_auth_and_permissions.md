# Task 003: Authentication & Functional Permission Model

## 🎯 Goal & Scope
Implement pure domain business logic for user management, password validation, and functional permissions. No rigid role hierarchy (RBAC); instead, granular functional flags with presets and non-revocable protection for the initial administrator.

## 📂 Affected Layer & Files
- **Layer:** `domain/auth/`, `domain/permissions/`
- **Files:**
  - `domain/auth/models.py`
  - `domain/auth/services.py`
  - `domain/auth/exceptions.py`
  - `domain/permissions/models.py`
  - `domain/permissions/services.py`
  - `domain/permissions/exceptions.py`

## 🔗 Dependencies
- `tasks/001_foundation_config_and_shared_utils.md`

## 📝 Functional Specifications & Requirements

### 1. `domain/auth/`
- **`User` (Entity/Dataclass):**
  - `id: int | None`
  - `username: str`
  - `email: str`
  - `password_hash: str`
  - `is_initial_admin: bool = False` (identifies the untouchable Super User)
  - `created_at: datetime`
- **`AuthService`:**
  - `create_user(username: str, email: str, password: str, is_initial_admin: bool = False) -> User` (hashes password via `shared.utils.hash_password`).
  - `authenticate_user(user: User, password: str) -> bool` (verifies via `shared.utils.verify_password`).
  - `change_password(user: User, new_password: str) -> None`.
- **Exceptions:** `AuthError`, `DuplicateEmailError`, `InvalidCredentialsError`.

### 2. `domain/permissions/`
- **`FunctionPermission` (Enum or Value Object):**
  - `ADMIN_ACCESS`: Full access to settings and user management.
  - `CHARACTER_CREATE`, `CHARACTER_EDIT`, `CHARACTER_DELETE`
  - `LOREBOOK_CREATE`, `LOREBOOK_EDIT`, `LOREBOOK_DELETE`
  - `WORLDINFO_CREATE`, `WORLDINFO_EDIT`, `WORLDINFO_DELETE`
  - `CHAT_ACCESS`: Participation in interactive roleplay chats.
  - `PERSONA_MANAGE`: Create and manage custom personas.
- **`UserPermissions` (Entity):**
  - `user_id: int`
  - `permissions: set[str]` (set of active permissions)
- **Presets:**
  - `Preset.ADMIN`: All existing flags.
  - `Preset.CREATOR`: Content creation and editing (`CHARACTER_*`, `LOREBOOK_*`, `WORLDINFO_*`, `PERSONA_MANAGE`, `CHAT_ACCESS`).
  - `Preset.USER`: `CHAT_ACCESS`, `PERSONA_MANAGE`.
- **`PermissionService` & Non-Revocable Permissions:**
  - `assign_preset(user: User, user_perms: UserPermissions, preset: str) -> None`
  - `grant_permission(user: User, user_perms: UserPermissions, permission: str) -> None`
  - `revoke_permission(user: User, user_perms: UserPermissions, permission: str) -> None`:
    - **Protection Rule:** If `user.is_initial_admin == True`, **no** permission may ever be revoked or disabled (`SuperAdminProtectionError`).
  - `has_permission(user_perms: UserPermissions, permission: str) -> bool`.
- **Exceptions:** `PermissionDeniedError`, `SuperAdminProtectionError`.

## ✅ Acceptance Criteria
- [x] Pure domain logic without database imports or Flask dependencies.
- [x] Password hashing and verification function securely.
- [x] Initial admin can neither lose permissions nor be deactivated.
- [x] Presets (`Admin`, `Creator`, `User`) accurately assign designated flag sets.
