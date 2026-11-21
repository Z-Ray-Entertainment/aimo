from __future__ import annotations

from dataclasses import dataclass

from application.chat_services.task_registry import extract_active_tags
from domain.characters.models import Character
from domain.chat.focus_analyzer import PythonFocusAnalyzer, SceneFocus
from domain.chat.models import ChatSession, MessageRole
from domain.chat.prompt_builder import PromptBuilder
from domain.chat.services import ChatService
from domain.lorebooks.services import LorebookService
from domain.memories.services import MemoryService
from domain.personas.models import UserPersona
from domain.settings.models import ServiceSettings, get_default_prompt, is_default_prompt
from domain.worldinfo.models import Event, Location, WorldInfo
from infrastructure.repositories.chat_repository import ChatRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.memory_repository import MemoryRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository


@dataclass
class AssembledTurnContext:
    assembled_prompt: str
    admin_prompt: str
    available_locations: list[Location]
    effective_num_ctx: int


def _localize_character(character: Character, target_lang: str, trans_repo: TranslationRepository) -> None:
    if character.id is None:
        return
    character.description = trans_repo.get_localized_field(
        "character", character.id, "description", target_lang, character.description
    )
    if character.appearance:
        character.appearance = trans_repo.get_localized_field(
            "character", character.id, "appearance", target_lang, character.appearance
        )
    raw_default_examples = (
        "\n\n".join(
            f"<START>\n{ex['trigger']}\n{ex['response']}" if isinstance(ex, dict) else str(ex)
            for ex in character.dialogue_examples
        )
        if isinstance(character.dialogue_examples, list)
        else str(character.dialogue_examples or "")
    )
    localized_dialogue = trans_repo.get_localized_field(
        "character", character.id, "dialogue_examples", target_lang, raw_default_examples
    )
    if isinstance(localized_dialogue, str):
        if "<START>" in localized_dialogue:
            character.dialogue_examples = [
                f"<START>\n{blk.strip()}"
                for blk in localized_dialogue.split("<START>")
                if blk.strip()
            ]
        else:
            character.dialogue_examples = [
                line.strip() for line in localized_dialogue.splitlines() if line.strip()
            ]
    elif isinstance(localized_dialogue, list):
        character.dialogue_examples = [str(x).strip() for x in localized_dialogue if str(x).strip()]


