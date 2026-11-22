from dataclasses import dataclass, field
from typing import Any

from security import RequestDataParser


@dataclass
class AdminUserForm:
    username: str = ""
    email: str = ""
    password: str = ""
    preset: str = ""
    permissions: list[str] = field(default_factory=list)

    @classmethod
    def from_request(cls, form_data: Any) -> "AdminUserForm":
        p = RequestDataParser
        return cls(
            username=p.to_str(form_data, "username"),
            email=p.to_str(form_data, "email").lower(),
            password=p.to_str(form_data, "password", strip=False),
            preset=p.to_str(form_data, "preset"),
            permissions=p.to_str_list(form_data, "permissions"),
        )


@dataclass
class AdminServicesForm:
    llm_backend: str = "ollama"
    ollama_url: str = ""
    google_ai_api_key: str = ""
    clear_google_ai_api_key: bool = False
    image_gen_backend: str = "disabled"
    comfyui_url: str = ""
    google_ai_image_model: str = ""
    search_backend: str = "disabled"
    searxng_url: str = ""
    roleplay_model: str = ""
    memory_model: str = ""
    assistant_model: str = ""
    classification_model: str = ""
    vision_model: str = ""
    num_ctx: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    repeat_penalty: float = 1.1

    @classmethod
    def from_request(cls, form_data: Any) -> "AdminServicesForm":
        p = RequestDataParser
        raw_search = p.to_str(form_data, "search_backend")
        if not raw_search:
            raw_search = "searxng" if p.to_bool(form_data, "searxng_enabled") else "disabled"
        raw_img = p.to_str(form_data, "image_gen_backend") or "disabled"
        return cls(
            llm_backend=p.to_str(form_data, "llm_backend", "ollama").lower(),
            ollama_url=p.to_str(form_data, "ollama_url"),
            google_ai_api_key=p.to_str(form_data, "google_ai_api_key"),
            clear_google_ai_api_key=p.to_bool(form_data, "clear_google_ai_api_key"),
            image_gen_backend=raw_img.lower(),
            comfyui_url=p.to_str(form_data, "comfyui_url"),
            google_ai_image_model=p.to_str(form_data, "google_ai_image_model"),
            search_backend=raw_search.lower(),
            searxng_url=p.to_str(form_data, "searxng_url"),
            roleplay_model=p.to_str(form_data, "roleplay_model"),
            memory_model=p.to_str(form_data, "memory_model"),
            assistant_model=p.to_str(form_data, "assistant_model"),
            classification_model=p.to_str(form_data, "classification_model"),
            vision_model=p.to_str(form_data, "vision_model"),
            num_ctx=p.to_int(form_data, "num_ctx", 4096),
            temperature=p.to_float(form_data, "temperature", 0.7),
            top_p=p.to_float(form_data, "top_p", 0.9),
            repeat_penalty=p.to_float(form_data, "repeat_penalty", 1.1),
        )


@dataclass
class AdminPromptsForm:
    roleplay_prompt: str = ""
    memory_prompt: str = ""
    diffuser_prompt: str = ""
    sparkle_assistant_prompt: str = ""
    vision_persona_prompt: str = ""
    dialogue_author_prompt: str = ""

    @classmethod
    def from_request(cls, form_data: Any) -> "AdminPromptsForm":
        p = RequestDataParser
        return cls(
            roleplay_prompt=p.to_str(form_data, "roleplay_prompt"),
            memory_prompt=p.to_str(form_data, "memory_prompt"),
            diffuser_prompt=p.to_str(form_data, "diffuser_prompt"),
            sparkle_assistant_prompt=p.to_str(form_data, "sparkle_assistant_prompt"),
            vision_persona_prompt=p.to_str(form_data, "vision_persona_prompt"),
            dialogue_author_prompt=p.to_str(form_data, "dialogue_author_prompt"),
        )
