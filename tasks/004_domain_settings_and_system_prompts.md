# Task 004: ServiceSettings & Editierbare System-Prompts

## 🎯 Ziel & Umfang
Verwaltung der Systemeinstellungen für externe KI-Dienste (Ollama, ComfyUI, SearXNG, Voice TTS) sowie aller editierbaren System-Prompts und task-spezifischen Hyperparameter.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `domain/settings/`
- **Dateien:**
  - `domain/settings/models.py`
  - `domain/settings/services.py`
  - `domain/settings/exceptions.py`

## 🔗 Abhängigkeiten
- `tasks/001_foundation_config_and_shared_utils.md`

## 📝 Fachliche Vorgaben & Spezifikation

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
  - `roleplay_prompt: str`: Kern-Instruktion für das interaktive Charakter-Rollenspiel (Strikte Regel: Niemals für den User antworten!).
  - `memory_prompt: str`: Extraktions-Prompt für 10-Nachrichten-Zusammenfassungen und Tags.
  - `diffuser_prompt: str`: Konvertiert Szene und Kontext in Stable Diffusion / Flux Prompts für ComfyUI.
  - `sparkle_assistant_prompt: str`: KI-Autor zur Optimierung von Charakterbeschreibungen (*"Du bist ein professioneller Autor..."*).
  - `vision_persona_prompt: str`: Extrahiert Gesichtszüge und äußere Merkmale aus Porträts (ohne Hintergrund/Posen).
- **`ServiceSettings` (Entity):**
  - `id: int`
  - `ollama_url: str`
  - `comfyui_url: str`
  - `searxng_url: str`
  - `searxng_enabled: bool = False` (vorerst TODO)
  - `tasks: TaskAssignment`
  - `params: ModelParameters`
  - `prompts: SystemPrompts`

### 2. `domain/settings/services.py`
- `SettingsService`:
  - `get_default_settings() -> ServiceSettings`: Initialisiert robuste Defaults.
  - `update_service_urls(...) -> ServiceSettings`
  - `update_task_models(...) -> ServiceSettings`
  - `update_parameters(...) -> ServiceSettings`
  - `update_system_prompts(...) -> ServiceSettings`

## ✅ Akzeptanzkriterien
- [x] Vollständige Repräsentation aller Modell-Parameter und System-Prompts.
- [x] Standard-Prompts entsprechen exakt den Vorgaben aus AGENTS.md (inkl. Rollenspiel-Disziplin und Autor-Sparkle).
- [x] Saubere Validierung der Inferenzparameter (z. B. positive Kontextgrößen, plausible Temperatur).
