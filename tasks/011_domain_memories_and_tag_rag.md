# Task 011: Asynchronous Memories & Vectorless Tag-RAG

## 🎯 Goal & Scope
Implementation of the automated 10-message memory system, dynamic chat title updates, strictly vectorless tag-based RAG (`tags_overlap >= 1`), and cascade deletion upon message deletion.

## 📂 Affected Layer & Files
- **Layer:** `domain/memories/`
- **Files:**
  - `domain/memories/models.py`
  - `domain/memories/services.py`
  - `domain/memories/exceptions.py`

## 🔗 Dependencies
- `tasks/001_foundation_config_and_shared_utils.md`
- `tasks/005_infrastructure_provider_interfaces_and_adapters.md`

## 📝 Functional Specifications & Requirements

### 1. `domain/memories/models.py`
- **`Memory` (Entity):**
  - `id: int | None`
  - `chat_session_id: int`
  - `message_idx: int` (validation index for forking and deletions)
  - `title: str` (concise descriptive section header)
  - `tags: list[str]` (keywords for RAG activation)
  - `summary: str` (recap of events, approx. 300–500 characters)
  - `created_at: datetime`
  - `updated_at: datetime`

### 2. `domain/memories/services.py`
- **`MemoryService`:**
  - `should_generate_memory(unsummarized_message_count: int) -> bool`:
    - Returns `True` if `unsummarized_message_count >= 10`.
  - `extract_memory_and_title(last_10_messages: list[dict], memory_prompt: str, llm_provider: LLMProvider, model: str) -> tuple[str, list[str], str, str]`:
    - Generates `(title, tags, summary, new_chat_title)`.
    - **Important:** Executes as an asynchronous background task so chat is never blocked.
  - `search_memories_by_tags(memories: list[Memory], active_tags: list[str]) -> list[Memory]`:
    - Filters memories via `shared.utils.tags_overlap(memory.tags, active_tags) == True`.
    - **Strict Rule:** No vector databases or embeddings!
  - `cascade_delete_memories(memories: list[Memory], deleted_message_idx: int) -> list[Memory]`:
    - Purges all memories where `message_idx > deleted_message_idx`.
  - `filter_memories_for_fork(memories: list[Memory], fork_point_idx: int) -> list[Memory]`:
    - Retains only memories where `message_idx <= fork_point_idx`.

### 3. `domain/memories/exceptions.py`
- `MemoryNotFoundError`, `InvalidMemoryDataError`.

## ✅ Acceptance Criteria
- [x] Memory creation is triggered every 10 unsummarized messages.
- [x] Vectorless RAG functions purely on tag lists (`tags_overlap >= 1`).
- [x] Cascading deletion of memories when deleting earlier chat messages.
- [x] Forking filter carries over only memories up to `fork_point_idx`.
