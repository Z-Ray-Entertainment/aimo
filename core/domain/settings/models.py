from __future__ import annotations

from dataclasses import dataclass, field

from domain.settings.exceptions import (
    InvalidModelParametersError,
    InvalidSystemPromptError,
)
from shared.i18n import gettext_noop as _, t

DEFAULT_ROLEPLAY_PROMPT: str = _(
    "Write {{char}}'s next reply in a fictional chat between {{char}} and {{user}}. "
    "Write all your replies as {{char}} in first person. Only one reply, do not advance the story.\n"
    "Strict Roleplay Rules:\n"
    "1. You are {{char}}. Speak, react, and feel strictly from {{char}}'s perspective.\n"
    "2. NEVER write, assume, or narrate dialogue, actions, thoughts, or feelings for {{user}}.\n"
    "3. Keep {{char}}'s identity and personality strictly separate from {{user}}.\n"
    "4. Stop immediately when {{char}} finishes speaking or acting; wait for {{user}}'s input.\n"
    "5. Canon Origin & Organic Development: {{char}}'s backstory, origins, and personal history prior to meeting {{user}} in [CHARACTER_DEFINITION] are immutable canon; NEVER contradict them or fabricate conflicting past experiences. However, allow {{char}}'s feelings, trust, and relationship boundaries to authentically evolve and change through events witnessed in [CHAT_HISTORY], [RELEVANT_MEMORIES], and [RELATION]."
)

DEFAULT_MEMORY_PROMPT: str = _(
    "Analyze the last 10 roleplay messages and extract a structured episodic memory in the language of the conversation. "
    "Provide:\n"
    "1. A concise section title.\n"
    "2. Comma-separated keywords/tags for tag-based retrieval.\n"
    "3. A narrative summary of key events and relationship developments (300 to 500 characters).\n"
    "4. An updated short title for the overall chat session."
)

DEFAULT_DIFFUSER_PROMPT: str = _(
    "Convert the current roleplay scene, character appearance, user persona appearance, and "
    "location details into a high-quality, comma-separated English image generation prompt "
    "optimized for Stable Diffusion / Flux in ComfyUI. Focus strictly on visual composition, "
    "lighting, expressions, clothing, and environment without meta-text."
)

DEFAULT_SPARKLE_ASSISTANT_PROMPT: str = _(
    "You are a professional creative author and roleplay character designer. "
    "Your task is to craft a vivid, psychologically deep, and immersive character description that serves "
    "directly as the roleplay AI's core persona definition. "
    "Write from an authoritative characterization perspective focused entirely on {{char}}'s identity: "
    "define {{char}}'s true nature, inner motivations, emotional depth, habits, speech mannerisms, and worldview "
    "so that an AI embodying {{char}} unmistakably understands this as its own identity and voice. "
    "Write strictly in continuous narrative prose paragraphs. "
    "Do NOT use markdown formatting, headings, bullet points, or meta-commentary."
)

DEFAULT_VISION_PERSONA_PROMPT: str = _(
    "Analyze the portrait image and describe only the character's physical appearance: "
    "facial features, eye color, hairstyle and hair color, skin tone, build, and distinctive "
    "physical traits. Strictly ignore image backgrounds, lighting effects, and situational body poses."
)

DEFAULT_DIALOGUE_AUTHOR_PROMPT: str = _(
    "You are a professional creative dialogue author and voice designer for roleplay characters. "
    "Your task is to analyze {{char}}'s identity, personality, speech quirks, tone, and worldview from their description, "
    "and generate a single vivid, authentic dialogue example showcasing how {{char}} naturally speaks and reacts to {{user}}.\n"
    "Guidelines:\n"
    "1. Output strictly one single dialogue pair formatted with {{user}}'s trigger and {{char}}'s response.\n"
    "2. Use {{user}} and {{char}} as placeholders.\n"
    "3. Format the response using roleplay dialogue style: spoken words in quotes, narrative actions, gestures, and facial expressions in asterisks (e.g. *actions* \"speech\").\n"
    "4. Respect the requested language and do not repeat scenarios from existing dialogue examples."
)

