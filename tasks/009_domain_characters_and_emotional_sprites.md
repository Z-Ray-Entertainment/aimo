# Task 009: KI-Charaktere, Emotionen & Galeriebilder

## 🎯 Ziel & Umfang
Domänenmodellierung für KI-Charaktere inklusive Geschlechts-Enum, 28-stufigem Emotions-Enum mit Varianten-Naming (`_[nummer]`), freischaltbaren 9:16-Galeriebildern mit Schwellenwerten (-100 bis +100), Ortspräferenzen und First Message.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `domain/characters/`
- **Dateien:**
  - `domain/characters/models.py`
  - `domain/characters/services.py`
  - `domain/characters/exceptions.py`

## 🔗 Abhängigkeiten
- `tasks/001_foundation_config_and_shared_utils.md`
- `tasks/006_domain_personas_and_vision_analysis.md` (Gender Enum)
- `tasks/008_domain_worldinfo_locations_and_events.md` (Location)

## 📝 Fachliche Vorgaben & Spezifikation

### 1. `domain/characters/models.py`
- **`Gender` (Enum):** `male`, `female`, `non-binary`.
- **`Emotion` (Enum):**
  - Feste 28 Werte: `admire`, `amused`, `anger`, `annoyed`, `approval`, `caring`, `confused`, `curious`, `desire`, `disappointed`, `disapproval`, `disgust`, `embarrassed` (alias `emberassed`), `excited`, `fear`, `gratitude`, `grief`, `joy`, `love`, `nervousness`, `neutral` (**Default & Fallback**), `optimistic`, `pride`, `realize`, `relief` (alias `relife`), `remorse`, `sad`, `surprise` (alias `suprise`).
- **`EmotionalSprite` (Value Object):**
  - `emotion: Emotion`
  - `variant: int` (Suffix `_[nummer]`, z. B. `joy_1.png`, `joy_2.webp`)
  - `file_path: str`
- **`CharacterImage` (Entity / Value Object):**
  - `id: int | None`
  - `character_id: int`
  - `file_path: str` (Hochformat 9:16)
  - `unlock_threshold: int` (-100 bis +100)
- **`Character` (Entity):**
  - `id: int | None`
  - `user_id: int`
  - `name: str`
  - `gender: Gender`
  - `visibility: str = "private"` (`private` oder `public`)
  - `primary_portrait_path: str` (Pflichtfeld)
  - `description: str` (Persönlichkeit, Sprechweise)
  - `dialogue_examples: list[str]`
  - `linked_lorebook_ids: list[int]`
  - `suggested_worldinfo_id: int | None` (Empfehlung)
  - `first_message: str` (Welcome Message)
  - `initial_location_id: int | None`
  - `initial_relationship: int = 0` (-100 bis +100)
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
    - Ermittelt automatisch die nächste freie Variantennummer für diese Emotion.
  - `delete_sprite(character: Character, emotion: Emotion, variant: int) -> None`
  - `select_sprite_for_emotion(character: Character, detected_emotion: Emotion) -> EmotionalSprite`:
    - Sucht alle Sprites für die erkannte Emotion.
    - Wählt **zufällig eine Variante** aus.
    - Liegt kein Sprite für diese Emotion vor, fällt die Auswahl auf `neutral` (bzw. `neutral_1`) zurück.
  - `get_unlocked_images(character: Character, relationship_value: float) -> list[CharacterImage]`:
    - Filtert Galeriebilder, bei denen `relationship_value >= image.unlock_threshold` ist.

### 3. `domain/characters/exceptions.py`
- `CharacterNotFoundError`, `InvalidCharacterDataError`.

## ✅ Akzeptanzkriterien
- [ ] Alle 28 Emotionen im Enum typisiert; `neutral` ist definierter Fallback.
- [ ] Zufällige Sprite-Variantenauswahl mit Fallback auf `neutral`.
- [ ] Galeriebilder besitzen Schwellenwerte im Bereich -100 bis +100.
- [ ] Sichtbarkeit (`private`/`public`) und First Message mit Initialort sind implementiert.
