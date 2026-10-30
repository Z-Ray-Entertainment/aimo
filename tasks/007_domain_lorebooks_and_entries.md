# Task 007: Lorebooks & Lorebook-Einträge

## 🎯 Ziel & Umfang
Erstellung und Verwaltung von Enzyklopädien und Wissensbüchern (`Lorebook`) mit zugehörigen Einträgen (`LorebookEntry`) für das spätere vektorlose Tag-RAG.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `domain/lorebooks/`
- **Dateien:**
  - `domain/lorebooks/models.py`
  - `domain/lorebooks/services.py`
  - `domain/lorebooks/exceptions.py`

## 🔗 Abhängigkeiten
- `tasks/001_foundation_config_and_shared_utils.md`

## 📝 Fachliche Vorgaben & Spezifikation

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
  - `tags: list[str]` (Schlagworte zur Aktivierung via RAG)
  - `content: str` (Fließtext-Wissensinhalt)
  - `created_at: datetime`
  - `updated_at: datetime`

### 2. `domain/lorebooks/services.py`
- **`LorebookService`:**
  - `create_lorebook(user_id: int, name: str, description: str = "") -> Lorebook`
  - `update_lorebook(lorebook: Lorebook, name: str, description: str) -> Lorebook`
  - `add_entry(lorebook_id: int, title: str, tags: list[str] | str, content: str) -> LorebookEntry`:
    - Tags werden über `shared.utils.parse_tags` validiert und normalisiert.
  - `update_entry(entry: LorebookEntry, title: str, tags: list[str] | str, content: str) -> LorebookEntry`
  - `delete_entry(entry: LorebookEntry) -> None`
  - `search_entries_by_tags(entries: list[LorebookEntry], active_tags: list[str]) -> list[LorebookEntry]`:
    - Filtert alle Einträge heraus, bei denen `shared.utils.tags_overlap(entry.tags, active_tags) == True` gilt.
    - **Keine Vektordatenbank!** Rein regelbasiertes Keyword-Matching.

### 3. `domain/lorebooks/exceptions.py`
- `LorebookNotFoundError`, `EntryNotFoundError`, `InvalidLorebookDataError`.

## ✅ Akzeptanzkriterien
- [ ] Reine Domänenkomponenten ohne I/O.
- [ ] Einträge besitzen zwingend Titel, Tags (`list[str]`) und Fließtext.
- [ ] Tag-Suche arbeitet exakt nach der Regel `tags_overlap >= 1`.
