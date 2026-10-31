# Task 021: Admin Dashboard, User Management & Services

## 🎯 Goal & Scope
Implementation of the administration area for managing user accounts, functional permissions with presets, and service connections (Ollama model management with install/delete, ComfyUI, task assignments, and hyperparameters).

## 📂 Affected Layer & Files
- **Layer:** `application/admin/`, `templates/admin/`
- **Files:**
  - `application/admin/views.py`
  - `application/admin/forms.py`
  - `templates/admin/layout.html`
  - `templates/admin/users.html`
  - `templates/admin/user_form.html`
  - `templates/admin/services.html`

## 🔗 Dependencies
- `tasks/003_domain_auth_and_permissions.md`
- `tasks/004_domain_settings_and_system_prompts.md`
- `tasks/005_infrastructure_provider_interfaces_and_adapters.md`
- `tasks/013_infrastructure_repositories.md`
- `tasks/015_ui_theme_static_assets_and_base_template.md`

## 📝 Functional Specifications & Requirements

### 1. User Management (`/admin/users`)
- Overview of all user accounts with permission badges and creation date.
- **New Account Provisioning (`/admin/users/new`):**
  - Username, email, initial password.
  - Assignment via Presets (`Admin`, `Creator`, `User`) or individual checkable flags (`FunctionPermission`).
- **Edit & Delete Users:**
  - Adjust permissions.
  - **Protection Rule:** Initial administrator (`is_initial_admin == True`) can neither be deleted nor have permissions revoked.

### 2. Service Management (`/admin/services`)
- **Ollama Model Management:**
  - Displays all installed models (via `LLMProvider.list_models()`).
  - Install Model (Pull): Input for model tag and progress feedback for `pull`.
  - Delete Model: Action button to remove (`delete`) models to reclaim storage.
- **Task-Specific Assignments:**
  - Dropdowns for `Roleplay`, `Memory`, `Assistant`, and `Vision`.
- **Inference Parameters:**
  - `num_ctx`, `temperature`, `top_p`, `repeat_penalty`.
- **ComfyUI and SearXNG Connections:** URLs and connection health status.
- **System Prompts:** Editable textareas for Roleplay, Memory, Diffuser, and Sparkle prompts.

## ✅ Acceptance Criteria
- [x] Accessible strictly to users holding `ADMIN_ACCESS` permission.
- [x] Initial admin cannot be manipulated or demoted.
- [x] Ollama models can be installed and deleted directly through the UI.
- [x] All system prompts and task model assignments persist and apply immediately.
