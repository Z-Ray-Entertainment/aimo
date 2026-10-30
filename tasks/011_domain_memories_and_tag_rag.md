# Task 011: Asynchrone Memories & Vektorloses RAG

## 🎯 Ziel & Umfang
Erstellung des automatisierten 10-Nachrichten-Memory-Systems, der dynamischen Chat-Titel-Aktualisierung, des strikt vektorlosen Tag-RAG (`tags_overlap >= 1`) und der Lösch-Kaskade bei Nachrichten-Löschung.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `domain/memories/`
- **Dateien:**
  - `domain/memories/models.py`
  - `domain/memories/services.py`
  - `domain/memories/exceptions.py`

## 🔗 Abhängigkeiten
- `tasks/001_foundation_config_and_shared_utils.md`
- `tasks/005_infrastructure_provider_interfaces_and_adapters.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. `domain/memories/models.py`
- **`Memory` (Entity):**
  - `id: int | None`
  - `chat_session_id: int`
  - `message_idx: int` (Gültigkeitsindex für Forking & Löschen)
  - `title: str` (Aussagekräftiger Abschnittstitel)
  - `tags: list[str]` (Schlagworte zur Aktivierung via RAG)
  - `summary: str` (Zusammenfassung der Geschehnisse, ca. 300–500 Zeichen)
  - `created_at: datetime`
  - `updated_at: datetime`

### 2. `domain/memories/services.py`
- **`MemoryService`:**
  - `should_generate_memory(unsummarized_message_count: int) -> bool`:
    - Gibt `True` zurück, wenn `unsummarized_message_count >= 10` ist.
  - `extract_memory_and_title(last_10_messages: list[dict], memory_prompt: str, llm_provider: LLMProvider, model: str) -> tuple[str, list[str], str, str]`:
    - Generiert `(title, tags, summary, new_chat_title)`.
    - **Wichtig:** Läuft als asynchroner Background-Task, um den Chat nie zu blockieren.
  - `search_memories_by_tags(memories: list[Memory], active_tags: list[str]) -> list[Memory]`:
    - Filtert Memories über `shared.utils.tags_overlap(memory.tags, active_tags) == True`.
    - **Strikte Regel:** Keine Vektordatenbank oder Embeddings!
  - `cascade_delete_memories(memories: list[Memory], deleted_message_idx: int) -> list[Memory]`:
    - Entfernt alle Memories, deren `message_idx > deleted_message_idx` ist.
  - `filter_memories_for_fork(memories: list[Memory], fork_point_idx: int) -> list[Memory]`:
    - Behält nur Memories mit `message_idx <= fork_point_idx`.

### 3. `domain/memories/exceptions.py`
- `MemoryNotFoundError`, `InvalidMemoryDataError`.

## ✅ Akzeptanzkriterien
- [ ] Memory-Erzeugung wird alle 10 ungesicherten Nachrichten ausgelöst.
- [ ] Vektorloses RAG arbeitet rein über Tag-Listen (`tags_overlap >= 1`).
- [ ] Kaskadierende Löschung von Memories bei Löschen älterer Chat-Nachrichten.
- [ ] Forking-Filterung übernimmt nur Memories bis `fork_point_idx`.
