from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

from shared.config import Config

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_initial_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

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
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_lorebooks_user_id ON lorebooks (user_id);

CREATE TABLE IF NOT EXISTS lorebook_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lorebook_id INTEGER NOT NULL REFERENCES lorebooks(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    content TEXT NOT NULL DEFAULT '',
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
    initial_location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
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
    vision_alt_text TEXT
);
CREATE INDEX IF NOT EXISTS ix_locations_worldinfo_id ON locations (worldinfo_id);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worldinfo_id INTEGER NOT NULL REFERENCES worldinfos(id) ON DELETE CASCADE,
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    probability INTEGER NOT NULL DEFAULT 50,
    one_shot INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_events_worldinfo_id ON events (worldinfo_id);

CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    gender TEXT NOT NULL DEFAULT 'non-binary',
    visibility TEXT NOT NULL DEFAULT 'private',
    primary_portrait_path TEXT NOT NULL,
    avatar_path TEXT,
    card_image_path TEXT,
    description TEXT NOT NULL DEFAULT '',
    dialogue_examples_json TEXT NOT NULL DEFAULT '[]',
    linked_lorebook_ids_json TEXT NOT NULL DEFAULT '[]',
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
    title TEXT NOT NULL DEFAULT 'Chat Session',
    relationship_value REAL NOT NULL DEFAULT 0.0,
    events_enabled INTEGER NOT NULL DEFAULT 1,
    cooldown_counter INTEGER NOT NULL DEFAULT 25,
    last_message_at TEXT NOT NULL,
    parent_session_id INTEGER REFERENCES chat_sessions(id) ON DELETE SET NULL,
    persona_locked INTEGER NOT NULL DEFAULT 0,
    triggered_event_ids_json TEXT NOT NULL DEFAULT '[]',
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
    english_content TEXT NOT NULL DEFAULT '',
    localized_content TEXT NOT NULL DEFAULT '',
    image_path TEXT,
    image_alt_text TEXT,
    emotion_tag TEXT,
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

CREATE TABLE IF NOT EXISTS system_settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    ollama_url TEXT NOT NULL,
    comfyui_url TEXT NOT NULL,
    searxng_url TEXT NOT NULL,
    searxng_enabled INTEGER NOT NULL DEFAULT 0,
    roleplay_model TEXT NOT NULL DEFAULT 'igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest',
    memory_model TEXT NOT NULL DEFAULT 'igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest',
    assistant_model TEXT NOT NULL DEFAULT 'gemma4:e4b',
    classification_model TEXT NOT NULL DEFAULT 'llama3.2:1b',
    vision_model TEXT NOT NULL DEFAULT 'gemma4:e4b',
    num_ctx INTEGER NOT NULL DEFAULT 4096,
    temperature REAL NOT NULL DEFAULT 0.7,
    top_p REAL NOT NULL DEFAULT 0.9,
    repeat_penalty REAL NOT NULL DEFAULT 1.1,
    roleplay_prompt TEXT NOT NULL,
    memory_prompt TEXT NOT NULL,
    diffuser_prompt TEXT NOT NULL,
    sparkle_assistant_prompt TEXT NOT NULL,
    vision_persona_prompt TEXT NOT NULL,
    default_backdrop_path TEXT
);
"""

_RESOLVED_DB_PATH: Path | None = None


def format_datetime(dt: datetime | None) -> str:
    if dt is None:
        return datetime.now(timezone.utc).isoformat()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def parse_datetime(raw: str | datetime | None) -> datetime:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw
    if not raw:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(str(raw))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime.now(timezone.utc)


def _resolve_db_path(target: Path | str | None = None) -> Path:
    global _RESOLVED_DB_PATH
    if target is None and _RESOLVED_DB_PATH is not None:
        return _RESOLVED_DB_PATH

    raw_target = target if target is not None else Config.DATABASE_PATH
    if isinstance(raw_target, str):
        if raw_target.startswith("sqlite:///"):
            raw_target = raw_target[len("sqlite:///") :]
        candidate = Path(raw_target).resolve()
    else:
        candidate = raw_target.resolve()

    parent = candidate.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        if os.access(parent, os.W_OK):
            if target is None:
                _RESOLVED_DB_PATH = candidate
            return candidate
    except OSError:
        pass

    fallback_dir = Path("/tmp/aimo/data")
    fallback_dir.mkdir(parents=True, exist_ok=True)
    fallback_path = fallback_dir / candidate.name
    if target is None:
        _RESOLVED_DB_PATH = fallback_path
    return fallback_path


def configure_sqlite_pragmas(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
    finally:
        cursor.close()


def create_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    resolved_path = _resolve_db_path(db_path)
    try:
        conn = sqlite3.connect(
            str(resolved_path),
            timeout=30.0,
            check_same_thread=False,
        )
    except sqlite3.OperationalError:
        fallback_dir = Path("/tmp/aimo/data")
        fallback_dir.mkdir(parents=True, exist_ok=True)
        fallback_path = fallback_dir / resolved_path.name
        global _RESOLVED_DB_PATH
        _RESOLVED_DB_PATH = fallback_path
        conn = sqlite3.connect(
            str(fallback_path),
            timeout=30.0,
            check_same_thread=False,
        )
    conn.row_factory = sqlite3.Row
    configure_sqlite_pragmas(conn)
    return conn


_MIGRATED_PATHS: set[str] = set()


def _ensure_incremental_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
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
        )
        """
    )
    for stmt in (
        "ALTER TABLE characters ADD COLUMN avatar_path TEXT",
        "ALTER TABLE characters ADD COLUMN card_image_path TEXT",
        "ALTER TABLE lorebooks ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'",
        "ALTER TABLE worldinfos ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'",
        "ALTER TABLE worldinfos ADD COLUMN initial_location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL",
        "ALTER TABLE system_settings ADD COLUMN classification_model TEXT NOT NULL DEFAULT 'hf.co/mradermacher/MN-Violet-Lotus-12B-GGUF:Q4_K_M'",
        "ALTER TABLE system_settings ADD COLUMN default_backdrop_path TEXT",
    ):
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass


@contextmanager
def get_db_session(
    db_path: Path | str | None = None,
) -> Generator[sqlite3.Connection, None, None]:
    conn = create_connection(db_path)
    resolved_key = str(_resolve_db_path(db_path))
    if resolved_key not in _MIGRATED_PATHS:
        try:
            _ensure_incremental_migrations(conn)
            conn.commit()
            _MIGRATED_PATHS.add(resolved_key)
        except sqlite3.OperationalError:
            pass
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    with get_db_session(db_path) as conn:
        conn.executescript(SCHEMA_DDL)
        _ensure_incremental_migrations(conn)
        configure_sqlite_pragmas(conn)