def assemble_turn_context(
    *,
    session: ChatSession,
    character: Character,
    persona: UserPersona,
    settings: ServiceSettings,
    llm,
    target_lang: str,
    triggered_event: Event | None,
) -> AssembledTurnContext:
    assert session.id is not None
    trans_repo = TranslationRepository()
    wi_repo = WorldInfoRepository()
    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()
    lb_repo = LorebookRepository()

    _localize_character(character, target_lang, trans_repo)

    if persona.id is not None:
        persona.description = trans_repo.get_localized_field(
            "persona", persona.id, "description", target_lang, persona.description
        )
        persona.appearance = trans_repo.get_localized_field(
            "persona", persona.id, "appearance", target_lang, persona.appearance
        )

    worldinfo: WorldInfo | None = (
        wi_repo.get_by_id(session.active_worldinfo_id) if session.active_worldinfo_id else None
    )
    available_locations: list[Location] = (
        [
            loc
            for loc in wi_repo.list_locations(worldinfo.id)
            if loc.character_id is None or loc.character_id == session.character_id
        ]
        if worldinfo and worldinfo.id is not None
        else []
    )
    for avail_loc in available_locations:
        if avail_loc.id is not None:
            avail_loc.name = trans_repo.get_localized_field(
                "worldinfo_location", avail_loc.id, "name", target_lang, avail_loc.name
            )

    current_location = (
        wi_repo.get_location(session.current_location_id) if session.current_location_id else None
    )
    if current_location and current_location.id is not None:
        current_location.name = trans_repo.get_localized_field(
            "worldinfo_location", current_location.id, "name", target_lang, current_location.name
        )
        current_location.description = trans_repo.get_localized_field(
            "worldinfo_location", current_location.id, "description", target_lang, current_location.description
        )

    if triggered_event and triggered_event.id is not None:
        triggered_event.title = trans_repo.get_localized_field(
            "worldinfo_event", triggered_event.id, "title", target_lang, triggered_event.title
        )
        triggered_event.description = trans_repo.get_localized_field(
            "worldinfo_event", triggered_event.id, "description", target_lang, triggered_event.description
        )

    raw_recent = chat_repo.get_messages(session.id, limit=30)
    recent_messages = [
        m for m in raw_recent if m.role in (MessageRole.USER, MessageRole.CHARACTER)
    ][-10:]
    combined_context_text = " ".join(m.effective_text for m in recent_messages[-2:])
    active_tags = extract_active_tags(combined_context_text)
    latest_user_msg = next(
        (m for m in reversed(recent_messages) if m.role == MessageRole.USER),
        None,
    )
    latest_user_text = latest_user_msg.effective_text if latest_user_msg is not None else ""
    latest_user_tags = extract_active_tags(latest_user_text)

    focus_analyzer = PythonFocusAnalyzer()
    scene_focus = focus_analyzer.analyze(
        recent_messages=recent_messages,
        active_tags=active_tags,
        has_triggered_event=(triggered_event is not None),
    )
    focus_keywords = focus_analyzer.get_focus_keywords(scene_focus)

    matched_memories = MemoryService().search_memories_by_tags(
        mem_repo.list_for_session(session.id),
        active_tags,
        latest_tags=latest_user_tags,
        focus_keywords=focus_keywords,
    )

    effective_lb_ids = ChatService().get_effective_lorebook_ids(
        session=session,
        character_lorebook_ids=character.linked_lorebook_ids,
        worldinfo_lorebook_id=worldinfo.lorebook_id if worldinfo else None,
        character_world_conditions=character.lorebook_world_conditions,
    )
    preferred_lb_ids: set[int] | None = None
    if scene_focus == SceneFocus.INTIMACY_BIO and character.linked_lorebook_ids:
        preferred_lb_ids = set(character.linked_lorebook_ids)
    elif scene_focus == SceneFocus.WORLD_EXPLORATION and worldinfo and worldinfo.lorebook_id:
        preferred_lb_ids = {worldinfo.lorebook_id}

    all_lorebook_entries = lb_repo.list_entries_for_lorebooks(effective_lb_ids)
    for lb_entry in all_lorebook_entries:
        if lb_entry.id is not None:
            lb_entry.title = trans_repo.get_localized_field(
                "lorebook_entry", lb_entry.id, "title", target_lang, lb_entry.title
            )
            lb_entry.content = trans_repo.get_localized_field(
                "lorebook_entry", lb_entry.id, "content", target_lang, lb_entry.content
            )
            raw_tags = trans_repo.get_localized_field(
                "lorebook_entry", lb_entry.id, "tags", target_lang, ""
            )
            if raw_tags:
                lb_entry.tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]

    matched_lorebooks = LorebookService().search_entries_by_tags(
        all_lorebook_entries,
        active_tags,
        latest_tags=latest_user_tags,
        focus_keywords=focus_keywords,
        preferred_lorebook_ids=preferred_lb_ids,
    )

    effective_num_ctx = settings.params.num_ctx
    if effective_num_ctx <= 0:
        effective_num_ctx = llm.get_model_context_length(settings.tasks.roleplay_model) or 4096

    raw_rp_prompt = settings.prompts.roleplay_prompt
    if is_default_prompt("roleplay_prompt", raw_rp_prompt):
        resolved_rp_prompt = get_default_prompt("roleplay_prompt", target_lang)
    else:
        resolved_rp_prompt = trans_repo.get_localized_field(
            "system_prompt", 1, "roleplay_prompt", target_lang, raw_rp_prompt
        )

    prompt_builder = PromptBuilder()
    assembled_prompt = prompt_builder.build_roleplay_prompt(
        roleplay_system_prompt=resolved_rp_prompt,
        character=character,
        persona=persona,
        worldinfo=worldinfo,
        current_location=current_location,
        triggered_event=triggered_event,
        recent_messages=recent_messages,
        matched_memories=matched_memories,
        matched_lorebooks=matched_lorebooks,
        available_locations=available_locations,
        relationship_value=session.relationship_value,
        relation_translations=None,
        scene_focus=scene_focus,
        effective_num_ctx=effective_num_ctx,
        thinking_enabled=bool(session.thinking_enabled),
        active_tags=active_tags,
        language=target_lang,
    )
    admin_prompt = (
        f"{prompt_builder.last_budget_report.format_header()}\n\n{assembled_prompt}"
        if prompt_builder.last_budget_report is not None
        else assembled_prompt
    )
    return AssembledTurnContext(
        assembled_prompt=assembled_prompt,
        admin_prompt=admin_prompt,
        available_locations=available_locations,
        effective_num_ctx=effective_num_ctx,
    )
