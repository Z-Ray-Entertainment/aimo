from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from domain.settings.exceptions import (
    InvalidImageGenBackendError,
    InvalidLLMBackendError,
    InvalidModelParametersError,
    InvalidSearchBackendError,
    InvalidSystemPromptError,
)
from shared.config import Config

DEFAULT_ROLEPLAY_PROMPT: str = (
    "Write {{char}}'s next reply in a fictional chat between {{char}} and {{user}}. "
    "Write all your replies as {{char}} in first person. Only one reply, do not advance the story.\n"
    "Strict Roleplay Rules:\n"
    "1. You are {{char}}. Speak, react, and feel strictly from {{char}}'s perspective.\n"
    "2. NEVER write, assume, or narrate dialogue, actions, thoughts, or feelings for {{user}}.\n"
    "3. Keep {{char}}'s identity and personality strictly separate from {{user}}.\n"
    "4. Stop immediately when {{char}} finishes speaking or acting; wait for {{user}}'s input.\n"
    "5. Canon Origin & Organic Development: {{char}}'s backstory, origins, and personal history prior to meeting {{user}} in [CHARACTER_DEFINITION] are immutable canon; NEVER contradict them or fabricate conflicting past experiences. However, allow {{char}}'s feelings, trust, and relationship boundaries to authentically evolve and change through events witnessed in [CHAT_HISTORY], [RELEVANT_MEMORIES], and [RELATION]."
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
    "You are a professional creative author and roleplay character designer. "
    "Your task is to craft a vivid, psychologically deep, and immersive character description that serves "
    "directly as the roleplay AI's core persona definition. "
    "Write from an authoritative characterization perspective focused entirely on {{char}}'s identity: "
    "define {{char}}'s true nature, inner motivations, emotional depth, habits, speech mannerisms, and worldview "
    "so that an AI embodying {{char}} unmistakably understands this as its own identity and voice. "
    "Write strictly in continuous narrative prose paragraphs. "
    "Do NOT use markdown formatting, headings, bullet points, or meta-commentary."
)

DEFAULT_VISION_PERSONA_PROMPT: str = (
    "Analyze the portrait image and describe only the character's physical appearance in English: "
    "facial features, eye color, hairstyle and hair color, skin tone, build, and distinctive "
    "physical traits. Strictly ignore image backgrounds, lighting effects, and situational body poses."
)

DEFAULT_DIALOGUE_AUTHOR_PROMPT: str = (
    "You are a professional creative dialogue author and voice designer for roleplay characters. "
    "Your task is to analyze {{char}}'s identity, personality, speech quirks, tone, and worldview from their description, "
    "and generate a single vivid, authentic dialogue example showcasing how {{char}} naturally speaks and reacts to {{user}}.\n"
    "Guidelines:\n"
    "1. Output strictly one single dialogue pair formatted with {{user}}'s trigger and {{char}}'s response.\n"
    "2. Use {{user}} and {{char}} as placeholders.\n"
    "3. Format the response using roleplay dialogue style: spoken words in quotes, narrative actions, gestures, and facial expressions in asterisks (e.g. *actions* \"speech\").\n"
    "4. Respect the requested language and do not repeat scenarios from existing dialogue examples."
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


class LLMBackend(StrEnum):
    OLLAMA = "ollama"
    GOOGLE_AI = "google_ai"

    @classmethod
    def resolve(cls, raw: str | "LLMBackend") -> "LLMBackend":
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, str):
            raise InvalidLLMBackendError(f"Unsupported LLM backend: '{raw}'")
        cleaned = raw.strip().lower()
        for member in cls:
            if cleaned == member.value or cleaned.upper() == member.name:
                return member
        raise InvalidLLMBackendError(f"Unsupported LLM backend: '{raw}'")


class ImageGenBackend(StrEnum):
    COMFYUI = "comfyui"
    GOOGLE_AI = "google_ai"
    DISABLED = "disabled"

    @classmethod
    def resolve(cls, raw: str | "ImageGenBackend") -> "ImageGenBackend":
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, str):
            raise InvalidImageGenBackendError(f"Unsupported image generation backend: '{raw}'")
        cleaned = raw.strip().lower()
        for member in cls:
            if cleaned == member.value or cleaned.upper() == member.name:
                return member
        raise InvalidImageGenBackendError(f"Unsupported image generation backend: '{raw}'")


