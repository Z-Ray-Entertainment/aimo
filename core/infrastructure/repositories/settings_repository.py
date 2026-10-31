import sqlite3

from domain.settings.models import (
    ModelParameters,
    ServiceSettings,
    SystemPrompts,
    TaskAssignment,
)
from domain.settings.services import SettingsService
from infrastructure.database import get_db_session


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
                id, ollama_url, comfyui_url, searxng_url, searxng_enabled,
                roleplay_model, memory_model, assistant_model, vision_model,
                num_ctx, temperature, top_p, repeat_penalty,
                roleplay_prompt, memory_prompt, diffuser_prompt,
                sparkle_assistant_prompt, vision_persona_prompt
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                ollama_url = excluded.ollama_url,
                comfyui_url = excluded.comfyui_url,
                searxng_url = excluded.searxng_url,
                searxng_enabled = excluded.searxng_enabled,
                roleplay_model = excluded.roleplay_model,
                memory_model = excluded.memory_model,
                assistant_model = excluded.assistant_model,
                vision_model = excluded.vision_model,
                num_ctx = excluded.num_ctx,
                temperature = excluded.temperature,
                top_p = excluded.top_p,
                repeat_penalty = excluded.repeat_penalty,
                roleplay_prompt = excluded.roleplay_prompt,
                memory_prompt = excluded.memory_prompt,
                diffuser_prompt = excluded.diffuser_prompt,
                sparkle_assistant_prompt = excluded.sparkle_assistant_prompt,
                vision_persona_prompt = excluded.vision_persona_prompt
            """,
            (
                settings.ollama_url,
                settings.comfyui_url,
                settings.searxng_url,
                1 if settings.searxng_enabled else 0,
                settings.tasks.roleplay_model,
                settings.tasks.memory_model,
                settings.tasks.assistant_model,
                settings.tasks.vision_model,
                settings.params.num_ctx,
                settings.params.temperature,
                settings.params.top_p,
                settings.params.repeat_penalty,
                settings.prompts.roleplay_prompt,
                settings.prompts.memory_prompt,
                settings.prompts.diffuser_prompt,
                settings.prompts.sparkle_assistant_prompt,
                settings.prompts.vision_persona_prompt,
            ),
        )

    @staticmethod
    def _to_entity(row: sqlite3.Row) -> ServiceSettings:
        return ServiceSettings(
            id=int(row["id"]),
            ollama_url=str(row["ollama_url"]),
            comfyui_url=str(row["comfyui_url"]),
            searxng_url=str(row["searxng_url"]),
            searxng_enabled=bool(row["searxng_enabled"]),
            tasks=TaskAssignment(
                roleplay_model=str(row["roleplay_model"]),
                memory_model=str(row["memory_model"]),
                assistant_model=str(row["assistant_model"]),
                vision_model=str(row["vision_model"]),
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
            ),
        )
