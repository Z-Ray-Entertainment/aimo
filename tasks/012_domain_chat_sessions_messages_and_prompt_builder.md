# Task 012: ChatSessions, Beziehungsdynamik & 7-Stufen-Prompt

## 🎯 Ziel & Umfang
Zentrale Rollenspiel- und Chatlogik: `ChatSession`, `Message`, Beziehungsdynamik (+0.1 pro Nachricht, -0.1 täglicher Decay), verbindliches 7-Stufen-Prompt-Layout mit Segment-Trennung und das Prinzip des sauberen Kontexts (Zero-Control-Tags).

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `domain/chat/`
- **Dateien:**
  - `domain/chat/models.py`
  - `domain/chat/services.py`
  - `domain/chat/prompt_builder.py`
  - `domain/chat/exceptions.py`

## 🔗 Abhängigkeiten
- `tasks/001_foundation_config_and_shared_utils.md`
- `tasks/006_domain_personas_and_vision_analysis.md`
- `tasks/008_domain_worldinfo_locations_and_events.md`
- `tasks/009_domain_characters_and_emotional_sprites.md`
- `tasks/011_domain_memories_and_tag_rag.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. `domain/chat/models.py`
- **`MessageRole` (Enum):** `USER = "user"`, `CHARACTER = "character"`, `SYSTEM = "system"`.
- **`Message` (Entity):**
  - `id: int | None`
  - `session_id: int`
  - `message_idx: int`
  - `role: MessageRole`
  - `english_content: str` (Kanonischer Text)
  - `localized_content: str` (Text für UI)
  - `image_path: str | None = None`
  - `image_alt_text: str | None = None`
  - `emotion_tag: str | None = None`
  - `created_at: datetime`
- **`ChatSession` (Entity):**
  - `id: int | None`
  - `user_id: int`
  - `character_id: int`
  - `persona_id: int` (nach 1. Benutzernachricht unveränderlich gesperrt)
  - `active_worldinfo_id: int | None` (Exklusiv: max 1 oder None)
  - `current_location_id: int | None`
  - `title: str` (dynamischer Titel)
  - `relationship_value: float = 0.0` (Gedeckelt von `-100.0` bis `+100.0`)
  - `events_enabled: bool = True` (Chat-Checkbox Opt-Out)
  - `cooldown_counter: int`
  - `last_message_at: datetime`
  - `parent_session_id: int | None = None` (für Forks)

### 2. `domain/chat/services.py`
- **Beziehungsdynamik:**
  - `apply_user_message_affection(session: ChatSession) -> None`: `session.relationship_value = min(100.0, session.relationship_value + 0.1)`.
  - `apply_time_decay(session: ChatSession, current_time: datetime) -> None`:
    - Berechnet vergangene Tage seit `session.last_message_at`: `days = (current_time - last_message_at).total_seconds() / 86400.0`.
    - Zieht `0.1 * days` ab, fest gedeckelt bei minimal `-100.0`.
- **Session-Management & Forking:**
  - `create_session(user_id: int, character: Character, persona_id: int, worldinfo_id: int | None) -> ChatSession`:
    - Setzt initialen Beziehungswert aus `character.initial_relationship`.
    - Initialisiert Cooldown (Zufall 10–100).
    - Erstellt die initiale `Message` mit `character.first_message` und `character.initial_location_id`.
  - `lock_persona(session: ChatSession) -> None`: Sperrt Persona nach 1. User-Nachricht.
  - `switch_worldinfo(session: ChatSession, new_worldinfo_id: int | None) -> None`
  - `fork_session(session: ChatSession, messages: list[Message], fork_point_idx: int) -> tuple[ChatSession, list[Message]]`:
    - Übernimmt nur Nachrichten mit `message.message_idx <= fork_point_idx`.

### 3. `domain/chat/prompt_builder.py`
- **Verbindliches 7-Stufen-Layout mit Begrenzern:**
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
- **Prinzip des sauberen Kontexts (Zero-Control-Tags):**
  - **Prompt-Reinheit:** Keine technischen Systemmeldungen (*"Ihr seid nach Wald gegangen"*), keine URLs oder Base64.
  - Bildanhänge fließen nur als übersetzter ALT-Text ein (`[Player shows an image: description]`).
  - Das Roleplay-Modell erhält **keine Anweisung**, Steuerbefehle auszugeben.
  - **Output-Reinheit:** Das Modell generiert reinen Fließtext. Nachgelagerter Klassifikations-Call ermittelt Emotion und Ortswechsel isoliert.

## ✅ Akzeptanzkriterien
- [x] Exakte 7-Stufen-Prompt-Assemblierung mit geschlossenen Begrenzern.
- [x] Beziehungsdynamik (+0.1 pro Nachricht, -0.1 pro Tag Inaktivität) strikt gedeckelt von -100 bis +100.
- [x] Persona-Sperre nach erster Benutzernachricht aktiv.
- [x] Reiner Rollenspieltext ohne eingebettete Steuercodes.