class SearchBackend(StrEnum):
    DISABLED = "disabled"
    SEARXNG = "searxng"
    GOOGLE_AI = "google_ai"

    @classmethod
    def resolve(cls, raw: str | "SearchBackend") -> "SearchBackend":
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, str):
            raise InvalidSearchBackendError(f"Unsupported search backend: '{raw}'")
        cleaned = raw.strip().lower()
        for member in cls:
            if cleaned == member.value or cleaned.upper() == member.name:
                return member
        raise InvalidSearchBackendError(f"Unsupported search backend: '{raw}'")


RECOMMENDED_ROLEPLAY_MODEL: str = (
    "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest"
)
RECOMMENDED_MEMORY_MODEL: str = (
    "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest"
)
RECOMMENDED_ASSISTANT_MODEL: str = "gemma4:e4b"
RECOMMENDED_VISION_MODEL: str = "gemma4:e4b"
RECOMMENDED_CLASSIFICATION_MODEL: str = "llama3.2:1b"

RECOMMENDED_DEFAULT_MODEL: str = RECOMMENDED_ROLEPLAY_MODEL

RECOMMENDED_MODELS: dict[str, dict[str, str]] = {
    "roleplay": {
        "role_name": "Roleplay",
        "model": RECOMMENDED_ROLEPLAY_MODEL,
        "description": "Narrative Dialog-Generierung und Rollenspiel im Chat.",
    },
    "memory": {
        "role_name": "Memory",
        "model": RECOMMENDED_MEMORY_MODEL,
        "description": "Erstellt alle 10 Nachrichten episodische Zusammenfassungen und aktualisiert den Chat-Titel.",
    },
    "assistant": {
        "role_name": "Assistant",
        "model": RECOMMENDED_ASSISTANT_MODEL,
        "description": "Zuständig für Sparkle-Optimierung (✨), Übersetzungen und Diffuser-Prompts.",
    },
    "vision": {
        "role_name": "Vision",
        "model": RECOMMENDED_VISION_MODEL,
        "description": "Optische Analyse von Porträts, Schauplatz-Hintergründen und Chat-Bildern.",
    },
    "classification": {
        "role_name": "Classification",
        "model": RECOMMENDED_CLASSIFICATION_MODEL,
        "description": "Schnelle Erkennung von Emotionen (Avatar-Sprites) und Ortswechsel-Vorschlägen.",
    },
}

RECOMMENDED_GOOGLE_AI_ROLEPLAY_MODEL: str = "gemini-4-hydrogen"
RECOMMENDED_GOOGLE_AI_MEMORY_MODEL: str = "gemini-4-hydrogen"
RECOMMENDED_GOOGLE_AI_ASSISTANT_MODEL: str = "gemini-4-hydrogen"
RECOMMENDED_GOOGLE_AI_VISION_MODEL: str = "gemini-4-hydrogen"
RECOMMENDED_GOOGLE_AI_CLASSIFICATION_MODEL: str = "gemini-3.1-flash-lite"
RECOMMENDED_GOOGLE_AI_IMAGE_MODEL: str = "gemini-3.1-flash-image-preview"

RECOMMENDED_GOOGLE_AI_MODELS: dict[str, dict[str, str]] = {
    "roleplay": {
        "role_name": "Roleplay",
        "model": RECOMMENDED_GOOGLE_AI_ROLEPLAY_MODEL,
        "description": "Schnelles Cloud-Sprachmodell für narrative Dialoge und Rollenspiel.",
    },
    "memory": {
        "role_name": "Memory",
        "model": RECOMMENDED_GOOGLE_AI_MEMORY_MODEL,
        "description": "Erstellt alle 10 Nachrichten episodische Zusammenfassungen und aktualisiert den Chat-Titel.",
    },
    "assistant": {
        "role_name": "Assistant",
        "model": RECOMMENDED_GOOGLE_AI_ASSISTANT_MODEL,
        "description": "Zuständig für Sparkle-Optimierung (✨), Übersetzungen und Bild-Prompts.",
    },
    "vision": {
        "role_name": "Vision",
        "model": RECOMMENDED_GOOGLE_AI_VISION_MODEL,
        "description": "Multimodale Analyse von Porträts, Schauplatz-Hintergründen und Chat-Bildern.",
    },
    "classification": {
        "role_name": "Classification",
        "model": RECOMMENDED_GOOGLE_AI_CLASSIFICATION_MODEL,
        "description": "Ultraschnelle und kosteneffiziente Erkennung von Emotionen und Ortswechseln.",
    },
}

