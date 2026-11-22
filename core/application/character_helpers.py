from typing import Any
from domain.characters.models import Character, Emotion, EmotionalSprite
from domain.characters.services import CharacterService
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.storage.file_storage import FileStorage


def save_and_persist_sprite(
    character: Character,
    emotion: Emotion | str,
    file_stream: Any,
    filename: str,
    char_service: CharacterService | None = None,
    char_repo: CharacterRepository | None = None,
    storage: FileStorage | None = None,
) -> EmotionalSprite:
    """Orchestrate saving sprite file to storage and persisting its metadata record."""
    if character.id is None:
        raise ValueError("Character must be persisted before adding sprites.")

    char_service = char_service or CharacterService()
    char_repo = char_repo or CharacterRepository()
    storage = storage or FileStorage()

    resolved_emotion = Emotion.resolve(emotion)
    temp_sprite = char_service.add_sprite(character, resolved_emotion, "pending")
    saved_path = storage.save_sprite(
        character_id=character.id,
        content=file_stream,
        filename=filename,
        emotion=resolved_emotion.value,
        variant=temp_sprite.variant,
    )
    temp_sprite.file_path = saved_path
    return char_repo.add_sprite(character.id, temp_sprite)
