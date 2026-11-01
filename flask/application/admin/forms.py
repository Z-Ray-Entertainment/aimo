from dataclasses import dataclass, field
from typing import Any

from shared.request_parsers import RequestDataParser


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
    ollama_url: str = ""
    comfyui_url: str = ""
    searxng_url: str = ""
    searxng_enabled: bool = False
    roleplay_model: str = ""
    memory_model: str = ""
    assistant_model: str = ""
    classification_model: str = ""
    vision_model: str = ""
    num_ctx: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    roleplay_prompt: str = ""
    memory_prompt: str = ""
    diffuser_prompt: str = ""
    sparkle_assistant_prompt: str = ""
    vision_persona_prompt: str = ""

    @classmethod
    def from_request(cls, form_data: Any) -> "AdminServicesForm":
        p = RequestDataParser
        return cls(
            ollama_url=p.to_str(form_data, "ollama_url"),
            comfyui_url=p.to_str(form_data, "comfyui_url"),
            searxng_url=p.to_str(form_data, "searxng_url"),
            searxng_enabled=p.to_bool(form_data, "searxng_enabled"),
            roleplay_model=p.to_str(form_data, "roleplay_model"),
            memory_model=p.to_str(form_data, "memory_model"),
            assistant_model=p.to_str(form_data, "assistant_model"),
            classification_model=p.to_str(form_data, "classification_model"),
            vision_model=p.to_str(form_data, "vision_model"),
            num_ctx=p.to_int(form_data, "num_ctx", 4096),
            temperature=p.to_float(form_data, "temperature", 0.7),
            top_p=p.to_float(form_data, "top_p", 0.9),
            repeat_penalty=p.to_float(form_data, "repeat_penalty", 1.1),
            roleplay_prompt=p.to_str(form_data, "roleplay_prompt"),
            memory_prompt=p.to_str(form_data, "memory_prompt"),
            diffuser_prompt=p.to_str(form_data, "diffuser_prompt"),
            sparkle_assistant_prompt=p.to_str(form_data, "sparkle_assistant_prompt"),
            vision_persona_prompt=p.to_str(form_data, "vision_persona_prompt"),
        )
