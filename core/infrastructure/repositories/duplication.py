from __future__ import annotations

from domain.characters.models import Character, CharacterImage, EmotionalSprite
from domain.lorebooks.models import Lorebook, LorebookEntry
from domain.worldinfo.models import Event, Location, WorldInfo
from infrastructure.database import get_db_session
from infrastructure.repositories.translation_repository import TranslationRepository
from shared.i18n import gettext_noop as _, t


def _get_user_language(target_user_id: int) -> str:
    with get_db_session() as conn:
        u_row = conn.execute(
            "SELECT language FROM users WHERE id = ?",
            (target_user_id,),
        ).fetchone()
    if u_row and u_row["language"]:
        return str(u_row["language"]).strip().lower()[:2] or "en"
    return "en"


def _copy_field_translations(entity_type: str, source_id: int, target_id: int) -> None:
    with get_db_session() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO entity_field_translations (
                entity_type, entity_id, field_name, language, text_content, is_outdated, updated_at
            )
            SELECT entity_type, ?, field_name, language, text_content, is_outdated, updated_at
            FROM entity_field_translations
            WHERE entity_type = ? AND entity_id = ?
            """,
            (target_id, entity_type, source_id),
        )


def duplicate_character_entity(repo, character_id: int, target_user_id: int) -> Character:
    orig = repo.get_by_id(character_id)
    if orig is None:
        raise ValueError(f"Character {character_id} not found.")

    target_lang = _get_user_language(target_user_id)
    trans_repo = TranslationRepository()
    orig_trans = trans_repo.get_entity_translations_map("character", character_id)
    has_target_desc = bool(orig_trans.get("description", {}).get(target_lang, {}).get("text", "").strip())

    copy_name = f"{orig.name} ({t(_('Copy'), target_lang)})"
    clone_origin_lang = target_lang if has_target_desc else (orig.origin_language or "en")
    clone = Character(
        id=None,
        user_id=target_user_id,
        name=copy_name,
        gender=orig.gender,
        visibility="private",
        origin_language=clone_origin_lang,
        collaborator_creator_tags=[],
        primary_portrait_path=orig.primary_portrait_path,
        avatar_path=orig.avatar_path,
        card_image_path=orig.card_image_path,
        appearance=trans_repo.get_localized_field("character", character_id, "appearance", target_lang, orig.appearance),
        description=trans_repo.get_localized_field("character", character_id, "description", target_lang, orig.description),
        dialogue_examples=list(orig.dialogue_examples),
        linked_lorebook_ids=list(orig.linked_lorebook_ids),
        lorebook_world_conditions=dict(orig.lorebook_world_conditions),
        suggested_worldinfo_id=orig.suggested_worldinfo_id,
        first_message=trans_repo.get_localized_field("character", character_id, "first_message", target_lang, orig.first_message),
        initial_location_id=orig.initial_location_id,
        initial_relationship=orig.initial_relationship,
        preferred_location_ids=list(orig.preferred_location_ids),
        disliked_location_ids=list(orig.disliked_location_ids),
        gallery_images=[],
        sprites=[],
    )
    saved = repo.save(clone)
    assert saved.id is not None

    _copy_field_translations("character", character_id, saved.id)

    for img in orig.gallery_images:
        repo.add_gallery_image(
            saved.id,
            CharacterImage(
                id=None,
                character_id=saved.id,
                file_path=img.file_path,
                unlock_threshold=img.unlock_threshold,
            ),
        )
    for sp in orig.sprites:
        repo.add_sprite(
            saved.id,
            EmotionalSprite(
                id=None,
                character_id=saved.id,
                emotion=sp.emotion,
                variant=sp.variant,
                file_path=sp.file_path,
            ),
        )

    with get_db_session() as conn:
        ev_rows = conn.execute(
            """
            SELECT worldinfo_id, location_id, title, probability, one_shot, description,
                   min_relationship, max_relationship, is_proper_noun
            FROM events WHERE character_id = ? ORDER BY id ASC
            """,
            (character_id,),
        ).fetchall()
        for ev in ev_rows:
            conn.execute(
                """
                INSERT INTO events (
                    worldinfo_id, character_id, location_id, title, probability, one_shot, description,
                    min_relationship, max_relationship, is_proper_noun
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ev["worldinfo_id"],
                    saved.id,
                    ev["location_id"],
                    ev["title"],
                    ev["probability"],
                    ev["one_shot"],
                    ev["description"],
                    ev["min_relationship"],
                    ev["max_relationship"],
                    ev["is_proper_noun"] if "is_proper_noun" in ev.keys() else 0,
                ),
            )

    reloaded = repo.get_by_id(saved.id)
    assert reloaded is not None
    return reloaded


