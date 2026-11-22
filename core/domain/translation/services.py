from domain.base import TextGenerationProvider
from domain.settings.models import ModelParameters
from domain.translation.exceptions import InvalidTranslationDataError
from domain.translation.models import (
    LANGUAGE_METADATA,
    Language,
    TranslationRecord,
    compute_source_hash,
)
from domain.validation import DomainValidator

TranslationLLMProvider = TextGenerationProvider


class TranslationService:
    def __init__(self) -> None:
        self._default_params = ModelParameters(
            num_ctx=4096,
            temperature=0.2,
            top_p=0.9,
            repeat_penalty=1.05,
        )

    @staticmethod
    def compute_source_hash(text: str) -> str:
        return compute_source_hash(text)

    def _invoke_translation_llm(
        self,
        llm_provider: TranslationLLMProvider,
        prompt: str,
        model: str,
    ) -> str:
        try:
            raw = llm_provider.generate(
                prompt=prompt,
                model=model,
                params=self._default_params,
                think=False,
            ).strip()
        except TypeError:
            raw = llm_provider.generate(
                prompt=prompt,
                model=model,
                params=self._default_params,
            ).strip()
        return DomainValidator.strip_llm_thinking_tags(raw)

    def translate_to_english(
        self,
        text: str,
        source_language: str,
        llm_provider: TranslationLLMProvider,
        model: str,
    ) -> str:
        if not isinstance(text, str) or not text.strip():
            return ""
        cleaned = text.strip()
        lang = source_language.strip().lower()[:2] if isinstance(source_language, str) else "en"
        if lang == Language.EN.value:
            return cleaned

        prompt = (
            f"Translate the following roleplay text from '{lang}' into natural, accurate English.\n"
            "Output ONLY the translated text without quotes, explanations, or commentary.\n\n"
            f"Text:\n{cleaned}"
        )
        try:
            translated = self._invoke_translation_llm(llm_provider, prompt, model)
            return translated or cleaned
        except Exception:
            return cleaned

    def get_localized_text(
        self,
        english_text: str,
        target_language: str,
        cache_records: dict[str, str],
        llm_provider: TranslationLLMProvider,
        model: str,
    ) -> str:
        if not isinstance(english_text, str) or not english_text.strip():
            return ""
        cleaned_en = english_text.strip()
        lang = target_language.strip().lower()[:2] if isinstance(target_language, str) else "en"
        if lang == Language.EN.value:
            return cleaned_en

        source_hash = compute_source_hash(cleaned_en)
        cache_key = f"{source_hash}:{lang}"
        if cache_key in cache_records:
            return cache_records[cache_key]
        if source_hash in cache_records:
            return cache_records[source_hash]

        lang_label = LANGUAGE_METADATA.get(lang, {}).get("label", lang)
        prompt = (
            f"Translate the following English roleplay text into natural, expressive {lang_label} ('{lang}'). "
            "Preserve tone, character voice, and narrative style.\n"
            "Output ONLY the translated text without quotes, explanations, or commentary.\n\n"
            f"English Text:\n{cleaned_en}"
        )
        try:
            translated = self._invoke_translation_llm(llm_provider, prompt, model)
            result = translated or cleaned_en
        except Exception:
            result = cleaned_en

        cache_records[source_hash] = result
        cache_records[cache_key] = result
        return result

    def translate_text(
        self,
        text: str,
        target_language: str,
        llm_provider: TranslationLLMProvider,
        model: str,
    ) -> str:
        if not isinstance(text, str) or not text.strip():
            return ""
        cleaned = text.strip()
        lang = target_language.strip().lower()[:2] if isinstance(target_language, str) else "en"
        lang_label = LANGUAGE_METADATA.get(lang, {}).get("label", lang)

        prompt = (
            f"Translate the following roleplay text accurately and naturally into {lang_label} ('{lang}').\n"
            "Preserve the narrative tone, character voice, Markdown formatting, and keep any "
            "{{char}} or {{user}} placeholders completely unchanged.\n"
            "Output ONLY the translated text without quotes, explanations, or commentary.\n\n"
            f"Text:\n{cleaned}"
        )
        try:
            translated = self._invoke_translation_llm(llm_provider, prompt, model)
            return translated or cleaned
        except Exception:
            return cleaned

    def translate_text_or_none(
        self,
        text: str,
        target_language: str,
        llm_provider: TranslationLLMProvider,
        model: str,
        should_abort=None,
    ) -> str | None:
        if not isinstance(text, str) or not text.strip():
            return None
        cleaned = text.strip()
        lang = target_language.strip().lower()[:2] if isinstance(target_language, str) else "en"
        lang_label = LANGUAGE_METADATA.get(lang, {}).get("label", lang)

        prompt = (
            f"Translate the following roleplay text accurately and naturally into {lang_label} ('{lang}').\n"
            "Preserve the narrative tone, character voice, Markdown formatting, and keep any "
            "{{char}} or {{user}} placeholders completely unchanged.\n"
            "Output ONLY the translated text without quotes, explanations, or commentary.\n\n"
            f"Text:\n{cleaned}"
        )
        try:
            if should_abort is not None and hasattr(llm_provider, "generate_stream"):
                if should_abort():
                    return None
                chunks: list[str] = []
                try:
                    stream = llm_provider.generate_stream(
                        prompt=prompt,
                        model=model,
                        params=self._default_params,
                        think=False,
                    )
                except TypeError:
                    stream = llm_provider.generate_stream(
                        prompt=prompt,
                        model=model,
                        params=self._default_params,
                    )
                try:
                    for token in stream:
                        if should_abort():
                            return None
                        if token:
                            chunks.append(str(token))
                finally:
                    close_fn = getattr(stream, "close", None)
                    if callable(close_fn):
                        close_fn()
                translated = DomainValidator.strip_llm_thinking_tags("".join(chunks))
            else:
                translated = self._invoke_translation_llm(llm_provider, prompt, model)
            return translated or None
        except Exception:
            return None

    def create_record(
        self,
        english_text: str,
        target_language: str,
        translated_text: str,
    ) -> TranslationRecord:
        if not isinstance(english_text, str) or not english_text.strip():
            raise InvalidTranslationDataError("english_text must not be empty.")
        cleaned_en = english_text.strip()
        lang = target_language.strip().lower()[:2] if isinstance(target_language, str) else "de"
        cleaned_trans = translated_text.strip() if isinstance(translated_text, str) else cleaned_en

        return TranslationRecord(
            id=None,
            source_hash=compute_source_hash(cleaned_en),
            english_text=cleaned_en,
            target_language=lang,
            translated_text=cleaned_trans,
            updated_at=datetime.now(timezone.utc),
        )

    def sync_text_update(
        self,
        old_english_text: str,
        new_user_text: str,
        user_language: str,
        llm_provider: TranslationLLMProvider,
        model: str,
        cache_records: dict[str, str] | None = None,
    ) -> tuple[str, str]:
        old_hash = compute_source_hash(old_english_text) if old_english_text else ""
        if cache_records is not None and old_hash:
            cache_records.pop(old_hash, None)
            keys_to_remove = [k for k in cache_records if k.startswith(f"{old_hash}:")]
            for k in keys_to_remove:
                cache_records.pop(k, None)

        new_english_text = self.translate_to_english(
            text=new_user_text,
            source_language=user_language,
            llm_provider=llm_provider,
            model=model,
        )
        if cache_records is not None and new_english_text:
            new_hash = compute_source_hash(new_english_text)
            lang = user_language.strip().lower()[:2] if isinstance(user_language, str) else "de"
            cache_records[new_hash] = new_user_text.strip()
            cache_records[f"{new_hash}:{lang}"] = new_user_text.strip()

        return new_english_text, old_hash
