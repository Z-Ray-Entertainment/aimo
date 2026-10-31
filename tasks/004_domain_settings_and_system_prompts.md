# Task 004: ServiceSettings & Editable System Prompts

## 🎯 Goal & Scope
Manage system settings for external AI services (Ollama, ComfyUI, SearXNG, Voice TTS) along with all editable system prompts and task-specific inference hyperparameters.

## 📂 Affected Layer & Files
- **Layer:** `domain/settings/`
- **Files:**
  - `domain/settings/models.py`
  - `domain/settings/services.py`
  - `domain/settings/exceptions.py`

## 🔗 Dependencies
- `tasks/001_foundation_config_and_shared_utils.md`

## 📝 Functional Specifications & Requirements

### 1. `domain/settings/models.py`
- **`ModelParameters` (Value Object):**
  - `num_ctx: int = 4096`
  - `temperature: float = 0.7`
  - `top_p: float = 0.9`
  - `repeat_penalty: float = 1.1`
- **`TaskAssignment` (Value Object):**
  - `roleplay_model: str`
  - `memory_model: str`
  - `assistant_model: str`
  - `vision_model: str`
- **`SystemPrompts` (Entity / Value Object):**
  - `roleplay_prompt: str`: Core instructions for interactive character roleplay (Strict rule: Never speak or act for the user!).
  - `memory_prompt: str`: Extraction prompt for 10-message summaries and tags.
  - `diffuser_prompt: str`: Converts scene context into Stable Diffusion / Flux prompts for ComfyUI.
  - `sparkle_assistant_prompt: str`: AI author for enhancing character descriptions (*"You are a professional author..."*).
  - `vision_persona_prompt: str`: Extracts facial features and physical appearance from portraits (ignoring background/poses).
- **`ServiceSettings` (Entity):**
  - `id: int`
  - `ollama_url: str`
  - `comfyui_url: str`
  - `searxng_url: str`
  - `searxng_enabled: bool = False` (currently TODO)
  - `tasks: TaskAssignment`
  - `params: ModelParameters`
  - `prompts: SystemPrompts`

### 2. `domain/settings/services.py`
- `SettingsService`:
  - `get_default_settings() -> ServiceSettings`: Initializes robust defaults.
  - `update_service_urls(...) -> ServiceSettings`
  - `update_task_models(...) -> ServiceSettings`
  - `update_parameters(...) -> ServiceSettings`
  - `update_system_prompts(...) -> ServiceSettings`

## ✅ Acceptance Criteria
- [x] Complete representation of all model parameters and system prompts.
- [x] Standard prompts strictly adhere to specifications from AGENTS.md (including roleplay discipline and author sparkle).
- [x] Clean validation of inference parameters (e.g., positive context window size, plausible temperature).
