# 🛡️ Administration & Settings

[← Back to Overview](README.md) | [← The Hub Dashboard](hub.md)

The Admin Panel is reserved for users holding the `ADMIN_ACCESS` permission. Here, you manage user accounts, assign functional permissions, configure local AI models, and customize the system backdrop.

---

## 🧭 Navigation & Layout

The Administration area shares the exact same two-column layout as the [User Settings](settings.md):
- **Left Sidebar (`Administration`):**
  - **Benutzerverwaltung (`👥`):** Opens the user and functional permission management.
  - **Services & Modelle (`⚙️`):** Opens configuration for AI service connections, model routing, and inference hyperparameters.
  - **System-Prompts (`📜`):** Opens configuration for system prompts and default reset capabilities.
  - **System-Backdrop (`🖼️`):** Opens the configuration for the global system background wallpaper.
  - **Zurück zum Hub (`← Zurück zum Hub`):** Returns you directly to the central Hub dashboard at any time.
- **Right Main Area:**
  - Displays the active administration section with responsive wrapping for mobile touch screens.

---

## 👥 User Management (`/admin/users`)

aimo avoids rigid role hierarchies in favor of a **functional permission model**:
- **Create User:** Provision new user accounts with username, email, and initial password.
- **Permission Presets:**
  - `Admin`: Automatically grants all available permissions (Super User).
  - `Creator`: Allows creating, editing, and duplicating characters, lorebooks, WorldInfo settings, and personas, as well as accessing the Creator-Tag collaboration system.
  - `User`: Basic access for roleplay chats and personal persona management.
- **Granular Checkboxes:** Any permission (`character_create`, `chat_access`, `worldinfo_edit`, etc.) can also be granted or revoked individually.
- **Full Access to Creations:** Every administrator can view, edit, and delete all characters, lorebooks, and worlds, even if they are neither the author nor a collaborator.
- **Creator-Tag Privacy & Protection:** A unique UUID4 creator tag is provisioned in the database for every user. Every user can see and copy their own Creator-Tag in **Settings → Account**.
- **Protection for Initial Admin:** The administrator created during first boot cannot be deleted, nor can their permissions be revoked or modified.

---

## 🔌 Service & Model Management (`/admin/services`)

### 1. Ollama Model Management & Setup-Helper
- **Setup-Helper:** Quick overview of the recommended model suite for optimal performance:
  - **Roleplay:** `igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest` (deep conversational nuance and roleplay fidelity)
  - **Memory:** `igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest` (10-message episodic memory and chat title generation)
  - **Assistant:** `gemma4:e4b` (Sparkle writing assistant, translation, ComfyUI image prompts)
  - **Vision:** `gemma4:e4b` (Multimodal vision analysis for portraits and 16:9 backgrounds)
  - **Classification:** `llama3.2:1b` (Ultra-fast post-streaming emotion classification and location change suggestions)
- **One-Click Actions:**
  - `✨ Vorgeschlagene Modelle zuweisen`: Automatically binds the recommended models to all 5 tasks.
  - `⚡ Fehlende installieren`: Sequentially pulls missing recommended models with live download progress.
- **Installed Models:** View all models currently hosted on your Ollama server.
- **Install New Model (Pull):** Enter any model tag or choose a quick shortcut to download it directly onto your Ollama server.
- **Delete Model:** Remove unused models to reclaim disk storage.

### 2. Task-Specific Model Assignments
Route specific duties to specialized models:
- **Roleplay:** Primary model for dialogue, character depiction, and narrative nuance.
- **Classification:** Fast, lightweight model for autonomous post-streaming emotion and location detection.
- **Memory:** Efficient model for 10-message event summaries and tag extraction.
- **Assistant:** Dedicated model for Sparkle assistant, translation, and diffuser prompts.
- **Vision:** Multimodal model for image analysis and persona appearance scans.

### 3. Inference Parameters
- Fine-tune generation hyperparameters:
  - `num_ctx`: Context window size (e.g., 4096, 8192).
  - `temperature`: Creativity and randomness (e.g., 0.7).
  - `top_p` and `repeat_penalty`.

---

## 📜 System-Prompts (`/admin/prompts`)

Manage and customize the system-level instructions that guide AI models across all core tasks.

### Placeholders
In roleplay prompts, dynamic template tags can be inserted:
- `{{char}}`: Dynamically substituted with the active character's name.
- `{{user}}`: Dynamically substituted with the active player persona's name.

### Configurable Prompts
- **Rollenspiel-Prompt:** The foundation prompt governing how the primary roleplay model embodies characters and generates pure dialogue and narrative text.
- **Memory-Prompt:** Directives instructing the memory model on creating concise, episodic summaries and relevant tags every 10 messages.
- **Diffuser-Prompt:** Formulates scenic descriptions into effective visual diffusion prompts for ComfyUI.
- **KI-Autor-Prompt:** Powers the Sparkle assistant (✨) in the character editor to write immersive, third-person descriptive prose based on author notes.
- **Vision-Prompt:** Directs multimodal vision models in extracting physical appearance features from persona portrait images.

### Restoring Defaults
Each prompt section features a **Standard wiederherstellen** button. Clicking it prompts for confirmation and immediately inserts the factory default prompt into the respective editor field. Changes take effect once you click **Prompts speichern**.

---

## 🖼️ System-Backdrop (`/admin/backdrop`)

Configure the global fallback background wallpaper for the application:
- **Upload Wallpaper:** Upload any 16:9 widescreen wallpaper (PNG, JPG, WEBP) to serve as the global atmospheric background across the entire interface.
- **Select from Worlds & Locations:** Quick-pick background art directly from any existing WorldInfo location.
- **Reset:** Revert to the default parchment and wood texture theme at any time.
