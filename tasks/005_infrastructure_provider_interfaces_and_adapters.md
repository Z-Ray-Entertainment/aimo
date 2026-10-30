# Task 005: Modulare Provider-Schicht (LLM, ComfyUI, Voice-TTS)

## 🎯 Ziel & Umfang
Erstellung der abstrakten Provider-Schnittstellen und konkreten Implementierungen für externe KI-Backends. Der Kern darf niemals direkt an Ollama oder ComfyUI gekoppelt sein, sondern interagiert ausschließlich über die abstrakten Interfaces.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `infrastructure/`
- **Dateien:**
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

## 🔗 Abhängigkeiten
- `tasks/001_foundation_config_and_shared_utils.md`
- `tasks/004_domain_settings_and_system_prompts.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. `infrastructure/llm/`
- **`interface.py` — `LLMProvider` (ABC):**
  - `generate_stream(prompt: str, model: str, params: ModelParameters) -> Iterator[str]`
  - `generate(prompt: str, model: str, params: ModelParameters) -> str`
  - `classify(text: str, candidates: list[str], model: str) -> str`: Schneller Klassifikations-Call zur Extraktion von Emotionen oder Ortstags.
  - `analyze_image(image_path: Path, prompt: str, model: str) -> str`: Vision-Extraktion für Persona-Porträts und Chat-Uploads.
  - `list_models() -> list[str]`
  - `pull_model(name: str) -> Iterator[dict]`
  - `delete_model(name: str) -> bool`
  - `check_health() -> bool`
- **`ollama.py` — `OllamaLLMProvider(LLMProvider)`:**
  - Konkrete HTTP-Anbindung an `/api/generate`, `/api/tags`, `/api/pull`, `/api/delete`.
  - Robuste Timeouts und Exception-Handling (Übersetzung in `InfrastructureError`).
- **`factory.py`:**
  - `get_llm_provider(settings: ServiceSettings) -> LLMProvider`.

### 2. `infrastructure/image_gen/`
- **`interface.py` — `ImageGenProvider` (ABC):**
  - `generate_image(prompt: str, reference_images: list[Path], negative_prompt: str, output_path: Path) -> Path`
  - `cancel_generation(task_id: str) -> None`
  - `check_health() -> bool`
- **`comfyui.py` — `ComfyUIImageGenProvider(ImageGenProvider)`:**
  - Übergibt Diffuser-Prompt und Referenzbilder (Porträts, Ortshintergrund) an ComfyUI-Workflow.
  - Websocket-/Polling-Überwachung und Cancel-Endpunkt.
- **`factory.py`:**
  - `get_image_gen_provider(settings: ServiceSettings) -> ImageGenProvider`.

### 3. `infrastructure/voice/`
- **`interface.py` — `VoiceTTSProvider` (ABC / TODO):**
  - `synthesize_speech(text: str, voice_id: str | None, language: str) -> Path`
  - `list_voices() -> list[dict]`
  - `check_health() -> bool`
- **`stub.py` — `VoiceTTSStubProvider(VoiceTTSProvider)`:**
  - Platzhalter, der saubere No-Op-Rückgaben liefert, bis eine konkrete TTS-Engine angebunden wird.

### 4. `infrastructure/storage/file_storage.py`
- Verwaltet Uploads und Dateipfade im Dateisystem:
  - Porträts (`uploads/portraits/`)
  - Sprites (`uploads/sprites/<character_id>/`)
  - WorldInfo-Hintergründe (`uploads/backgrounds/`)
  - Generierte Bilder (`uploads/generated/`)
- Validierung von Bildformaten (PNG, JPG, WEBP).

## ✅ Akzeptanzkriterien
- [ ] Vollständige Abstraktion aller externen Services über Interfaces.
- [ ] `OllamaLLMProvider` unterstützt Streaming, synchrone Generierung, Vision und Klassifikation.
- [ ] `ComfyUIImageGenProvider` unterstützt Workflow-Aufruf und Abbrechen.
- [ ] `VoiceTTSStubProvider` ermöglicht es dem Kern, TTS sauber aufzurufen.
- [ ] Datei-Storage speichert und liefert Bildpfade organisiert und sicher ab.
