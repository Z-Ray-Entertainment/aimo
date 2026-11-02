# 🛡️ Administration & Settings

[← Back to Overview](README.md) | [← The Chat Interface](chat.md)

The Admin Panel is reserved for users holding the `ADMIN_ACCESS` permission. Here, you manage user accounts, assign functional permissions, and configure local AI models.

---

## 👥 User Management (`/admin/users`)

aimo avoids rigid role hierarchies in favor of a **functional permission model**:
- **Create User:** Provision new user accounts with username, email, and initial password.
- **Permission Presets:**
  - `Admin`: Automatically grants all available permissions (Super User).
  - `Creator`: Allows creating, editing, and duplicating characters, lorebooks, WorldInfo settings, and personas, as well as accessing the Creator-Tag collaboration system.
  - `User`: Basic access for roleplay chats and personal persona management.
- **Granular Checkboxes:** Any permission (`character_create`, `chat_access`, `worldinfo_edit`, etc.) can also be granted or revoked individually.
- **Creator-Tag Privacy & Protection:** A unique UUID4 creator tag is provisioned in the database for every user. The UI displays the Creator-Tag only to accounts possessing active creator permissions.
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

### 3. Inference Parameters & System Prompts
- Fine-tune generation hyperparameters:
  - `num_ctx`: Context window size (e.g., 4096, 8192).
  - `temperature`: Creativity and randomness (e.g., 0.7).
  - `top_p` and `repeat_penalty`.
- **Edit System Prompts:** Directly customize base system directives for Roleplay, Memory extraction, ComfyUI prompt diffusion, and the Sparkle Writing Assistant ✨.
