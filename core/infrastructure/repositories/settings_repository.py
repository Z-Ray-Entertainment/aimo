import json
import sqlite3

from domain.settings.models import (
    DEFAULT_DIALOGUE_AUTHOR_PROMPT,
    ModelParameters,
    ServiceSettings,
    SystemPrompts,
    TaskAssignment,
)
from infrastructure.database import get_db_session
from infrastructure.image_gen.comfyui import ComfyUIImageGenProvider
from infrastructure.image_gen.factory import IMAGE_GEN_PROVIDER_CLASSES
from infrastructure.image_gen.google_ai import GoogleAIImageGenProvider
from infrastructure.llm.factory import LLM_PROVIDER_CLASSES
from infrastructure.llm.google_ai import GoogleAILLMProvider
from infrastructure.llm.ollama import OllamaLLMProvider
from infrastructure.provider_registry import ProviderRegistry
from infrastructure.search.factory import SEARCH_PROVIDER_CLASSES
from infrastructure.search.stub import DisabledSearchProvider, SearXNGSearchStubProvider


class SettingsRepository:
    def get_settings(self) -> ServiceSettings:
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT * FROM system_settings WHERE id = 1",
            ).fetchone()
            if row is None:
                defaults = ProviderRegistry.build_default_settings()
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
        provider_configs_payload = json.dumps(
            {
                "llm": settings.llm_configs,
                "image_gen": settings.image_gen_configs,
                "search": settings.search_configs,
            }
        )
        ollama_url = settings.get_llm_config(OllamaLLMProvider.PROVIDER_ID).get(
            "base_url", OllamaLLMProvider.DEFAULT_BASE_URL
        )
        google_api_key = settings.get_llm_config(GoogleAILLMProvider.PROVIDER_ID).get(
            "api_key", ""
        )
        comfyui_url = settings.get_image_gen_config(ComfyUIImageGenProvider.PROVIDER_ID).get(
            "base_url", ComfyUIImageGenProvider.DEFAULT_BASE_URL
        )
        google_img_model = settings.get_image_gen_config(
            GoogleAIImageGenProvider.PROVIDER_ID
        ).get("model", GoogleAIImageGenProvider.RECOMMENDED_MODEL or "")
        searxng_url = settings.get_search_config(SearXNGSearchStubProvider.PROVIDER_ID).get(
            "base_url", SearXNGSearchStubProvider.DEFAULT_BASE_URL
        )
        searxng_enabled = (
            1 if settings.search_backend == SearXNGSearchStubProvider.PROVIDER_ID else 0
        )

        conn.execute(
            """
            INSERT INTO system_settings (
                id, llm_backend, ollama_url, google_ai_api_key,
                image_gen_backend, google_ai_image_model, comfyui_url,
                search_backend, searxng_url, searxng_enabled, provider_configs_json,
                roleplay_model, memory_model, assistant_model, vision_model, classification_model,
                num_ctx, temperature, top_p, repeat_penalty,
                roleplay_prompt, memory_prompt, diffuser_prompt,
                sparkle_assistant_prompt, vision_persona_prompt, dialogue_author_prompt, default_backdrop_path
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                provider_configs_json = excluded.provider_configs_json,
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
                settings.llm_backend,
                ollama_url,
                google_api_key,
                settings.image_gen_backend,
                google_img_model,
                comfyui_url,
                settings.search_backend,
                searxng_url,
                searxng_enabled,
                provider_configs_payload,
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

        raw_llm_backend = (
            str(row["llm_backend"]).strip().lower()
            if "llm_backend" in keys and row["llm_backend"]
            else OllamaLLMProvider.PROVIDER_ID
        )
        if raw_llm_backend not in LLM_PROVIDER_CLASSES:
            raw_llm_backend = OllamaLLMProvider.PROVIDER_ID

        raw_img_backend = (
            str(row["image_gen_backend"]).strip().lower()
            if "image_gen_backend" in keys and row["image_gen_backend"]
            else ComfyUIImageGenProvider.PROVIDER_ID
        )
        if raw_img_backend not in IMAGE_GEN_PROVIDER_CLASSES:
            raw_img_backend = ComfyUIImageGenProvider.PROVIDER_ID

        searxng_enabled = bool(row["searxng_enabled"]) if "searxng_enabled" in keys else False
        raw_search_backend = (
            str(row["search_backend"]).strip().lower()
            if "search_backend" in keys and row["search_backend"]
            else (
                SearXNGSearchStubProvider.PROVIDER_ID
                if searxng_enabled
                else DisabledSearchProvider.PROVIDER_ID
            )
        )
        if raw_search_backend not in SEARCH_PROVIDER_CLASSES:
            raw_search_backend = (
                SearXNGSearchStubProvider.PROVIDER_ID
                if searxng_enabled
                else DisabledSearchProvider.PROVIDER_ID
            )

        parsed_json: dict = {}
        if "provider_configs_json" in keys and row["provider_configs_json"]:
            try:
                loaded = json.loads(str(row["provider_configs_json"]))
                if isinstance(loaded, dict):
                    parsed_json = loaded
            except ValueError:
                parsed_json = {}

        llm_configs: dict[str, dict[str, str]] = {
            pid: cls.get_default_config() for pid, cls in LLM_PROVIDER_CLASSES.items()
        }
        for pid, cfg in (parsed_json.get("llm") or {}).items():
            if isinstance(cfg, dict):
                llm_configs.setdefault(pid, {}).update(
                    {str(k): str(v) for k, v in cfg.items()}
                )

        if "ollama_url" in keys and row["ollama_url"]:
            llm_configs.setdefault(OllamaLLMProvider.PROVIDER_ID, {})["base_url"] = str(
                row["ollama_url"]
            )
        if "google_ai_api_key" in keys and row["google_ai_api_key"]:
            llm_configs.setdefault(GoogleAILLMProvider.PROVIDER_ID, {})["api_key"] = str(
                row["google_ai_api_key"]
            ).strip()
        elif not llm_configs.get(GoogleAILLMProvider.PROVIDER_ID, {}).get("api_key"):
            llm_configs.setdefault(GoogleAILLMProvider.PROVIDER_ID, {})["api_key"] = (
                GoogleAILLMProvider.DEFAULT_API_KEY
            )

        image_gen_configs: dict[str, dict[str, str]] = {
            pid: cls.get_default_config() for pid, cls in IMAGE_GEN_PROVIDER_CLASSES.items()
        }
        for pid, cfg in (parsed_json.get("image_gen") or {}).items():
            if isinstance(cfg, dict):
                image_gen_configs.setdefault(pid, {}).update(
                    {str(k): str(v) for k, v in cfg.items()}
                )

        if "comfyui_url" in keys and row["comfyui_url"]:
            image_gen_configs.setdefault(ComfyUIImageGenProvider.PROVIDER_ID, {})["base_url"] = str(
                row["comfyui_url"]
            )
        if "google_ai_image_model" in keys and row["google_ai_image_model"]:
            image_gen_configs.setdefault(GoogleAIImageGenProvider.PROVIDER_ID, {})["model"] = str(
                row["google_ai_image_model"]
            ).strip()

        search_configs: dict[str, dict[str, str]] = {
            pid: cls.get_default_config() for pid, cls in SEARCH_PROVIDER_CLASSES.items()
        }
        for pid, cfg in (parsed_json.get("search") or {}).items():
            if isinstance(cfg, dict):
                search_configs.setdefault(pid, {}).update(
                    {str(k): str(v) for k, v in cfg.items()}
                )

        if "searxng_url" in keys and row["searxng_url"]:
            search_configs.setdefault(SearXNGSearchStubProvider.PROVIDER_ID, {})["base_url"] = str(
                row["searxng_url"]
            )

        active_llm_cls = LLM_PROVIDER_CLASSES[raw_llm_backend]
        rec_models = active_llm_cls.get_recommended_task_models()

        def _row_model(col_name: str, fallback_key: str) -> str:
            val = str(row[col_name]).strip() if col_name in keys and row[col_name] else ""
            return val or rec_models[fallback_key]

        roleplay_val = _row_model("roleplay_model", "roleplay")
        classification_val = (
            str(row["classification_model"]).strip()
            if "classification_model" in keys and row["classification_model"]
            else roleplay_val
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

        return ServiceSettings(
            id=int(row["id"]),
            llm_backend=raw_llm_backend,
            image_gen_backend=raw_img_backend,
            search_backend=raw_search_backend,
            llm_configs=llm_configs,
            image_gen_configs=image_gen_configs,
            search_configs=search_configs,
            tasks=TaskAssignment(
                roleplay_model=roleplay_val,
                memory_model=_row_model("memory_model", "memory"),
                assistant_model=_row_model("assistant_model", "assistant"),
                vision_model=_row_model("vision_model", "vision"),
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
