from dataclasses import dataclass
from typing import Any

from domain.settings.models import (
    RECOMMENDED_GOOGLE_AI_IMAGE_MODEL,
    ImageGenBackend,
    LLMBackend,
    SearchBackend,
    get_recommended_task_models,
)
from shared.config import Config
from shared.request_parsers import RequestDataParser


@dataclass
class FirstBootForm:
    username: str = ""
    email: str = ""
    password: str = ""
    llm_backend: str = LLMBackend.OLLAMA.value
    ollama_url: str = Config.DEFAULT_OLLAMA_URL
    google_ai_api_key: str = ""
    image_gen_backend: str = ImageGenBackend.COMFYUI.value
    comfyui_url: str = Config.DEFAULT_COMFYUI_URL
    google_ai_image_model: str = RECOMMENDED_GOOGLE_AI_IMAGE_MODEL
    search_backend: str = SearchBackend.DISABLED.value
    searxng_url: str = Config.DEFAULT_SEARXNG_URL
    roleplay_model: str = ""
    memory_model: str = ""
    assistant_model: str = ""
    vision_model: str = ""
    classification_model: str = ""
    active_step: int = 1

    def __post_init__(self) -> None:
        rec = get_recommended_task_models(
            self.llm_backend
            if self.llm_backend in (LLMBackend.OLLAMA.value, LLMBackend.GOOGLE_AI.value)
            else LLMBackend.OLLAMA.value
        )
        if not self.roleplay_model:
            self.roleplay_model = rec["roleplay"]
        if not self.memory_model:
            self.memory_model = rec["memory"]
        if not self.assistant_model:
            self.assistant_model = rec["assistant"]
        if not self.vision_model:
            self.vision_model = rec["vision"]
        if not self.classification_model:
            self.classification_model = rec["classification"]

    @classmethod
    def from_request(cls, form_data: Any) -> "FirstBootForm":
        p = RequestDataParser
        raw_backend = p.to_str(form_data, "llm_backend", Config.DEFAULT_LLM_BACKEND).lower()
        if raw_backend not in (LLMBackend.OLLAMA.value, LLMBackend.GOOGLE_AI.value):
            raw_backend = LLMBackend.OLLAMA.value

        default_img = (
            ImageGenBackend.GOOGLE_AI.value
            if raw_backend == LLMBackend.GOOGLE_AI.value
            else ImageGenBackend.COMFYUI.value
        )
        raw_img_backend = p.to_str(form_data, "image_gen_backend", default_img).lower()
        raw_search_backend = p.to_str(
            form_data, "search_backend", SearchBackend.DISABLED.value
        ).lower()

        return cls(
            username=p.to_str(form_data, "username"),
            email=p.to_str(form_data, "email").lower(),
            password=p.to_str(form_data, "password", strip=False),
            llm_backend=raw_backend,
            ollama_url=p.to_str(form_data, "ollama_url") or Config.DEFAULT_OLLAMA_URL,
            google_ai_api_key=p.to_str(form_data, "google_ai_api_key"),
            image_gen_backend=raw_img_backend,
            comfyui_url=p.to_str(form_data, "comfyui_url") or Config.DEFAULT_COMFYUI_URL,
            google_ai_image_model=(
                p.to_str(form_data, "google_ai_image_model")
                or RECOMMENDED_GOOGLE_AI_IMAGE_MODEL
            ),
            search_backend=raw_search_backend,
            searxng_url=p.to_str(form_data, "searxng_url") or Config.DEFAULT_SEARXNG_URL,
            roleplay_model=p.to_str(form_data, "roleplay_model"),
            memory_model=p.to_str(form_data, "memory_model"),
            assistant_model=p.to_str(form_data, "assistant_model"),
            vision_model=p.to_str(form_data, "vision_model"),
            classification_model=p.to_str(form_data, "classification_model"),
            active_step=p.to_int(form_data, "active_step", 1, min_val=1, max_val=3),
        )
