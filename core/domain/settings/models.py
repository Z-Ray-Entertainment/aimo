from dataclasses import dataclass, field

from domain.settings.exceptions import (
    InvalidModelParametersError,
    InvalidSystemPromptError,
)
from shared.config import Config

DEFAULT_ROLEPLAY_PROMPT: str = (
    "Write {{char}}'s next reply in a fictional chat between {{char}} and {{user}}. "
    "Write all your replies as {{char}} in first person. Only one reply, do not advance the story."
)

DEFAULT_MEMORY_PROMPT: str = (
    "Analyze the last 10 roleplay messages and extract a structured episodic memory in English. "
    "Provide:\n"
    "1. A concise section title.\n"
    "2. Comma-separated keywords/tags for tag-based retrieval.\n"
    "3. A narrative summary of key events and relationship developments (300 to 500 characters).\n"
    "4. An updated short title for the overall chat session."
)

DEFAULT_DIFFUSER_PROMPT: str = (
    "Convert the current roleplay scene, character appearance, user persona appearance, and "
    "location details into a high-quality, comma-separated English image generation prompt "
    "optimized for Stable Diffusion / Flux in ComfyUI. Focus strictly on visual composition, "
    "lighting, expressions, clothing, and environment without meta-text."
)

DEFAULT_SPARKLE_ASSISTANT_PROMPT: str = (
    "Du bist ein professioneller Autor und entwirfst eine Charakterbeschreibung auf Basis der "
    "gegebenen Vorlage. / You are a professional author crafting a vivid, immersive, and "
    "well-structured character description based on the provided draft. Preserve all core traits "
    "while enhancing narrative depth, personality nuances, and sensory details."
)

DEFAULT_VISION_PERSONA_PROMPT: str = (
    "Analyze the portrait image and describe only the character's physical appearance in English: "
    "facial features, eye color, hairstyle and hair color, skin tone, build, and distinctive "
    "physical traits. Strictly ignore image backgrounds, lighting effects, and situational body poses."
)


@dataclass
class ModelParameters:
    num_ctx: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    repeat_penalty: float = 1.1

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if isinstance(self.num_ctx, bool) or not isinstance(self.num_ctx, int) or self.num_ctx <= 0:
            raise InvalidModelParametersError(
                "Context size (num_ctx) must be a positive integer."
            )
        if (
            isinstance(self.temperature, bool)
            or not isinstance(self.temperature, (int, float))
            or not (0.0 <= float(self.temperature) <= 2.0)
        ):
            raise InvalidModelParametersError(
                "Temperature must be a number between 0.0 and 2.0."
            )
        if (
            isinstance(self.top_p, bool)
            or not isinstance(self.top_p, (int, float))
            or not (0.0 < float(self.top_p) <= 1.0)
        ):
            raise InvalidModelParametersError(
                "top_p must be a number in the range (0.0, 1.0]."
            )
        if (
            isinstance(self.repeat_penalty, bool)
            or not isinstance(self.repeat_penalty, (int, float))
            or float(self.repeat_penalty) <= 0.0
        ):
            raise InvalidModelParametersError(
                "repeat_penalty must be a positive number greater than 0.0."
            )
        self.temperature = float(self.temperature)
        self.top_p = float(self.top_p)
        self.repeat_penalty = float(self.repeat_penalty)


RECOMMENDED_DEFAULT_MODEL: str = "hf.co/mradermacher/MN-Violet-Lotus-12B-GGUF:Q4_K_M"


@dataclass
class TaskAssignment:
    roleplay_model: str = RECOMMENDED_DEFAULT_MODEL
    memory_model: str = RECOMMENDED_DEFAULT_MODEL
    assistant_model: str = RECOMMENDED_DEFAULT_MODEL
    vision_model: str = "llava:latest"


@dataclass
class SystemPrompts:
    roleplay_prompt: str = DEFAULT_ROLEPLAY_PROMPT
    memory_prompt: str = DEFAULT_MEMORY_PROMPT
    diffuser_prompt: str = DEFAULT_DIFFUSER_PROMPT
    sparkle_assistant_prompt: str = DEFAULT_SPARKLE_ASSISTANT_PROMPT
    vision_persona_prompt: str = DEFAULT_VISION_PERSONA_PROMPT

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        fields = {
            "roleplay_prompt": self.roleplay_prompt,
            "memory_prompt": self.memory_prompt,
            "diffuser_prompt": self.diffuser_prompt,
            "sparkle_assistant_prompt": self.sparkle_assistant_prompt,
            "vision_persona_prompt": self.vision_persona_prompt,
        }
        for field_name, value in fields.items():
            if not isinstance(value, str) or not value.strip():
                raise InvalidSystemPromptError(
                    f"System prompt '{field_name}' must not be empty."
                )


@dataclass
class ServiceSettings:
    id: int = 1
    ollama_url: str = Config.DEFAULT_OLLAMA_URL
    comfyui_url: str = Config.DEFAULT_COMFYUI_URL
    searxng_url: str = Config.DEFAULT_SEARXNG_URL
    searxng_enabled: bool = False
    tasks: TaskAssignment = field(default_factory=TaskAssignment)
    params: ModelParameters = field(default_factory=ModelParameters)
    prompts: SystemPrompts = field(default_factory=SystemPrompts)
