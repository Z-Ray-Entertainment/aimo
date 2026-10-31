from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdminUserForm:
    username: str = ""
    email: str = ""
    password: str = ""
    preset: str = ""
    permissions: list[str] = field(default_factory=list)

    @classmethod
    def from_request(cls, form_data: Any) -> "AdminUserForm":
        perms = (
            form_data.getlist("permissions")
            if hasattr(form_data, "getlist")
            else []
        )
        return cls(
            username=str(form_data.get("username", "")).strip(),
            email=str(form_data.get("email", "")).strip().lower(),
            password=str(form_data.get("password", "")),
            preset=str(form_data.get("preset", "")).strip(),
            permissions=[str(p).strip() for p in perms if str(p).strip()],
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
        def _int(key: str, default: int) -> int:
            try:
                return int(str(form_data.get(key, default)).strip())
            except ValueError:
                return default

        def _float(key: str, default: float) -> float:
            try:
                return float(str(form_data.get(key, default)).strip())
            except ValueError:
                return default

        return cls(
            ollama_url=str(form_data.get("ollama_url", "")).strip(),
            comfyui_url=str(form_data.get("comfyui_url", "")).strip(),
            searxng_url=str(form_data.get("searxng_url", "")).strip(),
            searxng_enabled=bool(form_data.get("searxng_enabled")),
            roleplay_model=str(form_data.get("roleplay_model", "")).strip(),
            memory_model=str(form_data.get("memory_model", "")).strip(),
            assistant_model=str(form_data.get("assistant_model", "")).strip(),
            vision_model=str(form_data.get("vision_model", "")).strip(),
            num_ctx=_int("num_ctx", 4096),
            temperature=_float("temperature", 0.7),
            top_p=_float("top_p", 0.9),
            repeat_penalty=_float("repeat_penalty", 1.1),
            roleplay_prompt=str(form_data.get("roleplay_prompt", "")).strip(),
            memory_prompt=str(form_data.get("memory_prompt", "")).strip(),
            diffuser_prompt=str(form_data.get("diffuser_prompt", "")).strip(),
            sparkle_assistant_prompt=str(
                form_data.get("sparkle_assistant_prompt", "")
            ).strip(),
            vision_persona_prompt=str(
                form_data.get("vision_persona_prompt", "")
            ).strip(),
        )
