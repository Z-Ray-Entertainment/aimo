from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import uuid

from domain.chat.relationship import CANONICAL_RELATIONSHIP_TIERS
from shared.config import Config

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    creator_tag TEXT UNIQUE,
    language TEXT NOT NULL DEFAULT '',
    is_initial_admin INTEGER NOT NULL DEFAULT 0,
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


def set_db_path(target: Path | str | None) -> None:
    global _RESOLVED_DB_PATH
    if target is None:
        _RESOLVED_DB_PATH = None
    else:
        raw = str(target)
        if raw.startswith("sqlite:///"):
            raw = raw[len("sqlite:///") :]
        _RESOLVED_DB_PATH = Path(raw).resolve()


def _resolve_db_path(target: Path | str | None = None) -> Path:
    global _RESOLVED_DB_PATH
    if target is not None:
        raw_target = target
    elif _RESOLVED_DB_PATH is not None:
        return _RESOLVED_DB_PATH
    else:
        env_path = os.getenv("AIMO_DATABASE_PATH") or os.getenv("DATABASE_PATH")
        raw_target = env_path if env_path else Config.DATABASE_PATH

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
            if target is None and _RESOLVED_DB_PATH is None:
                _RESOLVED_DB_PATH = candidate
            return candidate
    except OSError:
        pass

    fallback_dir = Path("/tmp/aimo/data")
    fallback_dir.mkdir(parents=True, exist_ok=True)
    fallback_path = fallback_dir / candidate.name
    if target is None and _RESOLVED_DB_PATH is None:
        _RESOLVED_DB_PATH = fallback_path
    return fallback_path


