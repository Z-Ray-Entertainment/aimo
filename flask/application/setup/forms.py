from dataclasses import dataclass

from shared.config import Config


@dataclass
class FirstBootForm:
    username: str = ""
    email: str = ""
    password: str = ""
    ollama_url: str = Config.DEFAULT_OLLAMA_URL
    comfyui_url: str = Config.DEFAULT_COMFYUI_URL
    searxng_url: str = Config.DEFAULT_SEARXNG_URL

    @classmethod
    def from_request(cls, form_data: dict) -> "FirstBootForm":
        return cls(
            username=str(form_data.get("username", "")).strip(),
            email=str(form_data.get("email", "")).strip().lower(),
            password=str(form_data.get("password", "")),
            ollama_url=str(form_data.get("ollama_url", Config.DEFAULT_OLLAMA_URL)).strip(),
            comfyui_url=str(
                form_data.get("comfyui_url") or Config.DEFAULT_COMFYUI_URL
            ).strip(),
            searxng_url=str(
                form_data.get("searxng_url") or Config.DEFAULT_SEARXNG_URL
            ).strip(),
        )
