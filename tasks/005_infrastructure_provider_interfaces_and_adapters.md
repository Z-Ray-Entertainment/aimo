# Task 005: Modular Provider Layer (LLM, ComfyUI, Voice-TTS)

## 🎯 Goal & Scope
Construct abstract provider interfaces and concrete implementations for external AI backends. The core must never couple directly to Ollama or ComfyUI, interacting exclusively through abstract interfaces.

## 📂 Affected Layer & Files
- **Layer:** `infrastructure/`
- **Files:**
  - `infrastructure/llm/interface.py`
  - `infrastructure/llm/factory.py`
  - `infrastructure/llm/ollama.py`
  - `infrastructure/image_gen/interface.py`
  - `infrastructure/image_gen/factory.py`
  - `infrastructure/image_gen/comfyui.py`
  - `infrastructure/voice/interface.py`
  - `infrastructure/voice/factory.py`
  - `infrastructure/voice/stub.py`
  - `infrastructure/storage/file_storage.py`

## 🔗 Dependencies
- `tasks/001_foundation_config_and_shared_utils.md`
- `tasks/004_domain_settings_and_system_prompts.md`

## 📝 Functional Specifications & Requirements

### 1. `infrastructure/llm/`
- **`interface.py` — `LLMProvider` (ABC):**
  - `generate_stream(prompt: str, model: str, params: ModelParameters) -> Iterator[str]`
  - `generate(prompt: str, model: str, params: ModelParameters) -> str`
  - `classify(text: str, candidates: list[str], model: str) -> str`: Fast classification call to extract emotions or location tags.
  - `analyze_image(image_path: Path, prompt: str, model: str) -> str`: Vision extraction for persona portraits and chat uploads.
  - `list_models() -> list[str]`
  - `pull_model(name: str) -> Iterator[dict]`
  - `delete_model(name: str) -> bool`
  - `check_health() -> bool`
- **`ollama.py` — `OllamaLLMProvider(LLMProvider)`:**
  - Concrete HTTP client for `/api/generate`, `/api/tags`, `/api/pull`, `/api/delete`.
  - Robust timeouts and error handling (translating into `InfrastructureError`).
- **`factory.py`:**
  - `get_llm_provider(settings: ServiceSettings) -> LLMProvider`.

### 2. `infrastructure/image_gen/`
- **`interface.py` — `ImageGenProvider` (ABC):**
  - `generate_image(prompt: str, reference_images: list[Path], negative_prompt: str, output_path: Path) -> Path`
  - `cancel_generation(task_id: str) -> None`
  - `check_health() -> bool`
- **`comfyui.py` — `ComfyUIImageGenProvider(ImageGenProvider)`:**
  - Passes diffuser prompts and reference images (portraits, scene backgrounds) to ComfyUI workflow.
  - WebSocket / polling tracking and cancel endpoint.
- **`factory.py`:**
  - `get_image_gen_provider(settings: ServiceSettings) -> ImageGenProvider`.

### 3. `infrastructure/voice/`
- **`interface.py` — `VoiceTTSProvider` (ABC / TODO):**
  - `synthesize_speech(text: str, voice_id: str | None, language: str) -> Path`
  - `list_voices() -> list[dict]`
  - `check_health() -> bool`
- **`stub.py` — `VoiceTTSStubProvider(VoiceTTSProvider)`:**
  - Clean no-op provider returning placeholders until a concrete TTS engine is connected.

### 4. `infrastructure/storage/file_storage.py`
- Manages uploads and paths across the filesystem:
  - Portraits (`uploads/portraits/`)
  - Sprites (`uploads/sprites/<character_id>/`)
  - WorldInfo backgrounds (`uploads/backgrounds/`)
  - Generated images (`uploads/generated/`)
- Validates image formats (PNG, JPG, WEBP).

## ✅ Acceptance Criteria
- [x] Complete abstraction of all external services behind interfaces.
- [x] `OllamaLLMProvider` supports streaming, synchronous generation, vision, and classification.
- [x] `ComfyUIImageGenProvider` supports workflow execution and abortion.
- [x] `VoiceTTSStubProvider` allows clean invocation from the core.
- [x] File storage safely stores and resolves image paths.