def configure_sqlite_pragmas(connection: sqlite3.Connection) -> None:
    if getattr(connection, "in_transaction", False):
        try:
            connection.commit()
        except sqlite3.OperationalError:
            pass
    cursor = connection.cursor()
    try:
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
        except sqlite3.OperationalError:
            pass
        cursor.execute("PRAGMA busy_timeout=30000;")
        try:
            cursor.execute("PRAGMA synchronous=NORMAL;")
        except sqlite3.OperationalError:
            pass
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
        "ALTER TABLE characters ADD COLUMN appearance TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE lorebooks ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'",
        "ALTER TABLE worldinfos ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'",
        "ALTER TABLE worldinfos ADD COLUMN initial_location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL",
        "ALTER TABLE worldinfos ADD COLUMN cover_image_path TEXT",
        "ALTER TABLE worldinfos ADD COLUMN lorebook_id INTEGER REFERENCES lorebooks(id) ON DELETE SET NULL",
        "ALTER TABLE chat_sessions ADD COLUMN disabled_lorebook_ids_json TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE chat_sessions ADD COLUMN custom_lorebook_ids_json TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE lorebook_entries ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public'",
        "ALTER TABLE characters ADD COLUMN lorebook_world_conditions_json TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE system_settings ADD COLUMN classification_model TEXT NOT NULL DEFAULT 'hf.co/mradermacher/MN-Violet-Lotus-12B-GGUF:Q4_K_M'",
        "ALTER TABLE system_settings ADD COLUMN default_backdrop_path TEXT",
        "ALTER TABLE users ADD COLUMN creator_tag TEXT",
        "ALTER TABLE users ADD COLUMN language TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE characters ADD COLUMN collaborator_creator_tags_json TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE worldinfos ADD COLUMN collaborator_creator_tags_json TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE lorebooks ADD COLUMN collaborator_creator_tags_json TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE locations ADD COLUMN character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL",
        "ALTER TABLE chat_sessions ADD COLUMN initial_location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL",
        "ALTER TABLE chat_messages ADD COLUMN system_type TEXT",
        "ALTER TABLE chat_messages ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE chat_sessions ADD COLUMN thinking_enabled INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE system_settings ADD COLUMN dialogue_author_prompt TEXT",
        "ALTER TABLE system_settings ADD COLUMN llm_backend TEXT NOT NULL DEFAULT 'ollama'",
        "ALTER TABLE system_settings ADD COLUMN google_ai_api_key TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE system_settings ADD COLUMN image_gen_backend TEXT NOT NULL DEFAULT 'comfyui'",
        "ALTER TABLE system_settings ADD COLUMN google_ai_image_model TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE system_settings ADD COLUMN search_backend TEXT NOT NULL DEFAULT 'disabled'",
        "ALTER TABLE system_settings ADD COLUMN provider_configs_json TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE events ADD COLUMN min_relationship INTEGER",
        "ALTER TABLE events ADD COLUMN max_relationship INTEGER",
        "ALTER TABLE lorebooks ADD COLUMN is_proper_noun INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE lorebook_entries ADD COLUMN is_proper_noun INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE worldinfos ADD COLUMN is_proper_noun INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE locations ADD COLUMN is_proper_noun INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE events ADD COLUMN is_proper_noun INTEGER NOT NULL DEFAULT 0",
    ):
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass

    try:
        conn.execute(
            "UPDATE system_settings SET search_backend = 'searxng' "
            "WHERE searxng_enabled = 1 AND (search_backend IS NULL OR search_backend = 'disabled')"
        )
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("UPDATE chat_sessions SET initial_location_id = current_location_id WHERE initial_location_id IS NULL AND current_location_id IS NOT NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_locations_character_id ON locations (character_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_users_creator_tag ON users (creator_tag)")
        user_rows = conn.execute("SELECT id FROM users WHERE creator_tag IS NULL OR creator_tag = ''").fetchall()
        for u_row in user_rows:
            conn.execute("UPDATE users SET creator_tag = ? WHERE id = ?", (str(uuid.uuid4()), u_row["id"]))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS relationship_tiers (
                level INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                behavior_rules TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS relationship_tier_translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level INTEGER NOT NULL,
                language TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                behavior_rules TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(level, language)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_relationship_tier_trans_lookup ON relationship_tier_translations (level, language)"
        )
        now_str = datetime.now(timezone.utc).isoformat()
        for tier in CANONICAL_RELATIONSHIP_TIERS.values():
            conn.execute(
                """
                INSERT INTO relationship_tiers (level, name, description, behavior_rules, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(level) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    behavior_rules = excluded.behavior_rules,
                    updated_at = excluded.updated_at
                """,
                (tier.level, tier.name, tier.description, tier.behavior_rules, now_str),
            )
    except sqlite3.OperationalError:
        pass

    try:
        ev_cols = conn.execute("PRAGMA table_info(events)").fetchall()
        if ev_cols:
            has_char_col = any(c["name"] == "character_id" for c in ev_cols)
            wi_notnull = any(c["name"] == "worldinfo_id" and int(c["notnull"]) == 1 for c in ev_cols)
            if not has_char_col or wi_notnull:
                has_min_rel = any(c["name"] == "min_relationship" for c in ev_cols)
                has_max_rel = any(c["name"] == "max_relationship" for c in ev_cols)
                conn.execute(
                    """
                    CREATE TABLE events_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        worldinfo_id INTEGER REFERENCES worldinfos(id) ON DELETE CASCADE,
                        character_id INTEGER REFERENCES characters(id) ON DELETE CASCADE,
                        location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
                        title TEXT NOT NULL,
                        probability INTEGER NOT NULL DEFAULT 50,
                        one_shot INTEGER NOT NULL DEFAULT 0,
                        description TEXT NOT NULL DEFAULT '',
                        min_relationship INTEGER,
                        max_relationship INTEGER
                    )
                    """
                )
                char_expr = "character_id" if has_char_col else "NULL"
                min_rel_expr = "min_relationship" if has_min_rel else "NULL"
                max_rel_expr = "max_relationship" if has_max_rel else "NULL"
                conn.execute(
                    f"""
                    INSERT INTO events_new (id, worldinfo_id, character_id, location_id, title, probability, one_shot, description, min_relationship, max_relationship)
                    SELECT id, worldinfo_id, {char_expr}, location_id, title, probability, one_shot, description, {min_rel_expr}, {max_rel_expr} FROM events
                    """
                )
                conn.execute("DROP TABLE events")
                conn.execute("ALTER TABLE events_new RENAME TO events")
                conn.execute("CREATE INDEX IF NOT EXISTS ix_events_worldinfo_id ON events (worldinfo_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS ix_events_character_id ON events (character_id)")
    except sqlite3.OperationalError:
        pass

    _migrate_origin_language_and_seed_translations(conn)


