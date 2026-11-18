import sqlite3

from domain.settings.models import (
    DEFAULT_DIALOGUE_AUTHOR_PROMPT,
    RECOMMENDED_GOOGLE_AI_IMAGE_MODEL,
    ImageGenBackend,
    LLMBackend,
    ModelParameters,
    SearchBackend,
    ServiceSettings,
    SystemPrompts,
    TaskAssignment,
)
from domain.settings.services import SettingsService
from infrastructure.database import get_db_session
from shared.config import Config


class SettingsRepository:
    def __init__(self) -> None:
        self._service = SettingsService()

    def get_settings(self) -> ServiceSettings:
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT * FROM system_settings WHERE id = 1",
            ).fetchone()
            if row is None:
                defaults = self._service.get_default_settings()
                self._insert_or_replace(conn, defaults)
                row = conn.execute(
                    "SELECT * FROM system_settings WHERE id = 1",
                ).fetchone()
            return self._to_entity(row)

    def save_settings(self, settings: ServiceSettings) -> ServiceSettings:
        with get_db_session() as conn:
            self._insert_or_replace(conn, settings)
            row = conn.execute(
                "SELECT * FROM system_settings WHERE id = 1",
            ).fetchone()
            return self._to_entity(row)

    @staticmethod
    def _insert_or_replace(conn: sqlite3.Connection, settings: ServiceSettings) -> None:
        conn.execute(
            """
            INSERT INTO system_settings (
                id, llm_backend, ollama_url, google_ai_api_key,
                image_gen_backend, google_ai_image_model, comfyui_url,
                search_backend, searxng_url, searxng_enabled,
                roleplay_model, memory_model, assistant_model, vision_model, classification_model,
                num_ctx, temperature, top_p, repeat_penalty,
                roleplay_prompt, memory_prompt, diffuser_prompt,
                sparkle_assistant_prompt, vision_persona_prompt, dialogue_author_prompt, default_backdrop_path
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                llm_backend = excluded.llm_backend,
                ollama_url = excluded.ollama_url,
                google_ai_api_key = excluded.google_ai_api_key,
                image_gen_backend = excluded.image_gen_backend,
                google_ai_image_model = excluded.google_ai_image_model,
                comfyui_url = excluded.comfyui_url,
                search_backend = excluded.search_backend,
                searxng_url = excluded.searxng_url,
                searxng_enabled = excluded.searxng_enabled,
                roleplay_model = excluded.roleplay_model,
                memory_model = excluded.memory_model,
                assistant_model = excluded.assistant_model,
                vision_model = excluded.vision_model,
                classification_model = excluded.classification_model,
                num_ctx = excluded.num_ctx,
                temperature = excluded.temperature,
                top_p = excluded.top_p,
                repeat_penalty = excluded.repeat_penalty,
                roleplay_prompt = excluded.roleplay_prompt,
                memory_prompt = excluded.memory_prompt,
                diffuser_prompt = excluded.diffuser_prompt,
                sparkle_assistant_prompt = excluded.sparkle_assistant_prompt,
                vision_persona_prompt = excluded.vision_persona_prompt,
                dialogue_author_prompt = excluded.dialogue_author_prompt,
                default_backdrop_path = excluded.default_backdrop_path
            """,
            (
                settings.llm_backend.value,
                settings.ollama_url,
                settings.google_ai_api_key,
                settings.image_gen_backend.value,
                settings.google_ai_image_model,
                settings.comfyui_url,
                settings.search_backend.value,
                settings.searxng_url,
                1 if settings.searxng_enabled else 0,
                settings.tasks.roleplay_model,
                settings.tasks.memory_model,
                settings.tasks.assistant_model,
                settings.tasks.vision_model,
                settings.tasks.classification_model,
                settings.params.num_ctx,
                settings.params.temperature,
                settings.params.top_p,
                settings.params.repeat_penalty,
                settings.prompts.roleplay_prompt,
                settings.prompts.memory_prompt,
                settings.prompts.diffuser_prompt,
                settings.prompts.sparkle_assistant_prompt,
                settings.prompts.vision_persona_prompt,
                settings.prompts.dialogue_author_prompt,
                settings.default_backdrop_path,
            ),
        )

    @staticmethod
    def _to_entity(row: sqlite3.Row) -> ServiceSettings:
        keys = row.keys() if hasattr(row, "keys") else []
        classification_val = (
            str(row["classification_model"])
            if "classification_model" in keys
            else str(row["roleplay_model"])
        )
        default_backdrop = (
            str(row["default_backdrop_path"])
            if ("default_backdrop_path" in keys and row["default_backdrop_path"] is not None)
            else None
        )
        dialogue_prompt = (
            str(row["dialogue_author_prompt"])
            if ("dialogue_author_prompt" in keys and row["dialogue_author_prompt"])
            else DEFAULT_DIALOGUE_AUTHOR_PROMPT
        )

        raw_backend = str(row["llm_backend"]) if "llm_backend" in keys and row["llm_backend"] else "ollama"
        try:
            llm_backend = LLMBackend.resolve(raw_backend)
        except Exception:
            llm_backend = LLMBackend.OLLAMA

        db_api_key = str(row["google_ai_api_key"]).strip() if "google_ai_api_key" in keys and row["google_ai_api_key"] else ""
        resolved_api_key = db_api_key or Config.DEFAULT_GOOGLE_AI_API_KEY

        raw_img_backend = (
            str(row["image_gen_backend"])
            if "image_gen_backend" in keys and row["image_gen_backend"]
            else ImageGenBackend.COMFYUI.value
        )
        try:
            image_gen_backend = ImageGenBackend.resolve(raw_img_backend)
        except Exception:
            image_gen_backend = ImageGenBackend.COMFYUI

        img_model = (
            str(row["google_ai_image_model"]).strip()
            if "google_ai_image_model" in keys and row["google_ai_image_model"]
            else RECOMMENDED_GOOGLE_AI_IMAGE_MODEL
        )

        searxng_enabled = bool(row["searxng_enabled"])
        raw_search_backend = (
            str(row["search_backend"])
            if "search_backend" in keys and row["search_backend"]
            else (SearchBackend.SEARXNG.value if searxng_enabled else SearchBackend.DISABLED.value)
        )
        try:
            search_backend = SearchBackend.resolve(raw_search_backend)
        except Exception:
            search_backend = SearchBackend.SEARXNG if searxng_enabled else SearchBackend.DISABLED

        return ServiceSettings(
            id=int(row["id"]),
            llm_backend=llm_backend,
            ollama_url=str(row["ollama_url"]),
            google_ai_api_key=resolved_api_key,
            image_gen_backend=image_gen_backend,
            google_ai_image_model=img_model,
            comfyui_url=str(row["comfyui_url"]),
            search_backend=search_backend,
            searxng_url=str(row["searxng_url"]),
            searxng_enabled=searxng_enabled,
            tasks=TaskAssignment(
                roleplay_model=str(row["roleplay_model"]),
                memory_model=str(row["memory_model"]),
                assistant_model=str(row["assistant_model"]),
                vision_model=str(row["vision_model"]),
                classification_model=classification_val,
            ),
            params=ModelParameters(
                num_ctx=int(row["num_ctx"]),
                temperature=float(row["temperature"]),
                top_p=float(row["top_p"]),
                repeat_penalty=float(row["repeat_penalty"]),
            ),
            prompts=SystemPrompts(
                roleplay_prompt=str(row["roleplay_prompt"]),
                memory_prompt=str(row["memory_prompt"]),
                diffuser_prompt=str(row["diffuser_prompt"]),
                sparkle_assistant_prompt=str(row["sparkle_assistant_prompt"]),
                vision_persona_prompt=str(row["vision_persona_prompt"]),
                dialogue_author_prompt=dialogue_prompt,
            ),
            default_backdrop_path=default_backdrop,
        )