def duplicate_worldinfo_entity(repo, worldinfo_id: int, target_user_id: int) -> WorldInfo:
    orig = repo.get_by_id(worldinfo_id)
    if orig is None:
        raise ValueError(f"WorldInfo {worldinfo_id} not found.")

    target_lang = _get_user_language(target_user_id)
    trans_repo = TranslationRepository()
    copy_name = f"{orig.name} ({t(_('Copy'), target_lang)})"

    clone = WorldInfo(
        id=None,
        user_id=target_user_id,
        name=copy_name,
        icon=orig.icon,
        visibility="private",
        origin_language=orig.origin_language or "en",
        cover_image_path=orig.cover_image_path,
        backdrop_image_path=orig.backdrop_image_path,
        lorebook_id=orig.lorebook_id,
        collaborator_creator_tags=[],
        is_proper_noun=orig.is_proper_noun,
    )
    saved = repo.create(clone)
    assert saved.id is not None
    _copy_field_translations("worldinfo", worldinfo_id, saved.id)

    loc_map: dict[int, int] = {}
    for loc in repo.list_locations(worldinfo_id):
        if loc.id is None:
            continue
        saved_loc = repo.add_location(
            Location(
                id=None,
                worldinfo_id=saved.id,
                name=loc.name,
                tags=list(loc.tags),
                description=loc.description,
                background_image_path=loc.background_image_path,
                vision_alt_text=loc.vision_alt_text,
                character_id=loc.character_id,
                is_proper_noun=loc.is_proper_noun,
            )
        )
        assert saved_loc.id is not None
        loc_map[loc.id] = saved_loc.id
        _copy_field_translations("worldinfo_location", loc.id, saved_loc.id)

    for ev in repo.list_events(worldinfo_id):
        mapped_loc_id = loc_map.get(ev.location_id) if ev.location_id is not None else None
        saved_ev = repo.add_event(
            Event(
                id=None,
                worldinfo_id=saved.id,
                title=ev.title,
                probability=ev.probability,
                one_shot=ev.one_shot,
                description=ev.description,
                location_id=mapped_loc_id,
                is_proper_noun=ev.is_proper_noun,
            )
        )
        if ev.id is not None and saved_ev.id is not None:
            _copy_field_translations("worldinfo_event", ev.id, saved_ev.id)

    reloaded = repo.get_by_id(saved.id)
    assert reloaded is not None
    return reloaded


def duplicate_lorebook_entity(repo, lorebook_id: int, target_user_id: int) -> Lorebook:
    orig = repo.get_by_id(lorebook_id)
    if orig is None:
        raise ValueError(f"Lorebook {lorebook_id} not found.")

    target_lang = _get_user_language(target_user_id)
    copy_name = f"{orig.name} ({t(_('Copy'), target_lang)})"
    clone = Lorebook(
        id=None,
        user_id=target_user_id,
        name=copy_name,
        description=orig.description,
        visibility="private",
        origin_language=orig.origin_language or "en",
        collaborator_creator_tags=[],
        is_proper_noun=orig.is_proper_noun,
    )
    saved = repo.create(clone)
    assert saved.id is not None
    _copy_field_translations("lorebook", lorebook_id, saved.id)

    for entry in repo.list_entries(lorebook_id):
        saved_entry = repo.add_entry(
            LorebookEntry(
                id=None,
                lorebook_id=saved.id,
                title=entry.title,
                tags=list(entry.tags),
                content=entry.content,
                visibility=entry.visibility,
                is_proper_noun=entry.is_proper_noun,
            )
        )
        if entry.id is not None and saved_entry.id is not None:
            _copy_field_translations("lorebook_entry", entry.id, saved_entry.id)

    reloaded = repo.get_by_id(saved.id)
    assert reloaded is not None
    return reloaded
