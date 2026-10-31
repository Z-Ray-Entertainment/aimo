# Task 012: ChatSessions, Relationship Dynamics & 7-Stage Prompt

## 🎯 Goal & Scope
Core roleplay and chat logic: `ChatSession`, `Message`, relationship dynamics (+0.1 per user message, -0.1 daily inactivity decay), mandatory 7-stage prompt layout with segment delimiters, and zero-control-tag prompt purity.

## 📂 Affected Layer & Files
- **Layer:** `domain/chat/`
- **Files:**
  - `domain/chat/models.py`
  - `domain/chat/services.py`
  - `domain/chat/prompt_builder.py`
  - `domain/chat/exceptions.py`

## 🔗 Dependencies
- `tasks/001_foundation_config_and_shared_utils.md`
- `tasks/006_domain_personas_and_vision_analysis.md`
- `tasks/008_domain_worldinfo_locations_and_events.md`
- `tasks/009_domain_characters_and_emotional_sprites.md`
- `tasks/011_domain_memories_and_tag_rag.md`

## 📝 Functional Specifications & Requirements

### 1. `domain/chat/models.py`
- **`MessageRole` (Enum):** `USER = "user"`, `CHARACTER = "character"`, `SYSTEM = "system"`.
- **`Message` (Entity):**
  - `id: int | None`
  - `session_id: int`
  - `message_idx: int`
  - `role: MessageRole`
  - `english_content: str` (canonical text)
  - `localized_content: str` (UI presentation text)
  - `image_path: str | None = None`
  - `image_alt_text: str | None = None`
  - `emotion_tag: str | None = None`
  - `created_at: datetime`
- **`ChatSession` (Entity):**
  - `id: int | None`
  - `user_id: int`
  - `character_id: int`
  - `persona_id: int` (permanently locked after 1st user message)
  - `active_worldinfo_id: int | None` (exclusive: max 1 or None)
  - `current_location_id: int | None`
  - `title: str` (dynamic title)
  - `relationship_value: float = 0.0` (clamped between `-100.0` and `+100.0`)
  - `events_enabled: bool = True` (in-chat checkbox opt-out)
  - `cooldown_counter: int`
  - `last_message_at: datetime`
  - `parent_session_id: int | None = None` (for forks)

### 2. `domain/chat/services.py`
- **Relationship Dynamics:**
  - `apply_user_message_affection(session: ChatSession) -> None`: `session.relationship_value = min(100.0, session.relationship_value + 0.1)`.
  - `apply_time_decay(session: ChatSession, current_time: datetime) -> None`:
    - Calculates elapsed days since `session.last_message_at`: `days = (current_time - last_message_at).total_seconds() / 86400.0`.
    - Subtracts `0.1 * days`, firmly clamped at minimum `-100.0`.
- **Session Management & Forking:**
  - `create_session(user_id: int, character: Character, persona_id: int, worldinfo_id: int | None) -> ChatSession`:
    - Sets initial affection score from `character.initial_relationship`.
    - Initializes cooldown (random 10–100).
    - Generates initial `Message` with `character.first_message` and `character.initial_location_id`.
  - `lock_persona(session: ChatSession) -> None`: Locks persona after 1st user message.
  - `switch_worldinfo(session: ChatSession, new_worldinfo_id: int | None) -> None`
  - `fork_session(session: ChatSession, messages: list[Message], fork_point_idx: int) -> tuple[ChatSession, list[Message]]`:
    - Carries forward only messages where `message.message_idx <= fork_point_idx`.

### 3. `domain/chat/prompt_builder.py`
- **Mandatory 7-Stage Layout with Delimiters:**
  ```text
  [SYSTEM_PROMPT]
  {roleplay_system_prompt}
  [/SYSTEM_PROMPT]

  [CHARACTER_DEFINITION]
  {character_definition}
  [/CHARACTER_DEFINITION]

  [USER_PERSONA]
  {user_persona}
  [/USER_PERSONA]

  [WORLD_INFO]
  {world_info_and_location_and_triggered_event}
  [/WORLD_INFO]

  [CHAT_HISTORY]
  {last_10_messages}
  [/CHAT_HISTORY]

  [RELEVANT_MEMORIES]
  {matched_memories}
  [/RELEVANT_MEMORIES]

  [RELEVANT_LOREBOOKS]
  {matched_lorebooks}
  [/RELEVANT_LOREBOOKS]
  ```
- **Context Purity Principle (Zero-Control-Tags):**
  - **Prompt Purity:** No technical system messages (*"You travelled to forest"*), no URLs or Base64.
  - Image attachments enter only as translated ALT descriptions (`[Player shows an image: description]`).
  - The roleplay model receives **no instructions** to produce control syntax.
  - **Output Purity:** The model generates pure narrative prose. A downstream classification call extracts emotions and location changes in isolation.

## ✅ Acceptance Criteria
- [x] Exact 7-stage prompt assembly with closed delimiters.
- [x] Relationship dynamics (+0.1 per message, -0.1 daily inactivity decay) strictly clamped to -100 to +100.
- [x] Persona lock active after the first user message.
- [x] Pure roleplay text free of embedded control tags.
