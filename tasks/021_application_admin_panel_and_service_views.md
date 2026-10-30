# Task 021: Admin-Dashboard, Benutzerverwaltung & Services

## 🎯 Ziel & Umfang
Umsetzung des Administrationsbereichs zur Verwaltung von Benutzern, funktionalen Berechtigungen mit Presets sowie Service-Verbindungen (Ollama Modell-Management mit Install/Delete, ComfyUI, Task-Zuweisung und Hyperparameter).

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `application/admin/`, `templates/admin/`
- **Dateien:**
  - `application/admin/views.py`
  - `application/admin/forms.py`
  - `templates/admin/layout.html`
  - `templates/admin/users.html`
  - `templates/admin/user_form.html`
  - `templates/admin/services.html`

## 🔗 Abhängigkeiten
- `tasks/003_domain_auth_and_permissions.md`
- `tasks/004_domain_settings_and_system_prompts.md`
- `tasks/005_infrastructure_provider_interfaces_and_adapters.md`
- `tasks/013_infrastructure_repositories.md`
- `tasks/015_ui_theme_static_assets_and_base_template.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. Benutzerverwaltung (`/admin/users`)
- Übersicht aller Benutzer mit Berechtigungs-Badges und Datum.
- **Neuanlage (`/admin/users/new`):**
  - Benutzername, E-Mail, Initialpasswort.
  - Zuweisung über Presets (`Admin`, `Creator`, `User`) oder Checkboxen einzelner Flags (`FunctionPermission`).
- **Benutzer bearbeiten & löschen:**
  - Berechtigungen anpassen.
  - **Schutzregel:** Initialer Administrator (`is_initial_admin == True`) kann weder gelöscht werden noch können ihm Rechte entzogen werden.

### 2. Service-Management (`/admin/services`)
- **Ollama Modell-Management:**
  - Anzeige aller installierten Modelle (via `LLMProvider.list_models()`).
  - Modell installieren: Eingabefeld für Modellnamen und Progress-Anzeige für `pull`.
  - Modell löschen: Button zum Entfernen (`delete`) nicht mehr benötigter Modelle.
- **Task-spezifische Zuweisung:**
  - Dropdowns für `Roleplay`, `Memory`, `Assistant` und `Vision`.
- **Inferenz-Parameter:**
  - `num_ctx`, `temperature`, `top_p`, `repeat_penalty`.
- **ComfyUI- und SearXNG-Verbindung:** URLs und Verbindungsstatus.
- **System-Prompts:** Editierbare Textareas für Rollenspiel-, Memory-, Diffuser- und Sparkle-Prompts.

## ✅ Akzeptanzkriterien
- [ ] Nur für Nutzer mit Permission `ADMIN_ACCESS` erreichbar.
- [ ] Initialer Admin kann nicht manipuliert oder degradiert werden.
- [ ] Ollama Modelle können direkt über die Oberfläche installiert und gelöscht werden.
- [ ] Alle System-Prompts und Task-Zuweisungen lassen sich speichern und sofort wirksam anwenden.
