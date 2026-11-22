from dataclasses import dataclass
from typing import Any

from security import RequestDataParser


@dataclass
class FirstBootForm:
    username: str = ""
    email: str = ""
    password: str = ""
    language: str = "en"
    persona_name: str = ""
    persona_gender: str = "non-binary"
    persona_description: str = ""
    persona_appearance: str = ""
    llm_backend: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    google_ai_api_key: str = ""
    image_gen_backend: str = "disabled"
    comfyui_url: str = "http://localhost:8188"
    google_ai_image_model: str = "gemini-3.1-flash-image-preview"
    search_backend: str = "disabled"
    searxng_url: str = "http://localhost:8080"
    apply_recommended_models: bool = True
    roleplay_model: str = ""
    memory_model: str = ""
    assistant_model: str = ""
    vision_model: str = ""
    classification_model: str = ""
    active_step: int = 1

    @classmethod
    def from_request(cls, form_data: Any) -> "FirstBootForm":
        return cls(
            username=RequestDataParser.to_str(form_data, "username"),
            email=RequestDataParser.to_str(form_data, "email"),
            password=RequestDataParser.to_str(form_data, "password"),
            language=RequestDataParser.to_str(form_data, "language"),
            persona_name=RequestDataParser.to_str(form_data, "persona_name"),
            persona_gender=RequestDataParser.to_str(form_data, "persona_gender", "non-binary"),
            persona_description=RequestDataParser.to_str(form_data, "persona_description"),
            persona_appearance=RequestDataParser.to_str(form_data, "persona_appearance"),
            llm_backend=RequestDataParser.to_str(form_data, "llm_backend", "ollama").lower(),
            ollama_url=RequestDataParser.to_str(form_data, "ollama_url", "http://localhost:11434"),
            google_ai_api_key=RequestDataParser.to_str(form_data, "google_ai_api_key"),
            image_gen_backend=RequestDataParser.to_str(form_data, "image_gen_backend", "disabled").lower(),
            comfyui_url=RequestDataParser.to_str(form_data, "comfyui_url", "http://localhost:8188"),
            google_ai_image_model=RequestDataParser.to_str(
                form_data, "google_ai_image_model", "gemini-3.1-flash-image-preview"
            ),
            search_backend=RequestDataParser.to_str(form_data, "search_backend", "disabled").lower(),
            searxng_url=RequestDataParser.to_str(form_data, "searxng_url", "http://localhost:8080"),
            apply_recommended_models=RequestDataParser.to_bool(form_data, "apply_recommended_models", False),
            roleplay_model=RequestDataParser.to_str(form_data, "roleplay_model"),
            memory_model=RequestDataParser.to_str(form_data, "memory_model"),
            assistant_model=RequestDataParser.to_str(form_data, "assistant_model"),
            vision_model=RequestDataParser.to_str(form_data, "vision_model"),
            classification_model=RequestDataParser.to_str(form_data, "classification_model"),
            active_step=RequestDataParser.to_int(form_data, "active_step", 1, min_val=1, max_val=3),
        )