def _migrate_origin_language_and_seed_translations(conn: sqlite3.Connection) -> None:
    try:
        admin_row = conn.execute(
            "SELECT language FROM users WHERE is_initial_admin = 1 ORDER BY id ASC LIMIT 1"
        ).fetchone()
        default_origin = (
            str(admin_row["language"]).strip().lower()[:2]
            if admin_row and admin_row["language"]
            else "en"
        )
        if not default_origin:
            default_origin = "en"

        migrated_any = False
        for table in ("characters", "worldinfos", "lorebooks", "personas"):
            cols = {
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if cols and "origin_language" not in cols:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN origin_language TEXT NOT NULL DEFAULT 'en'"
                )
                if default_origin != "en":
                    conn.execute(
                        f"UPDATE {table} SET origin_language = ?",
                        (default_origin,),
                    )
                migrated_any = True

        if not migrated_any:
            return

        now_str = format_datetime(datetime.now(timezone.utc))

        def _seed_field(entity_type: str, entity_id: int, field_name: str, lang: str, text: str) -> None:
            cleaned = (text or "").strip()
            if not cleaned:
                return
            conn.execute(
                """
                INSERT OR IGNORE INTO entity_field_translations (
                    entity_type, entity_id, field_name, language, text_content, is_outdated, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (entity_type, entity_id, field_name, lang, cleaned, now_str),
            )

        for row in conn.execute("SELECT id, origin_language, description, appearance, first_message, dialogue_examples_json FROM characters").fetchall():
            lang = str(row["origin_language"] or default_origin)[:2]
            cid = int(row["id"])
            _seed_field("character", cid, "description", lang, str(row["description"] or ""))
            _seed_field("character", cid, "appearance", lang, str(row["appearance"] or ""))
            _seed_field("character", cid, "first_message", lang, str(row["first_message"] or ""))
            raw_dlg = str(row["dialogue_examples_json"] or "").strip()
            if raw_dlg and raw_dlg != "[]":
                _seed_field("character", cid, "dialogue_examples", lang, raw_dlg)

        for row in conn.execute("SELECT id, origin_language, name FROM worldinfos").fetchall():
            lang = str(row["origin_language"] or default_origin)[:2]
            _seed_field("worldinfo", int(row["id"]), "name", lang, str(row["name"] or ""))

        for row in conn.execute("SELECT l.id, w.origin_language, l.name, l.description FROM locations l JOIN worldinfos w ON w.id = l.worldinfo_id").fetchall():
            lang = str(row["origin_language"] or default_origin)[:2]
            lid = int(row["id"])
            _seed_field("worldinfo_location", lid, "name", lang, str(row["name"] or ""))
            _seed_field("worldinfo_location", lid, "description", lang, str(row["description"] or ""))

        for row in conn.execute("SELECT e.id, COALESCE(w.origin_language, c.origin_language, ?) AS olang, e.title, e.description FROM events e LEFT JOIN worldinfos w ON w.id = e.worldinfo_id LEFT JOIN characters c ON c.id = e.character_id", (default_origin,)).fetchall():
            lang = str(row["olang"] or default_origin)[:2]
            eid = int(row["id"])
            _seed_field("worldinfo_event", eid, "title", lang, str(row["title"] or ""))
            _seed_field("worldinfo_event", eid, "description", lang, str(row["description"] or ""))

        for row in conn.execute("SELECT id, origin_language, name, description FROM lorebooks").fetchall():
            lang = str(row["origin_language"] or default_origin)[:2]
            lbid = int(row["id"])
            _seed_field("lorebook", lbid, "name", lang, str(row["name"] or ""))
            _seed_field("lorebook", lbid, "description", lang, str(row["description"] or ""))

        for row in conn.execute("SELECT le.id, lb.origin_language, le.title, le.content, le.tags_json FROM lorebook_entries le JOIN lorebooks lb ON lb.id = le.lorebook_id").fetchall():
            lang = str(row["origin_language"] or default_origin)[:2]
            leid = int(row["id"])
            _seed_field("lorebook_entry", leid, "title", lang, str(row["title"] or ""))
            _seed_field("lorebook_entry", leid, "content", lang, str(row["content"] or ""))
            _seed_field("lorebook_entry", leid, "tags", lang, str(row["tags_json"] or ""))

        for row in conn.execute("SELECT id, origin_language, description, appearance FROM personas").fetchall():
            lang = str(row["origin_language"] or default_origin)[:2]
            pid = int(row["id"])
            _seed_field("persona", pid, "description", lang, str(row["description"] or ""))
            _seed_field("persona", pid, "appearance", lang, str(row["appearance"] or ""))
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
