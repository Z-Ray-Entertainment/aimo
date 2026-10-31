from domain.settings.models import ModelParameters
from domain.translation.models import Language, TranslationRecord, compute_source_hash
from domain.translation.services import TranslationService
from infrastructure.llm.interface import LLMProvider


class TranslationAdapter:
    def __init__(
        self,
        llm_provider: LLMProvider,
        model: str,
        translation_service: TranslationService | None = None,
    ) -> None:
        self.llm_provider = llm_provider
        self.model = model
        self.service = translation_service or TranslationService()
        self.params = ModelParameters(
            num_ctx=4096,
            temperature=0.2,
            top_p=0.9,
            repeat_penalty=1.05,
        )

    def to_english(self, text: str, source_language: str = "de") -> str:
        return self.service.translate_to_english(
            text=text,
            source_language=source_language,
            llm_provider=self.llm_provider,
            model=self.model,
        )

    def to_target_language(
        self,
        english_text: str,
        target_language: str = "de",
        cache_records: dict[str, str] | None = None,
    ) -> TranslationRecord:
        cache = cache_records if cache_records is not None else {}
        localized = self.service.get_localized_text(
            english_text=english_text,
            target_language=target_language,
            cache_records=cache,
            llm_provider=self.llm_provider,
            model=self.model,
        )
        return self.service.create_record(
            english_text=english_text,
            target_language=target_language,
            translated_text=localized,
        )

    @staticmethod
    def hash_text(english_text: str) -> str:
        return compute_source_hash(english_text)
