SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    creator_tag TEXT UNIQUE,
    language TEXT NOT NULL DEFAULT '',
    is_initial_admin INTEGER NOT NULL DEFAULT 0,
    ember_particles_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_creator_tag ON users (creator_tag);

CREATE TABLE IF NOT EXISTS user_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_user_permissions_user_id ON user_permissions (user_id);

CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    gender TEXT NOT NULL DEFAULT 'non-binary',
    portrait_path TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    appearance TEXT NOT NULL DEFAULT '',
    origin_language TEXT NOT NULL DEFAULT 'en',
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_personas_user_id ON personas (user_id);

CREATE TABLE IF NOT EXISTS lorebooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'private',
    origin_language TEXT NOT NULL DEFAULT 'en',
    collaborator_creator_tags_json TEXT NOT NULL DEFAULT '[]',
    is_proper_noun INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_lorebooks_user_id ON lorebooks (user_id);

CREATE TABLE IF NOT EXISTS lorebook_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lorebook_id INTEGER NOT NULL REFERENCES lorebooks(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    content TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'public',
    is_proper_noun INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_lorebook_entries_lorebook_id ON lorebook_entries (lorebook_id);

CREATE TABLE IF NOT EXISTS worldinfos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    icon TEXT,
    visibility TEXT NOT NULL DEFAULT 'private',
    cover_image_path TEXT,
    backdrop_image_path TEXT,
    lorebook_id INTEGER REFERENCES lorebooks(id) ON DELETE SET NULL,
    origin_language TEXT NOT NULL DEFAULT 'en',
    collaborator_creator_tags_json TEXT NOT NULL DEFAULT '[]',
    is_proper_noun INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_worldinfos_user_id ON worldinfos (user_id);

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worldinfo_id INTEGER NOT NULL REFERENCES worldinfos(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    description TEXT NOT NULL DEFAULT '',
    background_image_path TEXT,
    vision_alt_text TEXT,
    character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    is_proper_noun INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_locations_worldinfo_id ON locations (worldinfo_id);
CREATE INDEX IF NOT EXISTS ix_locations_character_id ON locations (character_id);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worldinfo_id INTEGER REFERENCES worldinfos(id) ON DELETE CASCADE,
    character_id INTEGER REFERENCES characters(id) ON DELETE CASCADE,
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    probability INTEGER NOT NULL DEFAULT 50,
    one_shot INTEGER NOT NULL DEFAULT 0,
    is_proper_noun INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT '',
    min_relationship INTEGER,
    max_relationship INTEGER
);
CREATE INDEX IF NOT EXISTS ix_events_worldinfo_id ON events (worldinfo_id);
CREATE INDEX IF NOT EXISTS ix_events_character_id ON events (character_id);

CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    gender TEXT NOT NULL DEFAULT 'non-binary',
    visibility TEXT NOT NULL DEFAULT 'private',
    origin_language TEXT NOT NULL DEFAULT 'en',
    collaborator_creator_tags_json TEXT NOT NULL DEFAULT '[]',
    primary_portrait_path TEXT NOT NULL,
    avatar_path TEXT,
    card_image_path TEXT,
    appearance TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    dialogue_examples_json TEXT NOT NULL DEFAULT '[]',
    linked_lorebook_ids_json TEXT NOT NULL DEFAULT '[]',
    lorebook_world_conditions_json TEXT NOT NULL DEFAULT '{}',
    suggested_worldinfo_id INTEGER REFERENCES worldinfos(id) ON DELETE SET NULL,
    first_message TEXT NOT NULL DEFAULT '',
    initial_location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    initial_relationship INTEGER NOT NULL DEFAULT 0,
    preferred_location_ids_json TEXT NOT NULL DEFAULT '[]',
    disliked_location_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_characters_user_id ON characters (user_id);

CREATE TABLE IF NOT EXISTS character_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    unlock_threshold INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_character_images_character_id ON character_images (character_id);

CREATE TABLE IF NOT EXISTS character_sprites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    emotion TEXT NOT NULL,
    variant INTEGER NOT NULL DEFAULT 1,
    file_path TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_character_sprites_character_id ON character_sprites (character_id);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE RESTRICT,
    active_worldinfo_id INTEGER REFERENCES worldinfos(id) ON DELETE SET NULL,
    current_location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    initial_location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    title TEXT NOT NULL DEFAULT 'Chat Session',
    relationship_value REAL NOT NULL DEFAULT 0.0,
    events_enabled INTEGER NOT NULL DEFAULT 1,
    thinking_enabled INTEGER NOT NULL DEFAULT 0,
    cooldown_counter INTEGER NOT NULL DEFAULT 25,
    last_message_at TEXT NOT NULL,
    parent_session_id INTEGER REFERENCES chat_sessions(id) ON DELETE SET NULL,
    persona_locked INTEGER NOT NULL DEFAULT 0,
    triggered_event_ids_json TEXT NOT NULL DEFAULT '[]',
    disabled_lorebook_ids_json TEXT NOT NULL DEFAULT '[]',
    custom_lorebook_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_chat_sessions_user_id ON chat_sessions (user_id);
CREATE INDEX IF NOT EXISTS ix_chat_sessions_character_id ON chat_sessions (character_id);
CREATE INDEX IF NOT EXISTS ix_chat_sessions_persona_id ON chat_sessions (persona_id);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_idx INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    english_content TEXT NOT NULL DEFAULT '',
    localized_content TEXT NOT NULL DEFAULT '',
    image_path TEXT,
    image_alt_text TEXT,
    emotion_tag TEXT,
    system_type TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_chat_messages_session_id ON chat_messages (session_id);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_idx INTEGER NOT NULL,
    title TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_memories_chat_session_id ON memories (chat_session_id);

CREATE TABLE IF NOT EXISTS translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_hash TEXT NOT NULL,
    english_text TEXT NOT NULL,
    target_language TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_translations_source_hash ON translations (source_hash);
CREATE INDEX IF NOT EXISTS ix_translations_target_language ON translations (target_language);

CREATE TABLE IF NOT EXISTS entity_field_translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    language TEXT NOT NULL,
    text_content TEXT NOT NULL,
    is_outdated INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    UNIQUE(entity_type, entity_id, field_name, language)
);
CREATE INDEX IF NOT EXISTS ix_entity_field_trans_lookup
    ON entity_field_translations (entity_type, entity_id, field_name);

