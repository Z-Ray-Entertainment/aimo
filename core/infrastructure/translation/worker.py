from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone

from domain.settings.models import PROMPT_KEYS, is_default_prompt
from domain.translation.services import TranslationService
from infrastructure.llm.factory import get_llm_provider, get_llm_provider_class
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository


class BackgroundTranslationWorker:
    def __init__(self, is_busy_fn: Callable[[], bool] | None = None) -> None:
        self._is_busy_fn = is_busy_fn or (lambda: False)
        self._wake_event = threading.Event()
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._manual_requested = False
        self._running = False
        self._paused = False
        self._completed = 0
        self._total = 0
        self._current_item = ""
        self._current_type = ""
        self._current_title = ""
        self._current_language = ""
        self._last_error = ""
        self._last_finished_at: str | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run_loop,
                name="aimo-translation-worker",
                daemon=True,
            )
            self._thread.start()
        self.trigger_sync(manual=False)

    def trigger_sync(self, manual: bool = False) -> bool:
        settings = SettingsRepository().get_settings()
        llm_cls = get_llm_provider_class(settings.llm_backend)
        if not manual and llm_cls.is_cloud_provider():
            return False
        with self._lock:
            if manual:
                self._manual_requested = True
            self._cancel_event.clear()
        self._wake_event.set()
        return True

    def cancel_sync(self) -> None:
        self._cancel_event.set()

    def get_status(self) -> dict:
        settings = SettingsRepository().get_settings()
        llm_cls = get_llm_provider_class(settings.llm_backend)
        with self._lock:
            return {
                "running": self._running,
                "paused": self._paused,
                "manual": self._manual_requested,
                "is_cloud": llm_cls.is_cloud_provider(),
                "completed": self._completed,
                "total": self._total,
                "current_item": self._current_item,
                "current_type": self._current_type,
                "current_title": self._current_title,
                "current_language": self._current_language,
                "last_error": self._last_error,
                "last_finished_at": self._last_finished_at,
            }

    def _run_loop(self) -> None:
        while True:
            self._wake_event.wait(timeout=300.0)
            self._wake_event.clear()

            with self._lock:
                manual = self._manual_requested

            settings = SettingsRepository().get_settings()
            llm_cls = get_llm_provider_class(settings.llm_backend)
            if not manual and llm_cls.is_cloud_provider():
                continue

            model = (settings.tasks.assistant_model or settings.tasks.roleplay_model or "").strip()
            if not model:
                continue

            try:
                self._execute_cycle(settings, model)
            except Exception as exc:
                with self._lock:
                    self._last_error = str(exc)
            finally:
                with self._lock:
                    self._running = False
                    self._paused = False
                    self._manual_requested = False
                    self._current_item = ""
                    self._current_type = ""
                    self._current_title = ""
                    self._current_language = ""
                    self._last_finished_at = datetime.now(timezone.utc).isoformat()

    def _wait_if_busy(self) -> bool:
        while not self._cancel_event.is_set():
            if not self._is_busy_fn():
                with self._lock:
                    self._paused = False
                return True
            with self._lock:
                self._paused = True
            time.sleep(1.0)
        with self._lock:
            self._paused = False
        return False

    def _execute_cycle(self, settings, model: str) -> None:
        user_repo = UserRepository()
        char_repo = CharacterRepository()
        wi_repo = WorldInfoRepository()
        lb_repo = LorebookRepository()
        persona_repo = PersonaRepository()
        trans_repo = TranslationRepository()
        trans_service = TranslationService()
        llm = get_llm_provider(settings)

        target_langs = user_repo.list_distinct_languages()
        if not target_langs:
            target_langs = ["en"]

        tasks: list[tuple[str, int, str, str, str, str]] = []
        seen_keys: set[tuple[str, int, str]] = set()

        def _enqueue(
            entity_type: str,
            entity_id: int | None,
            field_name: str,
            base_text: str,
            origin_lang: str,
            label: str,
        ) -> None:
            if not entity_id or not base_text or not base_text.strip():
                return
            key = (entity_type, entity_id, field_name)
            if key in seen_keys:
                return
            seen_keys.add(key)
            tasks.append((entity_type, entity_id, field_name, base_text.strip(), origin_lang or "en", label))

        # 1. Customized System Prompts
        for prompt_key in PROMPT_KEYS:
            val = getattr(settings.prompts, prompt_key, "")
            if val and not is_default_prompt(prompt_key, val):
                _enqueue("system_prompt", 1, prompt_key, val, "en", f"System Prompt: {prompt_key}")

        processed_worldinfos: set[int] = set()
        processed_lorebooks: set[int] = set()

        def _enqueue_lorebook(lb_id: int) -> None:
            if lb_id in processed_lorebooks:
                return
            processed_lorebooks.add(lb_id)
            lb = lb_repo.get_by_id(lb_id)
            if lb is None or lb.id is None:
                return
            olang = getattr(lb, "origin_language", "en") or "en"
            if not getattr(lb, "is_proper_noun", False):
                _enqueue("lorebook", lb.id, "name", lb.name, olang, f"Lorebook: {lb.name}")
            _enqueue("lorebook", lb.id, "description", lb.description, olang, f"Lorebook: {lb.name}")
            for entry in lb_repo.list_entries(lb.id, is_admin=True):
                if entry.id is None:
                    continue
                if not getattr(entry, "is_proper_noun", False):
                    _enqueue("lorebook_entry", entry.id, "title", entry.title, olang, f"Lorebook Entry: {entry.title}")
                _enqueue("lorebook_entry", entry.id, "content", entry.content, olang, f"Lorebook Entry: {entry.title}")
                if entry.tags:
                    _enqueue("lorebook_entry", entry.id, "tags", ", ".join(entry.tags), olang, f"Lorebook Tags: {entry.title}")

        def _enqueue_worldinfo_base(wi_id: int) -> None:
            if wi_id in processed_worldinfos:
                return
            processed_worldinfos.add(wi_id)
            wi = wi_repo.get_by_id(wi_id)
            if wi is None or wi.id is None:
                return
            olang = getattr(wi, "origin_language", "en") or "en"
            if not getattr(wi, "is_proper_noun", False):
                _enqueue("worldinfo", wi.id, "name", wi.name, olang, f"World: {wi.name}")
            if wi.lorebook_id is not None:
                _enqueue_lorebook(wi.lorebook_id)
            for loc in wi_repo.list_locations(wi.id):
                if loc.id is None or loc.character_id is not None:
                    continue
                if not getattr(loc, "is_proper_noun", False):
                    _enqueue("worldinfo_location", loc.id, "name", loc.name, olang, f"Location: {loc.name}")
                _enqueue("worldinfo_location", loc.id, "description", loc.description, olang, f"Location: {loc.name}")
                if loc.tags:
                    _enqueue("worldinfo_location", loc.id, "tags", ", ".join(loc.tags), olang, f"Location Tags: {loc.name}")
            for ev in wi_repo.list_events(wi.id):
                if ev.id is None or ev.character_id is not None:
                    continue
                if not getattr(ev, "is_proper_noun", False):
                    _enqueue("worldinfo_event", ev.id, "title", ev.title, olang, f"Event: {ev.title}")
                _enqueue("worldinfo_event", ev.id, "description", ev.description, olang, f"Event: {ev.title}")

        # 2. Popular Characters + Recommended WorldInfo (before character)
        for char_id, suggested_wi_id in char_repo.list_popularity_ordered_ids():
            if suggested_wi_id is not None:
                _enqueue_worldinfo_base(suggested_wi_id)
            char = char_repo.get_by_id(char_id)
            if char is None or char.id is None:
                continue
            c_lang = getattr(char, "origin_language", "en") or "en"
            for lb_id in char.linked_lorebook_ids:
                _enqueue_lorebook(lb_id)
            _enqueue("character", char.id, "description", char.description, c_lang, f"Character: {char.name}")
            _enqueue("character", char.id, "appearance", char.appearance, c_lang, f"Character: {char.name}")
            _enqueue("character", char.id, "first_message", char.first_message, c_lang, f"Character: {char.name}")
            if char.dialogue_examples:
                dlg_text = (
                    "\n\n".join(
                        f"<START>\n{ex['trigger']}\n{ex['response']}" if isinstance(ex, dict) else str(ex)
                        for ex in char.dialogue_examples
                    )
                    if isinstance(char.dialogue_examples, list)
                    else str(char.dialogue_examples)
                )
                _enqueue("character", char.id, "dialogue_examples", dlg_text, c_lang, f"Character: {char.name}")
            if char.suggested_worldinfo_id is not None:
                for loc in wi_repo.list_locations(char.suggested_worldinfo_id):
                    if loc.id is not None and loc.character_id == char.id:
                        if not getattr(loc, "is_proper_noun", False):
                            _enqueue("worldinfo_location", loc.id, "name", loc.name, c_lang, f"Location: {loc.name}")
                        _enqueue("worldinfo_location", loc.id, "description", loc.description, c_lang, f"Location: {loc.name}")
            for ev in wi_repo.list_character_events(char.id):
                if ev.id is not None:
                    if not getattr(ev, "is_proper_noun", False):
                        _enqueue("worldinfo_event", ev.id, "title", ev.title, c_lang, f"Character Event: {ev.title}")
                    _enqueue("worldinfo_event", ev.id, "description", ev.description, c_lang, f"Character Event: {ev.title}")

        # 3. Remaining standalone WorldInfos, Lorebooks
        for wi in wi_repo.list_all():
            if wi.id is not None:
                _enqueue_worldinfo_base(wi.id)
        for lb in lb_repo.list_for_user(None):
            if lb.id is not None:
                _enqueue_lorebook(lb.id)

        work_items: list[tuple[str, int, str, str, str, list[str], str]] = []
        for etype, eid, fname, base_txt, olang, label in tasks:
            missing = trans_repo.get_missing_languages(etype, eid, fname, target_langs)
            if not missing:
                continue
            # Ensure origin text is stored in entity_field_translations
            existing = trans_repo.get_field_translations(etype, eid, fname)
            if olang not in existing and olang in missing:
                trans_repo.save_field_translation(etype, eid, fname, olang, base_txt, is_outdated=False)
                missing = [m for m in missing if m != olang]
            if missing:
                work_items.append((etype, eid, fname, base_txt, olang, missing, label))

        total_steps = sum(len(item[5]) for item in work_items)
        with self._lock:
            self._running = True
            self._completed = 0
            self._total = total_steps
            self._last_error = ""

        for etype, eid, fname, base_txt, olang, missing_langs, label in work_items:
            if self._cancel_event.is_set():
                break
            existing = trans_repo.get_field_translations(etype, eid, fname)
            source_text = (
                existing.get("en", {}).get("text")
                or existing.get(olang, {}).get("text")
                or base_txt
            )
            # Translate to English first if missing, so all subsequent targets have a clean English pivot
            ordered_missing = (["en"] + [m for m in missing_langs if m != "en"]) if "en" in missing_langs else missing_langs
            for target_lang in ordered_missing:
                if not self._wait_if_busy():
                    return
                item_type, _, item_title = label.partition(": ")
                with self._lock:
                    self._current_item = f"{label} ({target_lang.upper()})"
                    self._current_type = item_type.strip()
                    self._current_title = item_title.strip() or label
                    self._current_language = target_lang.upper()
                translated = trans_service.translate_text_or_none(
                    text=source_text,
                    target_language=target_lang,
                    llm_provider=llm,
                    model=model,
                )
                if translated and translated.strip():
                    trans_repo.save_field_translation(
                        entity_type=etype,
                        entity_id=eid,
                        field_name=fname,
                        language=target_lang,
                        text_content=translated.strip(),
                        is_outdated=False,
                    )
                    if target_lang == "en":
                        source_text = translated.strip()
                with self._lock:
                    self._completed += 1


_WORKER_INSTANCE: BackgroundTranslationWorker | None = None


def get_translation_worker(is_busy_fn: Callable[[], bool] | None = None) -> BackgroundTranslationWorker:
    global _WORKER_INSTANCE
    if _WORKER_INSTANCE is None:
        _WORKER_INSTANCE = BackgroundTranslationWorker(is_busy_fn=is_busy_fn)
    return _WORKER_INSTANCE


def trigger_translation_sync(manual: bool = False) -> bool:
    return get_translation_worker().trigger_sync(manual=manual)
