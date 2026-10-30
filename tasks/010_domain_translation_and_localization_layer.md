# Task 010: Übersetzungsschicht & Englischer Kanon

## 🎯 Ziel & Umfang
Sicherstellung des englischen LLM-Kanons: Alle Daten werden im Hintergrund primär auf Englisch geführt und gecacht. Die Web-UI zeigt Texte in der Nutzersprache an. Bei Benutzer-Edits wird das englische Original aktualisiert und der Übersetzungs-Cache synchronisiert.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `domain/translation/`, `infrastructure/translation/`
- **Dateien:**
  - `domain/translation/models.py`
  - `domain/translation/services.py`
  - `domain/translation/exceptions.py`
  - `infrastructure/translation/adapter.py`

## 🔗 Abhängigkeiten
- `tasks/001_foundation_config_and_shared_utils.md`
- `tasks/005_infrastructure_provider_interfaces_and_adapters.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. `domain/translation/models.py`
- **`Language` (Enum / Value Object):** `EN = "en"`, `DE = "de"`, etc.
- **`TranslationRecord` (Entity):**
  - `id: int | None`
  - `source_hash: str` (SHA-256 Hash des englischen Originaltextes)
  - `english_text: str` (Kanonischer Text)
  - `target_language: str`
  - `translated_text: str`
  - `updated_at: datetime`

### 2. `domain/translation/services.py`
- **`TranslationService`:**
  - `translate_to_english(text: str, source_language: str, llm_provider: LLMProvider, model: str) -> str`:
    - Übersetzt Benutzereingaben oder Entitäten ins Englische, falls sie nicht bereits auf Englisch vorliegen.
  - `get_localized_text(english_text: str, target_language: str, cache_records: dict[str, str], llm_provider: LLMProvider, model: str) -> str`:
    - Prüft zuerst den Cache (`source_hash`).
    - Falls kein Treffer: Führt Übersetzung durch und legt neuen `TranslationRecord` an.
  - `sync_text_update(old_english_text: str, new_user_text: str, user_language: str, llm_provider: LLMProvider, model: str) -> tuple[str, str]`:
    - Aktualisiert bei Benutzer-Edits das englische Original.
    - Invalidiert veraltete Cache-Einträge für `old_english_text`.

### 3. `infrastructure/translation/adapter.py`
- Nutzt `LLMProvider.generate()` mit einem spezialisierten Übersetzungs-Prompt zur präzisen Übersetzung zwischen Englisch und Nutzersprache.

## ✅ Akzeptanzkriterien
- [ ] LLM-Kontext bleibt kanonisch auf Englisch.
- [ ] Übersetzungs-Cache in SQLite (`TranslationRecord`) verhindert doppelte API-Calls.
- [ ] Edits aktualisieren das englische Original und invalidieren abhängige Cache-Einträge.
