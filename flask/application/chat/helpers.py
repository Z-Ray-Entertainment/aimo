from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, has_perm, is_admin as is_admin_user, require_permission
from application.chat.forms import MemoryEditForm, StartChatForm
from application.translation_helpers import is_worldinfo_ready_for_language
from application.ui_helpers import tr
from i18n import gettext_noop as _
from domain.characters.models import Emotion
from domain.characters.services import CharacterService
from domain.chat.models import MessageRole
from domain.chat.services import ChatService
from domain.memories.services import MemoryService
from domain.permissions.models import FunctionPermission
from domain.personas.models import Gender
from domain.personas.services import PersonaService
from infrastructure.image_gen.factory import get_image_gen_provider
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.chat_repository import ChatRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.memory_repository import MemoryRepository
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.relationship_repository import RelationshipRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from shared.exceptions import AimoError
from shared.utils import replace_roleplay_placeholders


def _get_user_system_language() -> str:
    user = get_current_user()
    if user is not None and user.language:
        return user.language
    cookie_lang = request.cookies.get("aimo_sys_lang", "").strip().lower()[:2]
    if cookie_lang in ("de", "en", "fr", "es", "it", "ja"):
        return cookie_lang
    best = request.accept_languages.best_match(["de", "en", "fr", "es", "it", "ja"])
    return best if best else "de"


def _build_lorebook_view_data(user_id: int, character, worldinfo=None, chat_session=None, is_admin: bool = False):
    lb_repo = LorebookRepository()
    wi_repo = WorldInfoRepository()
    all_visible = lb_repo.list_visible(user_id)
    all_map = {lb.id: lb for lb in all_visible if lb.id is not None}

    def _format_item(
        lb,
        source: str,
        is_active: bool = True,
        is_locked: bool = False,
        required_worldinfo_id: int | None = None,
        required_worldinfo_name: str | None = None,
    ):
        entries = lb_repo.list_entries(lb.id, user_id=user_id, is_admin=is_admin) if lb.id else []
        all_tags: set[str] = set()
        for e in entries:
            all_tags.update(e.tags)
        is_private_to_user = (lb.user_id != user_id and not is_admin and lb.visibility == "private")
        return {
            "id": lb.id,
            "name": lb.name,
            "description": lb.description,
            "tags": sorted(all_tags),
            "entry_count": len(entries),
            "source": source,
            "is_active": is_active,
            "is_locked": is_locked,
            "required_worldinfo_id": required_worldinfo_id,
            "required_worldinfo_name": required_worldinfo_name,
            "is_private_to_user": is_private_to_user,
        }

    char_lb_ids = set(character.linked_lorebook_ids) if character else set()
    wi_lb_id = worldinfo.lorebook_id if (worldinfo and worldinfo.lorebook_id) else None
    char_conditions = getattr(character, "lorebook_world_conditions", {}) or {}

    default_ids = set(char_lb_ids)
    if wi_lb_id:
        default_ids.add(wi_lb_id)

    disabled_ids = set(chat_session.disabled_lorebook_ids) if chat_session else set()
    custom_ids = list(chat_session.custom_lorebook_ids) if chat_session else []

    active_wi_id = worldinfo.id if worldinfo else (chat_session.active_worldinfo_id if chat_session else None)

    default_lorebooks = []
    for lb_id in sorted(default_ids):
        lb = all_map.get(lb_id) or lb_repo.get_by_id(lb_id)
        if lb:
            in_char = lb_id in char_lb_ids
            in_wi = lb_id == wi_lb_id
            if in_char and in_wi:
                source = "Charakter & Welt"
            elif in_char:
                source = "Charakter"
            else:
                source = "Welt"

            is_locked = False
            req_wi_id = None
            req_wi_name = None
            if in_char and lb_id in char_conditions:
                req_wi_id = char_conditions[lb_id]
                req_wi = wi_repo.get_by_id(req_wi_id)
                req_wi_name = req_wi.name if req_wi else f"Welt #{req_wi_id}"
                if active_wi_id != req_wi_id:
                    is_locked = True

            if is_locked:
                is_active = False
            else:
                is_active = lb.id not in disabled_ids

            default_lorebooks.append(
                _format_item(
                    lb,
                    source,
                    is_active=is_active,
                    is_locked=is_locked,
                    required_worldinfo_id=req_wi_id,
                    required_worldinfo_name=req_wi_name,
                )
            )

    default_lorebooks.sort(key=lambda x: x["name"].lower())

    custom_lorebooks = []
    for lb_id in custom_ids:
        if lb_id in default_ids:
            continue
        lb = all_map.get(lb_id) or lb_repo.get_by_id(lb_id)
        if lb:
            is_active = lb.id not in disabled_ids
            custom_lorebooks.append(_format_item(lb, "Benutzerdefiniert", is_active=is_active))

    custom_lorebooks.sort(key=lambda x: x["name"].lower())

    active_in_session_ids = default_ids.union(custom_ids)
    available_lorebooks = []
    for lb in sorted(all_visible, key=lambda x: x.name.lower()):
        entries = lb_repo.list_entries(lb.id, user_id=user_id, is_admin=is_admin) if lb.id else []
        all_tags: set[str] = set()
        for e in entries:
            all_tags.update(e.tags)
        available_lorebooks.append({
            "id": lb.id,
            "name": lb.name,
            "description": lb.description,
            "tags": sorted(all_tags),
            "entry_count": len(entries),
            "is_added": lb.id in active_in_session_ids,
        })

    active_count = len([x for x in default_lorebooks if x["is_active"]]) + len(
        [x for x in custom_lorebooks if x["is_active"]]
    )

    return {
        "default_lorebooks": default_lorebooks,
        "custom_lorebooks": custom_lorebooks,
        "available_lorebooks": available_lorebooks,
        "active_count": active_count,
    }
