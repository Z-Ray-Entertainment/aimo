# Task 010: Translation Layer & English Canon

## 🎯 Goal & Scope
Enforce canonical English LLM context: All background data is maintained and cached primarily in English. The web UI displays text in the user's localized language. When users make edits, the English canonical text is updated and the translation cache is synchronized.

## 📂 Affected Layer & Files
- **Layer:** `domain/translation/`, `infrastructure/translation/`
- **Files:**
  - `domain/translation/models.py`
  - `domain/translation/services.py`
  - `domain/translation/exceptions.py`
  - `infrastructure/translation/adapter.py`

## 🔗 Dependencies
- `tasks/001_foundation_config_and_shared_utils.md`
- `tasks/005_infrastructure_provider_interfaces_and_adapters.md`

## 📝 Functional Specifications & Requirements

### 1. `domain/translation/models.py`
- **`Language` (Enum / Value Object):** `EN = "en"`, `DE = "de"`, etc.
- **`TranslationRecord` (Entity):**
  - `id: int | None`
  - `source_hash: str` (SHA-256 hash of original canonical English text)
  - `english_text: str` (canonical text)
  - `target_language: str`
  - `translated_text: str`
  - `updated_at: datetime`

### 2. `domain/translation/services.py`
- **`TranslationService`:**
  - `translate_to_english(text: str, source_language: str, llm_provider: LLMProvider, model: str) -> str`:
    - Translates user inputs or entities into English if not already in English.
  - `get_localized_text(english_text: str, target_language: str, cache_records: dict[str, str], llm_provider: LLMProvider, model: str) -> str`:
    - Checks cache first (`source_hash`).
    - If cache miss: executes translation and stores new `TranslationRecord`.
  - `sync_text_update(old_english_text: str, new_user_text: str, user_language: str, llm_provider: LLMProvider, model: str) -> tuple[str, str]`:
    - Updates canonical English original on user edits.
    - Invalidates stale cache entries for `old_english_text`.

### 3. `infrastructure/translation/adapter.py`
- Utilizes `LLMProvider.generate()` with a specialized translation prompt for precise translation between English and the user's language.

## ✅ Acceptance Criteria
- [x] LLM context remains canonically in English.
- [x] SQLite translation cache (`TranslationRecord`) avoids redundant API calls.
- [x] Edits refresh the canonical English original and invalidate dependent cache records.