PROMPT_KEYS: tuple[str, ...] = (
    "roleplay_prompt",
    "memory_prompt",
    "diffuser_prompt",
    "sparkle_assistant_prompt",
    "vision_persona_prompt",
    "dialogue_author_prompt",
)

DEFAULT_PROMPTS_BY_KEY: dict[str, str] = {
    "roleplay_prompt": DEFAULT_ROLEPLAY_PROMPT,
    "memory_prompt": DEFAULT_MEMORY_PROMPT,
    "diffuser_prompt": DEFAULT_DIFFUSER_PROMPT,
    "sparkle_assistant_prompt": DEFAULT_SPARKLE_ASSISTANT_PROMPT,
    "vision_persona_prompt": DEFAULT_VISION_PERSONA_PROMPT,
    "dialogue_author_prompt": DEFAULT_DIALOGUE_AUTHOR_PROMPT,
}


def get_default_prompt(prompt_key: str, language: str = "en") -> str:
    msgid = DEFAULT_PROMPTS_BY_KEY.get(prompt_key, "")
    if not msgid:
        return ""
    return t(msgid, language)


def is_default_prompt(prompt_key: str, text: str) -> bool:
    msgid = DEFAULT_PROMPTS_BY_KEY.get(prompt_key, "")
    if not msgid or not isinstance(text, str):
        return False
    return text.strip() == msgid.strip()


@dataclass
class ModelParameters:
    num_ctx: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if isinstance(self.num_ctx, bool) or not isinstance(self.num_ctx, int) or self.num_ctx <= 0:
            raise InvalidModelParametersError(
                "Context size (num_ctx) must be a positive integer."
            )
        if self.max_tokens is not None and (
            isinstance(self.max_tokens, bool)
            or not isinstance(self.max_tokens, int)
            or self.max_tokens <= 0
        ):
            raise InvalidModelParametersError(
                "max_tokens must be a positive integer."
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


@dataclass
class TaskAssignment:
    roleplay_model: str = ""
    memory_model: str = ""
    assistant_model: str = ""
    classification_model: str = ""
    vision_model: str = ""


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
    llm_backend: str = ""
    image_gen_backend: str = ""
    search_backend: str = ""
    llm_configs: dict[str, dict[str, str]] = field(default_factory=dict)
    image_gen_configs: dict[str, dict[str, str]] = field(default_factory=dict)
    search_configs: dict[str, dict[str, str]] = field(default_factory=dict)
    tasks: TaskAssignment = field(default_factory=TaskAssignment)
    params: ModelParameters = field(default_factory=ModelParameters)
    prompts: SystemPrompts = field(default_factory=SystemPrompts)
    default_backdrop_path: str | None = None

    @property
    def parameters(self) -> ModelParameters:
        return self.params

    @staticmethod
    def _get_provider_config(
        store: dict[str, dict[str, str]],
        default_backend: str,
        backend: str | None,
    ) -> dict[str, str]:
        key = (backend or default_backend).strip().lower()
        return dict(store.get(key, {}))

    @staticmethod
    def _set_provider_config(
        store: dict[str, dict[str, str]],
        backend: str,
        values: dict[str, str],
    ) -> None:
        key = backend.strip().lower()
        if key:
            store[key] = {str(k): str(v) for k, v in values.items()}

    def get_llm_config(self, backend: str | None = None) -> dict[str, str]:
        return self._get_provider_config(self.llm_configs, self.llm_backend, backend)

    def set_llm_config(self, backend: str, values: dict[str, str]) -> None:
        self._set_provider_config(self.llm_configs, backend, values)

    def get_image_gen_config(self, backend: str | None = None) -> dict[str, str]:
        return self._get_provider_config(self.image_gen_configs, self.image_gen_backend, backend)

    def set_image_gen_config(self, backend: str, values: dict[str, str]) -> None:
        self._set_provider_config(self.image_gen_configs, backend, values)

    def get_search_config(self, backend: str | None = None) -> dict[str, str]:
        return self._get_provider_config(self.search_configs, self.search_backend, backend)

    def set_search_config(self, backend: str, values: dict[str, str]) -> None:
        self._set_provider_config(self.search_configs, backend, values)
