from urllib.parse import urlparse

from domain.settings.exceptions import (
    InvalidServiceCredentialsError,
    InvalidServiceUrlError,
    InvalidTaskModelError,
)
from domain.settings.models import (
    RECOMMENDED_GOOGLE_AI_IMAGE_MODEL,
    ImageGenBackend,
    LLMBackend,
    ModelParameters,
    SearchBackend,
    ServiceSettings,
    SystemPrompts,
    TaskAssignment,
    get_recommended_task_models,
)
from shared.config import Config


class SettingsService:
    def get_default_settings(self) -> ServiceSettings:
        try:
            default_backend = LLMBackend.resolve(Config.DEFAULT_LLM_BACKEND)
        except Exception:
            default_backend = LLMBackend.OLLAMA

        rec = get_recommended_task_models(default_backend)
        default_img_backend = (
            ImageGenBackend.GOOGLE_AI
            if default_backend == LLMBackend.GOOGLE_AI
            else ImageGenBackend.COMFYUI
        )
        return ServiceSettings(
            id=1,
            llm_backend=default_backend,
            ollama_url=Config.DEFAULT_OLLAMA_URL,
            google_ai_api_key=Config.DEFAULT_GOOGLE_AI_API_KEY,
            image_gen_backend=default_img_backend,
            google_ai_image_model=RECOMMENDED_GOOGLE_AI_IMAGE_MODEL,
            comfyui_url=Config.DEFAULT_COMFYUI_URL,
            search_backend=SearchBackend.DISABLED,
            searxng_url=Config.DEFAULT_SEARXNG_URL,
            searxng_enabled=False,
            tasks=TaskAssignment(
                roleplay_model=rec["roleplay"],
                memory_model=rec["memory"],
                assistant_model=rec["assistant"],
                vision_model=rec["vision"],
                classification_model=rec["classification"],
            ),
            params=ModelParameters(),
            prompts=SystemPrompts(),
            default_backdrop_path=None,
        )

    def update_backend_configuration(
        self,
        settings: ServiceSettings,
        llm_backend: LLMBackend | str,
        ollama_url: str | None = None,
        google_ai_api_key: str | None = None,
        clear_google_ai_api_key: bool = False,
        image_gen_backend: ImageGenBackend | str | None = None,
        comfyui_url: str | None = None,
        google_ai_image_model: str | None = None,
        search_backend: SearchBackend | str | None = None,
        searxng_url: str | None = None,
    ) -> ServiceSettings:
        previous_backend = settings.llm_backend
        resolved_llm = LLMBackend.resolve(llm_backend)

        if resolved_llm == LLMBackend.OLLAMA:
            target_ollama_url = ollama_url if ollama_url is not None else settings.ollama_url
            settings.ollama_url = self._validate_url("ollama_url", target_ollama_url)
            if clear_google_ai_api_key:
                settings.google_ai_api_key = ""
            elif google_ai_api_key and google_ai_api_key.strip():
                settings.google_ai_api_key = self._validate_api_key(
                    "google_ai_api_key", google_ai_api_key
                )
        else:
            if clear_google_ai_api_key:
                raise InvalidServiceCredentialsError(
                    "Google AI API-Key darf nicht leer sein, solange Google AI als aktives Backend gewählt ist."
                )
            raw_key = (
                google_ai_api_key.strip()
                if isinstance(google_ai_api_key, str) and google_ai_api_key.strip()
                else settings.google_ai_api_key.strip()
            )
            settings.google_ai_api_key = self._validate_api_key("google_ai_api_key", raw_key)
            if isinstance(ollama_url, str) and ollama_url.strip():
                settings.ollama_url = self._validate_url("ollama_url", ollama_url)
            elif not settings.ollama_url:
                settings.ollama_url = Config.DEFAULT_OLLAMA_URL

        resolved_img = (
            ImageGenBackend.resolve(image_gen_backend)
            if image_gen_backend is not None
            else settings.image_gen_backend
        )
        if resolved_llm == LLMBackend.OLLAMA and resolved_img == ImageGenBackend.GOOGLE_AI:
            candidate_comfy = (
                comfyui_url.strip()
                if isinstance(comfyui_url, str) and comfyui_url.strip()
                else settings.comfyui_url
            )
            resolved_img = (
                ImageGenBackend.COMFYUI if candidate_comfy else ImageGenBackend.DISABLED
            )

        if resolved_img == ImageGenBackend.COMFYUI:
            target_comfy = comfyui_url if comfyui_url is not None else settings.comfyui_url
            settings.comfyui_url = self._validate_url("comfyui_url", target_comfy)
        else:
            if isinstance(comfyui_url, str) and comfyui_url.strip():
                settings.comfyui_url = self._validate_url("comfyui_url", comfyui_url)
            if resolved_img == ImageGenBackend.GOOGLE_AI:
                target_img_model = (
                    google_ai_image_model
                    if google_ai_image_model is not None and google_ai_image_model.strip()
                    else (settings.google_ai_image_model or RECOMMENDED_GOOGLE_AI_IMAGE_MODEL)
                )
                settings.google_ai_image_model = self._validate_model_name(
                    "google_ai_image_model", target_img_model
                )

        resolved_search = (
            SearchBackend.resolve(search_backend)
            if search_backend is not None
            else settings.search_backend
        )
        if resolved_llm == LLMBackend.OLLAMA and resolved_search == SearchBackend.GOOGLE_AI:
            resolved_search = SearchBackend.DISABLED

        if resolved_search == SearchBackend.SEARXNG:
            target_searxng = searxng_url if searxng_url is not None else settings.searxng_url
            settings.searxng_url = self._validate_url("searxng_url", target_searxng)
            settings.searxng_enabled = True
        else:
            settings.searxng_enabled = False
            if isinstance(searxng_url, str) and searxng_url.strip():
                settings.searxng_url = self._validate_url("searxng_url", searxng_url)

        settings.llm_backend = resolved_llm
        settings.image_gen_backend = resolved_img
        settings.search_backend = resolved_search

        if previous_backend != resolved_llm:
            self.reconcile_task_models_for_backend(settings, previous_backend=previous_backend)

        return settings

    def update_service_urls(
        self,
        settings: ServiceSettings,
        ollama_url: str,
        comfyui_url: str,
        searxng_url: str,
        searxng_enabled: bool = False,
    ) -> ServiceSettings:
        return self.update_backend_configuration(
            settings=settings,
            llm_backend=settings.llm_backend,
            ollama_url=ollama_url,
            image_gen_backend=(
                ImageGenBackend.COMFYUI
                if (comfyui_url and comfyui_url.strip())
                else ImageGenBackend.DISABLED
            ),
            comfyui_url=comfyui_url,
            search_backend=(
                SearchBackend.SEARXNG if searxng_enabled else SearchBackend.DISABLED
            ),
            searxng_url=searxng_url,
        )

    def update_task_models(
        self,
        settings: ServiceSettings,
        roleplay_model: str,
        memory_model: str,
        assistant_model: str,
        vision_model: str,
        classification_model: str | None = None,
    ) -> ServiceSettings:
        cleaned_roleplay = self._validate_model_name("roleplay_model", roleplay_model)
        cleaned_memory = self._validate_model_name("memory_model", memory_model)
        cleaned_assistant = self._validate_model_name("assistant_model", assistant_model)
        cleaned_vision = self._validate_model_name("vision_model", vision_model)
        cleaned_classification = self._validate_model_name(
            "classification_model",
            classification_model or cleaned_roleplay,
        )

        settings.tasks = TaskAssignment(
            roleplay_model=cleaned_roleplay,
            memory_model=cleaned_memory,
            assistant_model=cleaned_assistant,
            vision_model=cleaned_vision,
            classification_model=cleaned_classification,
        )
        return settings

    def apply_recommended_task_models(self, settings: ServiceSettings) -> ServiceSettings:
        rec = get_recommended_task_models(settings.llm_backend)
        if settings.llm_backend == LLMBackend.GOOGLE_AI and not settings.google_ai_image_model:
            settings.google_ai_image_model = RECOMMENDED_GOOGLE_AI_IMAGE_MODEL
        return self.update_task_models(
            settings=settings,
            roleplay_model=rec["roleplay"],
            memory_model=rec["memory"],
            assistant_model=rec["assistant"],
            vision_model=rec["vision"],
            classification_model=rec["classification"],
        )

    def reconcile_task_models_for_backend(
        self,
        settings: ServiceSettings,
        previous_backend: LLMBackend | None = None,
    ) -> ServiceSettings:
        target = settings.llm_backend
        rec = get_recommended_task_models(target)
        prev_rec = (
            set(get_recommended_task_models(previous_backend).values())
            if previous_backend is not None and previous_backend != target
            else set()
        )

        def _pick(current: str, role: str) -> str:
            if not current or not current.strip():
                return rec[role]
            if not self.is_model_compatible_with_backend(current, target):
                return rec[role]
            if current in prev_rec:
                return rec[role]
            return current.strip()

        settings.tasks = TaskAssignment(
            roleplay_model=_pick(settings.tasks.roleplay_model, "roleplay"),
            memory_model=_pick(settings.tasks.memory_model, "memory"),
            assistant_model=_pick(settings.tasks.assistant_model, "assistant"),
            vision_model=_pick(settings.tasks.vision_model, "vision"),
            classification_model=_pick(settings.tasks.classification_model, "classification"),
        )
        return settings

    @staticmethod
    def is_model_compatible_with_backend(model_name: str, backend: LLMBackend) -> bool:
        cleaned = (model_name or "").strip().lower()
        if not cleaned:
            return False
        if backend == LLMBackend.GOOGLE_AI:
            # Ollama model tags routinely contain ':' or repo slashes like 'user/model:tag'
            return ":" not in cleaned and not cleaned.startswith("llama")
        # Ollama models don't use hosted Gemini cloud IDs
        return not cleaned.startswith("gemini-") and not cleaned.startswith("models/gemini-")

    def update_parameters(
        self,
        settings: ServiceSettings,
        num_ctx: int,
        temperature: float,
        top_p: float,
        repeat_penalty: float,
    ) -> ServiceSettings:
        settings.params = ModelParameters(
            num_ctx=num_ctx,
            temperature=temperature,
            top_p=top_p,
            repeat_penalty=repeat_penalty,
        )
        return settings

    def update_system_prompts(
        self,
        settings: ServiceSettings,
        roleplay_prompt: str,
        memory_prompt: str,
        diffuser_prompt: str,
        sparkle_assistant_prompt: str,
        vision_persona_prompt: str | None = None,
        dialogue_author_prompt: str | None = None,
    ) -> ServiceSettings:
        resolved_vision_prompt = (
            settings.prompts.vision_persona_prompt
            if vision_persona_prompt is None
            else vision_persona_prompt.strip()
        )
        resolved_dialogue_prompt = (
            settings.prompts.dialogue_author_prompt
            if dialogue_author_prompt is None
            else dialogue_author_prompt.strip()
        )
        settings.prompts = SystemPrompts(
            roleplay_prompt=roleplay_prompt.strip() if isinstance(roleplay_prompt, str) else "",
            memory_prompt=memory_prompt.strip() if isinstance(memory_prompt, str) else "",
            diffuser_prompt=diffuser_prompt.strip() if isinstance(diffuser_prompt, str) else "",
            sparkle_assistant_prompt=(
                sparkle_assistant_prompt.strip()
                if isinstance(sparkle_assistant_prompt, str)
                else ""
            ),
            vision_persona_prompt=resolved_vision_prompt,
            dialogue_author_prompt=resolved_dialogue_prompt,
        )
        return settings

    def update_default_backdrop(
        self,
        settings: ServiceSettings,
        backdrop_path: str | None,
    ) -> ServiceSettings:
        cleaned = (
            backdrop_path.strip()
            if isinstance(backdrop_path, str) and backdrop_path.strip()
            else None
        )
        settings.default_backdrop_path = cleaned
        return settings

    @staticmethod
    def _validate_url(field_name: str, raw_url: str) -> str:
        if not isinstance(raw_url, str) or not raw_url.strip():
            raise InvalidServiceUrlError(f"Service URL '{field_name}' must not be empty.")
        cleaned = raw_url.strip().rstrip("/")
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise InvalidServiceUrlError(
                f"Service URL '{field_name}' must be a valid HTTP/HTTPS URL: '{raw_url}'."
            )
        return cleaned

    @staticmethod
    def _validate_api_key(field_name: str, raw_key: str) -> str:
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise InvalidServiceCredentialsError(
                f"Google AI API-Key ('{field_name}') darf nicht leer sein."
            )
        cleaned = raw_key.strip()
        if any(ch.isspace() for ch in cleaned):
            raise InvalidServiceCredentialsError(
                "Google AI API-Key darf keine Leerzeichen oder Zeilenumbrüche enthalten."
            )
        return cleaned

    @staticmethod
    def _validate_model_name(field_name: str, model_name: str) -> str:
        if not isinstance(model_name, str) or not model_name.strip():
            raise InvalidTaskModelError(f"Task model '{field_name}' must not be empty.")
        return model_name.strip()
