# Task 007: Lorebooks & Lorebook Entries

## 🎯 Goal & Scope
Creation and management of encyclopedias and lorebooks (`Lorebook`) with corresponding entries (`LorebookEntry`) for subsequent vectorless tag-based RAG.

## 📂 Affected Layer & Files
- **Layer:** `domain/lorebooks/`
- **Files:**
  - `domain/lorebooks/models.py`
  - `domain/lorebooks/services.py`
  - `domain/lorebooks/exceptions.py`

## 🔗 Dependencies
- `tasks/001_foundation_config_and_shared_utils.md`

## 📝 Functional Specifications & Requirements

### 1. `domain/lorebooks/models.py`
- **`Lorebook` (Entity):**
  - `id: int | None`
  - `user_id: int`
  - `name: str`
  - `description: str = ""`
  - `created_at: datetime`
- **`LorebookEntry` (Entity):**
  - `id: int | None`
  - `lorebook_id: int`
  - `title: str`
  - `tags: list[str]` (keywords for RAG activation)
  - `content: str` (prose lore content)
  - `created_at: datetime`
  - `updated_at: datetime`

### 2. `domain/lorebooks/services.py`
- **`LorebookService`:**
  - `create_lorebook(user_id: int, name: str, description: str = "") -> Lorebook`
  - `update_lorebook(lorebook: Lorebook, name: str, description: str) -> Lorebook`
  - `add_entry(lorebook_id: int, title: str, tags: list[str] | str, content: str) -> LorebookEntry`:
    - Tags are parsed and normalized via `shared.utils.parse_tags`.
  - `update_entry(entry: LorebookEntry, title: str, tags: list[str] | str, content: str) -> LorebookEntry`
  - `delete_entry(entry: LorebookEntry) -> None`
  - `search_entries_by_tags(entries: list[LorebookEntry], active_tags: list[str]) -> list[LorebookEntry]`:
    - Filters entries where `shared.utils.tags_overlap(entry.tags, active_tags) == True`.
    - **No vector database!** Strictly rule-based keyword matching.

### 3. `domain/lorebooks/exceptions.py`
- `LorebookNotFoundError`, `EntryNotFoundError`, `InvalidLorebookDataError`.

## ✅ Acceptance Criteria
- [x] Pure domain components without I/O.
- [x] Entries strictly require title, tags (`list[str]`), and prose content.
- [x] Tag search operates precisely according to the rule `tags_overlap >= 1`.
