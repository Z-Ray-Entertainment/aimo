from __future__ import annotations

import logging
import threading

from domain.memories.services import MemoryService
from domain.settings.models import get_default_prompt, is_default_prompt
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.chat_repository import ChatRepository
from infrastructure.repositories.memory_repository import MemoryRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.user_repository import UserRepository
from shared.llm_activity import interactive_llm_guard

logger = logging.getLogger(__name__)


def resolve_memory_prompt(settings, user_lang: str) -> str:
    raw_mem_prompt = settings.prompts.memory_prompt
    if is_default_prompt("memory_prompt", raw_mem_prompt):
        return get_default_prompt("memory_prompt", user_lang)
    return TranslationRepository().get_localized_field(
        "system_prompt", 1, "memory_prompt", user_lang, raw_mem_prompt
    )


def run_async_memory_extraction(session_id: int) -> None:
    def _worker() -> None:
        try:
            chat_repo = ChatRepository()
            mem_repo = MemoryRepository()
            settings_repo = SettingsRepository()
            mem_service = MemoryService()

            chat_session = chat_repo.get_session(session_id)
            if chat_session is None:
                return

            all_messages = chat_repo.get_messages(session_id, limit=None)
            narrative_msgs = mem_service.filter_narrative_messages(all_messages)
            existing_memories = mem_repo.list_for_session(session_id)
            last_mem_idx = max((m.message_idx for m in existing_memories), default=0)
            unsummarized = [m for m in narrative_msgs if m.message_idx > last_mem_idx]

            if not mem_service.should_generate_memory(len(unsummarized)):
                return

            chunk = unsummarized[:10]
            target_idx = chunk[-1].message_idx
            settings = settings_repo.get_settings()
            llm = get_llm_provider(settings)

            session_user = UserRepository().get_by_id(chat_session.user_id)
            user_lang = (session_user.language if session_user and session_user.language else "en")[:2].lower()
            resolved_mem_prompt = resolve_memory_prompt(settings, user_lang)

            msg_dicts = [
                {"role": m.role.value, "content": m.localized_content or m.english_content or ""}
                for m in chunk
            ]
            with interactive_llm_guard():
                title, tags, summary, new_chat_title = mem_service.extract_memory_and_title(
                    last_10_messages=msg_dicts,
                    memory_prompt=resolved_mem_prompt,
                    llm_provider=llm,
                    model=settings.tasks.memory_model,
                    params=settings.params,
                )
            memory = mem_service.create_memory(
                chat_session_id=session_id,
                message_idx=target_idx,
                title=title,
                tags=tags,
                summary=summary,
            )
            mem_repo.add_memory(memory)

            if new_chat_title:
                chat_session.title = new_chat_title
                chat_repo.update_session(chat_session)
        except Exception as exc:
            logger.exception("Background memory generation failed for session %s: %s", session_id, exc)

    threading.Thread(target=_worker, daemon=True).start()
