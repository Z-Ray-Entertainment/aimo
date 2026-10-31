# 🛡️ Administration & Settings

[← Back to Overview](README.md) | [← The Chat Interface](chat.md)

The Admin Panel is reserved for users holding the `ADMIN_ACCESS` permission. Here, you manage user accounts, assign functional permissions, and configure local AI models.

---

## 👥 User Management (`/admin/users`)

aimo avoids rigid role hierarchies in favor of a **functional permission model**:
- **Create User:** Provision new user accounts with username, email, and initial password.
- **Permission Presets:**
  - `Admin`: Automatically grants all available permissions (Super User).
  - `Creator`: Allows creating and editing characters, lorebooks, WorldInfo settings, and personas.
  - `User`: Basic access for roleplay chats and personal persona management.
- **Granular Checkboxes:** Any permission (`character_create`, `chat_access`, `worldinfo_edit`, etc.) can also be granted or revoked individually.
- **Protection for Initial Admin:** The administrator created during first boot cannot be deleted, nor can their permissions be revoked or modified.

---

## 🔌 Service & Model Management (`/admin/services`)

### 1. Ollama Model Management
- **Installed Models:** View all models currently hosted on your Ollama server.
- **Install New Model (Pull):** Enter a model tag (e.g., `llama3:8b`, `qwen2.5:7b`) to download it directly through the web UI onto your Ollama server.
- **Delete Model:** Remove unused models to reclaim disk storage.

### 2. Task-Specific Model Assignments
Route specific duties to specialized models:
- **Roleplay:** Your premier model for dialogue, character depiction, and narrative nuance.
- **Memory:** A fast, efficient model for 10-message event summaries and tag extraction.
- **Assistant:** Model for tool calling, translation, and coordination.
- **Vision:** Multimodal model (e.g., `llava`, `llama3.2-vision`) for image analysis and persona appearance scans.

### 3. Inference Parameters & System Prompts
- Fine-tune generation hyperparameters:
  - `num_ctx`: Context window size (e.g., 4096, 8192).
  - `temperature`: Creativity and randomness (e.g., 0.7).
  - `top_p` and `repeat_penalty`.
- **Edit System Prompts:** Directly customize base system directives for Roleplay, Memory extraction, ComfyUI prompt diffusion, and the Sparkle Writing Assistant ✨.
