# Task 006: Player Personas & Vision Appearance Analysis

## 🎯 Goal & Scope
Management of player personas (the user's identity in roleplay) including automated appearance extraction via Vision models and deletion protection for personas active in chat sessions.

## 📂 Affected Layer & Files
- **Layer:** `domain/personas/`
- **Files:**
  - `domain/personas/models.py`
  - `domain/personas/services.py`
  - `domain/personas/exceptions.py`

## 🔗 Dependencies
- `tasks/001_foundation_config_and_shared_utils.md`
- `tasks/005_infrastructure_provider_interfaces_and_adapters.md`

## 📝 Functional Specifications & Requirements

### 1. `domain/personas/models.py`
- **`Gender` (Enum):**
  - `MALE = "male"`
  - `FEMALE = "female"`
  - `NON_BINARY = "non-binary"`
- **`UserPersona` (Entity):**
  - `id: int | None`
  - `user_id: int`
  - `name: str`
  - `gender: Gender`
  - `portrait_path: str` (visual reference image)
  - `description: str` (backstory, personality traits)
  - `appearance: str` (textual description of physical features)
  - `is_default: bool = False` (default persona for header button)
  - `created_at: datetime`

### 2. `domain/personas/services.py`
- **`PersonaService`:**
  - `create_persona(user_id: int, name: str, gender: Gender, portrait_path: str, description: str, appearance: str = "", is_default: bool = False) -> UserPersona`
  - `update_persona(persona: UserPersona, name: str, gender: Gender, portrait_path: str, description: str, appearance: str) -> UserPersona`
  - `analyze_appearance(persona: UserPersona, vision_provider: LLMProvider, vision_model: str, prompt: str) -> str`:
    - Calls `vision_provider.analyze_image()` with the portrait image.
    - **Focus Rule:** Extracts facial features, hair, complexion, physique. Image backgrounds and situational poses are ignored.
    - Updates `persona.appearance`.
  - `delete_persona(persona: UserPersona, has_active_chats: bool) -> None`:
    - **Deletion Lock:** If `has_active_chats == True`, raises `PersonaInUseError`.
  - `set_default_persona(user_id: int, persona_id: int) -> None`

### 3. `domain/personas/exceptions.py`
- `PersonaNotFoundError`, `InvalidPersonaDataError`, `PersonaInUseError`.

## ✅ Acceptance Criteria
- [x] Complete domain logic for personas with `Gender` enum.
- [x] Automated Vision analysis populates appearance without backgrounds/poses.
- [x] Deletion protection reliably triggers if persona is referenced in chats.
- [x] Manually edited appearance descriptions remain preserved.