RECOMMENDED_MODELS_BY_BACKEND: dict[str, dict[str, dict[str, str]]] = {
    LLMBackend.OLLAMA.value: RECOMMENDED_MODELS,
    LLMBackend.GOOGLE_AI.value: RECOMMENDED_GOOGLE_AI_MODELS,
}


def get_recommended_models_for_backend(
    backend: LLMBackend | str,
) -> dict[str, dict[str, str]]:
    resolved = LLMBackend.resolve(backend)
    return RECOMMENDED_MODELS_BY_BACKEND[resolved.value]


def get_recommended_task_models(backend: LLMBackend | str) -> dict[str, str]:
    detail = get_recommended_models_for_backend(backend)
    return {role: info["model"] for role, info in detail.items()}


@dataclass
class TaskAssignment:
    roleplay_model: str = RECOMMENDED_ROLEPLAY_MODEL
    memory_model: str = RECOMMENDED_MEMORY_MODEL
    assistant_model: str = RECOMMENDED_ASSISTANT_MODEL
    classification_model: str = RECOMMENDED_CLASSIFICATION_MODEL
    vision_model: str = RECOMMENDED_VISION_MODEL


@dataclass
class SystemPrompts:
    roleplay_prompt: str = DEFAULT_ROLEPLAY_PROMPT
    memory_prompt: str = DEFAULT_MEMORY_PROMPT
    diffuser_prompt: str = DEFAULT_DIFFUSER_PROMPT
    sparkle_assistant_prompt: str = DEFAULT_SPARKLE_ASSISTANT_PROMPT
    vision_persona_prompt: str = DEFAULT_VISION_PERSONA_PROMPT
    dialogue_author_prompt: str = DEFAULT_DIALOGUE_AUTHOR_PROMPT

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        fields = {
            "roleplay_prompt": self.roleplay_prompt,
            "memory_prompt": self.memory_prompt,
            "diffuser_prompt": self.diffuser_prompt,
            "sparkle_assistant_prompt": self.sparkle_assistant_prompt,
            "vision_persona_prompt": self.vision_persona_prompt,
            "dialogue_author_prompt": self.dialogue_author_prompt,
        }
        for field_name, value in fields.items():
            if not isinstance(value, str) or not value.strip():
                raise InvalidSystemPromptError(
                    f"System prompt '{field_name}' must not be empty."
                )


@dataclass
class ServiceSettings:
    id: int = 1
    llm_backend: LLMBackend = LLMBackend.OLLAMA
    ollama_url: str = Config.DEFAULT_OLLAMA_URL
    google_ai_api_key: str = Config.DEFAULT_GOOGLE_AI_API_KEY
    image_gen_backend: ImageGenBackend = ImageGenBackend.COMFYUI
    google_ai_image_model: str = RECOMMENDED_GOOGLE_AI_IMAGE_MODEL
    comfyui_url: str = Config.DEFAULT_COMFYUI_URL
    search_backend: SearchBackend = SearchBackend.DISABLED
    searxng_url: str = Config.DEFAULT_SEARXNG_URL
    searxng_enabled: bool = False
    tasks: TaskAssignment = field(default_factory=TaskAssignment)
    params: ModelParameters = field(default_factory=ModelParameters)
    prompts: SystemPrompts = field(default_factory=SystemPrompts)
    default_backdrop_path: str | None = None

    @property
    def parameters(self) -> ModelParameters:
        return self.params
