from datetime import datetime, timezone
import sqlite3
import uuid

from domain.chat.relationship import CANONICAL_RELATIONSHIP_TIERS

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
        "ALTER TABLE worldinfos ADD COLUMN backdrop_image_path TEXT",
        "ALTER TABLE worldinfos ADD COLUMN lorebook_id INTEGER REFERENCES lorebooks(id) ON DELETE SET NULL",
        "ALTER TABLE chat_sessions ADD COLUMN disabled_lorebook_ids_json TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE chat_sessions ADD COLUMN custom_lorebook_ids_json TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE lorebook_entries ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public'",
        "ALTER TABLE characters ADD COLUMN lorebook_world_conditions_json TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE system_settings ADD COLUMN classification_model TEXT NOT NULL DEFAULT 'hf.co/mradermacher/MN-Violet-Lotus-12B-GGUF:Q4_K_M'",
        "ALTER TABLE system_settings ADD COLUMN default_backdrop_path TEXT",
        "ALTER TABLE users ADD COLUMN creator_tag TEXT",
        "ALTER TABLE users ADD COLUMN language TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE users ADD COLUMN ember_particles_enabled INTEGER NOT NULL DEFAULT 1",
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
