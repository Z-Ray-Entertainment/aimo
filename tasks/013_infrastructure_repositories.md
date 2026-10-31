# Task 013: SQLAlchemy Repositories for All Domains

## 🎯 Goal & Scope
Implementation of the persistence layer with SQLAlchemy ORM models and repositories for all domain entities. Clean decoupling: The domain remains unaware of SQLAlchemy models; repositories map between ORM structures and pure domain entities.

## 📂 Affected Layer & Files
- **Layer:** `infrastructure/repositories/`
- **Files:**
  - `infrastructure/repositories/orm_models.py`
  - `infrastructure/repositories/user_repository.py`
  - `infrastructure/repositories/persona_repository.py`
  - `infrastructure/repositories/lorebook_repository.py`
  - `infrastructure/repositories/worldinfo_repository.py`
  - `infrastructure/repositories/character_repository.py`
  - `infrastructure/repositories/chat_repository.py`
  - `infrastructure/repositories/memory_repository.py`
  - `infrastructure/repositories/translation_repository.py`
  - `infrastructure/repositories/settings_repository.py`

## 🔗 Dependencies
- `tasks/002_infrastructure_database_sqlite_wal.md`
- `tasks/003_domain_auth_and_permissions.md` through `tasks/012_domain_chat_sessions_messages_and_prompt_builder.md`

## 📝 Functional Specifications & Requirements

### 1. `infrastructure/repositories/orm_models.py`
SQLAlchemy table definitions for SQLite:
- `UserORM` (`users`), `PermissionORM` (`user_permissions`)
- `PersonaORM` (`personas`)
- `LorebookORM` (`lorebooks`), `LorebookEntryORM` (`lorebook_entries`)
- `WorldInfoORM` (`worldinfos`), `LocationORM` (`locations`), `EventORM` (`events`)
- `CharacterORM` (`characters`), `CharacterImageORM` (`character_images`), `SpriteORM` (`character_sprites`)
- `ChatSessionORM` (`chat_sessions`), `MessageORM` (`chat_messages`)
- `MemoryORM` (`memories`)
- `TranslationORM` (`translations`)
- `SettingsORM` (`system_settings`)

### 2. Repositories
Each repository encapsulates database operations and returns pure domain entities:
- **`UserRepository`:** `get_by_id`, `get_by_email`, `create`, `count_users`.
- **`PersonaRepository`:** `list_for_user`, `get_by_id`, `create`, `update`, `delete`, `is_used_in_any_session`.
- **`LorebookRepository`:** `list_for_user`, `get_by_id`, `add_entry`, `list_entries`, `delete_entry`.
- **`WorldInfoRepository`:** `list_all`, `get_by_id`, `add_location`, `list_locations`, `add_event`, `list_events`.
- **`CharacterRepository`:** `list_visible(user_id)`, `get_by_id`, `save`, `add_sprite`, `add_gallery_image`, `get_best_relationship_for_user(character_id, user_id)`.
- **`ChatRepository`:** `list_sessions_for_character(character_id, user_id)`, `get_session`, `create_session`, `add_message`, `get_messages(session_id, limit=10)`, `delete_messages_after(session_id, message_idx)`.
- **`MemoryRepository`:** `list_for_session(session_id)`, `add_memory`, `delete_after_idx(session_id, message_idx)`.
- **`TranslationRepository`:** `get_translation(source_hash, target_lang)`, `save_translation`, `invalidate(source_hash)`.
- **`SettingsRepository`:** `get_settings`, `save_settings`.

## ✅ Acceptance Criteria
- [x] Complete mappings for all domain entities.
- [x] Transaction safety guaranteed through `get_db_session()`.
- [x] No leaks of SQLAlchemy objects into the domain layer.
- [x] Cascading deletions and foreign key integrity (`foreign_keys=ON`) verified.
