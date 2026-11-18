from dataclasses import dataclass
from typing import Any

from infrastructure.image_gen.comfyui import ComfyUIImageGenProvider
from infrastructure.image_gen.google_ai import GoogleAIImageGenProvider
from infrastructure.llm.factory import LLM_PROVIDER_CLASSES, get_llm_provider_class
from infrastructure.llm.ollama import OllamaLLMProvider
from infrastructure.search.stub import (
    DisabledSearchProvider,
    SearXNGSearchStubProvider,
)
from shared.config import Config
from shared.request_parsers import RequestDataParser


@dataclass
class FirstBootForm:
    username: str = ""
    email: str = ""
    password: str = ""
    llm_backend: str = OllamaLLMProvider.PROVIDER_ID
    ollama_url: str = OllamaLLMProvider.DEFAULT_BASE_URL
    google_ai_api_key: str = ""
    image_gen_backend: str = ComfyUIImageGenProvider.PROVIDER_ID
    comfyui_url: str = ComfyUIImageGenProvider.DEFAULT_BASE_URL
    google_ai_image_model: str = GoogleAIImageGenProvider.RECOMMENDED_MODEL or ""
    search_backend: str = DisabledSearchProvider.PROVIDER_ID
    searxng_url: str = SearXNGSearchStubProvider.DEFAULT_BASE_URL
    roleplay_model: str = ""
    memory_model: str = ""
    assistant_model: str = ""
    vision_model: str = ""
    classification_model: str = ""
    active_step: int = 1

    def __post_init__(self) -> None:
        backend_id = (
            self.llm_backend
            if self.llm_backend in LLM_PROVIDER_CLASSES
            else OllamaLLMProvider.PROVIDER_ID
        )
        rec = get_llm_provider_class(backend_id).get_recommended_task_models()
        if not self.roleplay_model:
            self.roleplay_model = rec.get("roleplay", "")
        if not self.memory_model:
            self.memory_model = rec.get("memory", "")
        if not self.assistant_model:
            self.assistant_model = rec.get("assistant", "")
        if not self.vision_model:
            self.vision_model = rec.get("vision", "")
        if not self.classification_model:
            self.classification_model = rec.get("classification", "")

    @classmethod
    def from_request(cls, form_data: Any) -> "FirstBootForm":
        p = RequestDataParser
        raw_backend = p.to_str(form_data, "llm_backend", Config.DEFAULT_LLM_BACKEND).lower()
        if raw_backend not in LLM_PROVIDER_CLASSES:
            raw_backend = OllamaLLMProvider.PROVIDER_ID

        default_img = (
            GoogleAIImageGenProvider.PROVIDER_ID
            if raw_backend == GoogleAIImageGenProvider.REQUIRES_LLM_BACKEND
            else ComfyUIImageGenProvider.PROVIDER_ID
        )
        raw_img_backend = p.to_str(form_data, "image_gen_backend", default_img).lower()
        raw_search_backend = p.to_str(
            form_data, "search_backend", DisabledSearchProvider.PROVIDER_ID
        ).lower()

        return cls(
            username=p.to_str(form_data, "username"),
            email=p.to_str(form_data, "email").lower(),
            password=p.to_str(form_data, "password", strip=False),
            llm_backend=raw_backend,
            ollama_url=p.to_str(form_data, "ollama_url") or OllamaLLMProvider.DEFAULT_BASE_URL,
            google_ai_api_key=p.to_str(form_data, "google_ai_api_key"),
            image_gen_backend=raw_img_backend,
            comfyui_url=p.to_str(form_data, "comfyui_url") or ComfyUIImageGenProvider.DEFAULT_BASE_URL,
            google_ai_image_model=(
                p.to_str(form_data, "google_ai_image_model")
                or (GoogleAIImageGenProvider.RECOMMENDED_MODEL or "")
            ),
            search_backend=raw_search_backend,
            searxng_url=p.to_str(form_data, "searxng_url") or SearXNGSearchStubProvider.DEFAULT_BASE_URL,
            roleplay_model=p.to_str(form_data, "roleplay_model"),
            memory_model=p.to_str(form_data, "memory_model"),
            assistant_model=p.to_str(form_data, "assistant_model"),
            vision_model=p.to_str(form_data, "vision_model"),
            classification_model=p.to_str(form_data, "classification_model"),
            active_step=p.to_int(form_data, "active_step", 1, min_val=1, max_val=3),
        )
