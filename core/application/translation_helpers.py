from __future__ import annotations

from domain.characters.models import Character
from domain.lorebooks.models import Lorebook
from domain.worldinfo.models import WorldInfo
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository


def is_worldinfo_ready_for_language(
    worldinfo: WorldInfo,
    language: str,
    trans_repo: TranslationRepository,
    wi_repo: WorldInfoRepository,
) -> bool:
    if worldinfo.id is None:
        return False
    olang = getattr(worldinfo, "origin_language", "en") or "en"
    for loc in wi_repo.list_locations(worldinfo.id):
        if loc.id is not None and loc.character_id is None:
            loc_fields = [("description", loc.description)]
            if not getattr(loc, "is_proper_noun", False):
                loc_fields.insert(0, ("name", loc.name))
            if not trans_repo.is_entity_ready_for_language(
                "worldinfo_location",
                loc.id,
                language,
                loc_fields,
                origin_language=olang,
            ):
                return False
    for ev in wi_repo.list_events(worldinfo.id):
        if ev.id is not None and ev.character_id is None:
            ev_fields = [("description", ev.description)]
            if not getattr(ev, "is_proper_noun", False):
                ev_fields.insert(0, ("title", ev.title))
            if not trans_repo.is_entity_ready_for_language(
                "worldinfo_event",
                ev.id,
                language,
                ev_fields,
                origin_language=olang,
            ):
                return False
    return True


def is_lorebook_ready_for_language(
    lorebook: Lorebook,
    language: str,
    trans_repo: TranslationRepository,
) -> bool:
    if lorebook.id is None:
        return False
    olang = getattr(lorebook, "origin_language", "en") or "en"
    lb_fields = [("description", lorebook.description)]
    if not getattr(lorebook, "is_proper_noun", False):
        lb_fields.insert(0, ("name", lorebook.name))
    return trans_repo.is_entity_ready_for_language(
        "lorebook",
        lorebook.id,
        language,
        lb_fields,
        origin_language=olang,
    )


def is_character_ready_for_language(
    character: Character,
    language: str,
    trans_repo: TranslationRepository,
    wi_repo: WorldInfoRepository,
) -> bool:
    if character.id is None:
        return False
    olang = getattr(character, "origin_language", "en") or "en"
    required = [
        ("description", character.description),
        ("appearance", getattr(character, "appearance", "")),
        ("first_message", character.first_message),
    ]
    if not trans_repo.is_entity_ready_for_language(
        "character", character.id, language, required, origin_language=olang
    ):
        return False
    if character.suggested_worldinfo_id is not None:
        wi = wi_repo.get_by_id(character.suggested_worldinfo_id)
        if wi is not None and not is_worldinfo_ready_for_language(wi, language, trans_repo, wi_repo):
            return False
    return True