CREATE TABLE IF NOT EXISTS relationship_tiers (
    level INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    behavior_rules TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relationship_tier_translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level INTEGER NOT NULL,
    language TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    behavior_rules TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(level, language)
);
CREATE INDEX IF NOT EXISTS ix_relationship_tier_trans_lookup
    ON relationship_tier_translations (level, language);

CREATE TABLE IF NOT EXISTS system_settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    llm_backend TEXT NOT NULL DEFAULT 'ollama',
    ollama_url TEXT NOT NULL DEFAULT '',
    google_ai_api_key TEXT NOT NULL DEFAULT '',
    image_gen_backend TEXT NOT NULL DEFAULT 'comfyui',
    google_ai_image_model TEXT NOT NULL DEFAULT '',
    comfyui_url TEXT NOT NULL DEFAULT '',
    search_backend TEXT NOT NULL DEFAULT 'disabled',
    searxng_url TEXT NOT NULL DEFAULT '',
    searxng_enabled INTEGER NOT NULL DEFAULT 0,
    provider_configs_json TEXT NOT NULL DEFAULT '{}',
    roleplay_model TEXT NOT NULL DEFAULT '',
    memory_model TEXT NOT NULL DEFAULT '',
    assistant_model TEXT NOT NULL DEFAULT '',
    classification_model TEXT NOT NULL DEFAULT '',
    vision_model TEXT NOT NULL DEFAULT '',
    num_ctx INTEGER NOT NULL DEFAULT 4096,
    temperature REAL NOT NULL DEFAULT 0.7,
    top_p REAL NOT NULL DEFAULT 0.9,
    repeat_penalty REAL NOT NULL DEFAULT 1.1,
    roleplay_prompt TEXT NOT NULL,
    memory_prompt TEXT NOT NULL,
    diffuser_prompt TEXT NOT NULL,
    sparkle_assistant_prompt TEXT NOT NULL,
    vision_persona_prompt TEXT NOT NULL,
    dialogue_author_prompt TEXT,
    default_backdrop_path TEXT
);
"""


