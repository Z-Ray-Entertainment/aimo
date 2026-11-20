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

### 1. Active AI Backend (Exclusive Selection)
Choose **strictly one** primary AI backend at any time (Ollama and Google AI Cloud are never operated simultaneously):
- **🦙 Ollama (Local / Self-Hosted):** Connect to your Ollama server URL and test reachability directly from the panel.
- **✨ Google AI Cloud (Gemini API):** Enter your Google AI Studio API key (stored masked once saved — leave the input empty to keep the existing key) and click **API-Key & Modelle testen** to verify access and load available cloud models.

### 2. Image Generation & Web Search Services
Depending on your active AI backend, configure image generation and prepared web search options:
- **Image Generation (Chat Magic Wand):**
  - **Google AI Image** *(only available with Google AI active)*: Uses your API key and a Gemini image model (default: `gemini-3.1-flash-image-preview`) to generate 16:9 scenes.
  - **ComfyUI (Local):** Connect to your local ComfyUI server URL.
  - **Deaktiviert:** Hides scene image generation in chat.
- **Web Search (Prepared):**
  - Select **Google Search** *(only available with Google AI active)*, **SearXNG (Local)** with a SearXNG URL, or **Deaktiviert**.

When switching back from Google AI Cloud to Ollama, any Google-specific image or search selection automatically adjusts so local and cloud backends never run in parallel.

### 3. Model Management & Setup-Helper
- **When Ollama is active (Ollama Model Manager):**
  - **Setup-Helper:** Overview of the recommended local models (`igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest`, `gemma4:e4b`, `llama3.2:1b`).
  - **One-Click Actions:** `✨ Vorgeschlagene Modelle zuweisen` binds the recommended models to all 5 roles; `⚡ Fehlende installieren` sequentially pulls missing recommended models with live download progress.
  - **Pull & Delete:** Enter any model tag to download onto your Ollama server, view installed models, and remove unused models.
- **When Google AI Cloud is active (Google AI Cloud Setup):**
  - Displays the API key setup instructions, recommended Gemini models (`gemini-4-hydrogen` and `gemini-3.1-flash-lite` plus `gemini-3.1-flash-image-preview` for images), and the list of cloud models available to your key.

### 4. Task-Specific Model Assignments
Route specific duties to specialized models of the active backend:
- **Roleplay:** Primary model for dialogue, character depiction, and narrative nuance.
- **Classification:** Fast, lightweight model for autonomous post-streaming emotion and location detection.
- **Memory:** Efficient model for 10-message event summaries and tag extraction.
- **Assistant:** Dedicated model for Sparkle assistant, translation, and image scene prompts.
- **Vision:** Multimodal model for image analysis and persona appearance scans.

### 5. Inference Parameters
- Fine-tune generation hyperparameters:
  - `num_ctx`: Context window budget controlling how much conversation history and lore fit into prompts (active for both Ollama and Google AI).
  - `temperature`: Creativity and randomness (e.g., 0.7).
  - `top_p` and `repeat_penalty` (applied to Ollama).

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
- **KI-Autor-Dialog-Prompt:** Guides the AI author in formulating authentic, situational dialogue examples (`{{user}}` trigger and `{{char}}` response) based on the character description.

### Restoring Defaults
Each prompt section features a **Standard wiederherstellen** button. Clicking it prompts for confirmation and immediately inserts the factory default prompt into the respective editor field. Changes take effect once you click **Prompts speichern**.

---

## 🖼️ System-Backdrop (`/admin/backdrop`)

Configure the global fallback background wallpaper for the application:
- **Upload Wallpaper:** Upload any 16:9 widescreen wallpaper (PNG, JPG, WEBP) to serve as the global atmospheric background across the entire interface and as the base fallback in chats (Priority: **System → World → Location**).
- **Select from Worlds & Locations:** Quick-pick background art directly from any existing WorldInfo backdrop or location background.
- **Reset:** Revert to the default parchment and wood texture theme at any time.

### Multi-Language System Prompts & Translation Sync
- Each system prompt displays country-flag pill badges for all 20 supported languages (existing translations appear first; missing languages appear greyed out at the end).
- Clicking any flag badge loads that language's prompt for inspection, manual editing, on-demand **AI Translate**, or deleting the translation (via the trash button next to **AI Translate**) so the background Translation Worker can regenerate it from the English original when needed.
- **Restore Default** resets all languages of that prompt back to the built-in factory defaults.
- **Synchronize Missing Translations:** Starts a dependency-ordered translation run across all customized prompts, characters, worlds, and lorebooks with live progress and a **Cancel** button (especially useful when using Cloud AI providers, where automatic background translation is disabled to protect token quotas).
