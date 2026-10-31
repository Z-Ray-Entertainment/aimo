# Task 009: AI Characters, Emotions & Gallery Images

## 🎯 Goal & Scope
Domain modeling for AI characters including Gender enum, 28-value Emotion enum with variant naming (`_[number]`), unlockable 9:16 gallery images with affection thresholds (-100 to +100), location preferences, and First Message.

## 📂 Affected Layer & Files
- **Layer:** `domain/characters/`
- **Files:**
  - `domain/characters/models.py`
  - `domain/characters/services.py`
  - `domain/characters/exceptions.py`

## 🔗 Dependencies
- `tasks/001_foundation_config_and_shared_utils.md`
- `tasks/006_domain_personas_and_vision_analysis.md` (Gender Enum)
- `tasks/008_domain_worldinfo_locations_and_events.md` (Location)

## 📝 Functional Specifications & Requirements

### 1. `domain/characters/models.py`
- **`Gender` (Enum):** `male`, `female`, `non-binary`.
- **`Emotion` (Enum):**
  - 28 fixed values: `admire`, `amused`, `anger`, `annoyed`, `approval`, `caring`, `confused`, `curious`, `desire`, `disappointed`, `disapproval`, `disgust`, `embarrassed` (alias `emberassed`), `excited`, `fear`, `gratitude`, `grief`, `joy`, `love`, `nervousness`, `neutral` (**Default & Fallback**), `optimistic`, `pride`, `realize`, `relief` (alias `relife`), `remorse`, `sad`, `surprise` (alias `suprise`).
- **`EmotionalSprite` (Value Object):**
  - `emotion: Emotion`
  - `variant: int` (suffix `_[number]`, e.g., `joy_1.png`, `joy_2.webp`)
  - `file_path: str`
- **`CharacterImage` (Entity / Value Object):**
  - `id: int | None`
  - `character_id: int`
  - `file_path: str` (portrait 9:16)
  - `unlock_threshold: int` (-100 to +100)
- **`Character` (Entity):**
  - `id: int | None`
  - `user_id: int`
  - `name: str`
  - `gender: Gender`
  - `visibility: str = "private"` (`private` or `public`)
  - `primary_portrait_path: str` (mandatory field)
  - `description: str` (personality, speech mannerisms)
  - `dialogue_examples: list[str]`
  - `linked_lorebook_ids: list[int]`
  - `suggested_worldinfo_id: int | None` (recommendation)
  - `first_message: str` (welcome message)
  - `initial_location_id: int | None`
  - `initial_relationship: int = 0` (-100 to +100)
  - `preferred_location_ids: list[int]`
  - `disliked_location_ids: list[int]`
  - `gallery_images: list[CharacterImage]`
  - `sprites: list[EmotionalSprite]`

### 2. `domain/characters/services.py`
- **`CharacterService`:**
  - `create_character(...) -> Character`
  - `update_character(...) -> Character`
  - `add_gallery_image(character: Character, file_path: str, threshold: int) -> CharacterImage`
  - `add_sprite(character: Character, emotion: Emotion, file_path: str) -> EmotionalSprite`:
    - Automatically determines the next available variant number for this emotion.
  - `delete_sprite(character: Character, emotion: Emotion, variant: int) -> None`
  - `select_sprite_for_emotion(character: Character, detected_emotion: Emotion) -> EmotionalSprite`:
    - Looks up all sprites for the detected emotion.
    - Selects **one variant at random**.
    - If no sprite exists for this emotion, falls back to `neutral` (or `neutral_1`).
  - `get_unlocked_images(character: Character, relationship_value: float) -> list[CharacterImage]`:
    - Filters gallery images where `relationship_value >= image.unlock_threshold`.

### 3. `domain/characters/exceptions.py`
- `CharacterNotFoundError`, `InvalidCharacterDataError`.

## ✅ Acceptance Criteria
- [x] All 28 emotions typed in enum; `neutral` configured as explicit fallback.
- [x] Random sprite variant selection with fallback to `neutral`.
- [x] Gallery images have thresholds bounded between -100 and +100.
- [x] Visibility (`private`/`public`) and First Message with initial location implemented.
