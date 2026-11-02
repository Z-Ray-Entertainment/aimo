import json
import sqlite3

from domain.chat.models import ChatSession, Message, MessageRole
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import format_datetime, parse_datetime


class ChatRepository:
    def list_sessions_for_character(
        self,
        character_id: int,
        user_id: int,
    ) -> list[ChatSession]:
        with get_db_session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chat_sessions
                WHERE character_id = ? AND user_id = ?
                ORDER BY last_message_at DESC, id DESC
                """,
                (character_id, user_id),
            ).fetchall()
            return [self._session_to_entity(row) for row in rows]

    def get_session(self, session_id: int) -> ChatSession | None:
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT * FROM chat_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            return self._session_to_entity(row)

    def create_session(self, chat_session: ChatSession) -> ChatSession:
        last_msg_str = format_datetime(chat_session.last_message_at)
        created_str = format_datetime(chat_session.created_at)
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO chat_sessions (
                    user_id, character_id, persona_id, active_worldinfo_id,
                    current_location_id, title, relationship_value, events_enabled,
                    cooldown_counter, last_message_at, parent_session_id,
                    persona_locked, triggered_event_ids_json, disabled_lorebook_ids_json,
                    custom_lorebook_ids_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_session.user_id,
                    chat_session.character_id,
                    chat_session.persona_id,
                    chat_session.active_worldinfo_id,
                    chat_session.current_location_id,
                    chat_session.title,
                    chat_session.relationship_value,
                    1 if chat_session.events_enabled else 0,
                    chat_session.cooldown_counter,
                    last_msg_str,
                    chat_session.parent_session_id,
                    1 if chat_session.persona_locked else 0,
                    json.dumps(sorted(chat_session.triggered_event_ids)),
                    json.dumps(sorted(chat_session.disabled_lorebook_ids)),
                    json.dumps(list(chat_session.custom_lorebook_ids)),
                    created_str,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            row = conn.execute(
                "SELECT * FROM chat_sessions WHERE id = ?",
                (new_id,),
            ).fetchone()
            return self._session_to_entity(row)

    def update_session(self, chat_session: ChatSession) -> ChatSession:
        if chat_session.id is None:
            return self.create_session(chat_session)
        last_msg_str = format_datetime(chat_session.last_message_at)
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ?",
                (chat_session.id,),
            ).fetchone()
            if existing is None:
                return self.create_session(chat_session)
            conn.execute(
                """
                UPDATE chat_sessions
                SET persona_id = ?, active_worldinfo_id = ?, current_location_id = ?,
                    title = ?, relationship_value = ?, events_enabled = ?,
                    cooldown_counter = ?, last_message_at = ?, persona_locked = ?,
                    triggered_event_ids_json = ?, disabled_lorebook_ids_json = ?,
                    custom_lorebook_ids_json = ?
                WHERE id = ?
                """,
                (
                    chat_session.persona_id,
                    chat_session.active_worldinfo_id,
                    chat_session.current_location_id,
                    chat_session.title,
                    chat_session.relationship_value,
                    1 if chat_session.events_enabled else 0,
                    chat_session.cooldown_counter,
                    last_msg_str,
                    1 if chat_session.persona_locked else 0,
                    json.dumps(sorted(chat_session.triggered_event_ids)),
                    json.dumps(sorted(chat_session.disabled_lorebook_ids)),
                    json.dumps(list(chat_session.custom_lorebook_ids)),
                    chat_session.id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM chat_sessions WHERE id = ?",
                (chat_session.id,),
            ).fetchone()
            return self._session_to_entity(row)

    def delete_session(self, session_id: int) -> bool:
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if existing is None:
                return False
            conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
            return True

    def add_message(self, message: Message) -> Message:
        created_str = format_datetime(message.created_at)
        with get_db_session() as conn:
            if message.message_idx < 0:
                max_row = conn.execute(
                    "SELECT MAX(message_idx) AS max_idx FROM chat_messages WHERE session_id = ?",
                    (message.session_id,),
                ).fetchone()
                max_idx = max_row["max_idx"] if max_row is not None else None
                message.message_idx = 0 if max_idx is None else int(max_idx) + 1

            cursor = conn.execute(
                """
                INSERT INTO chat_messages (
                    session_id, message_idx, role, english_content,
                    localized_content, image_path, image_alt_text, emotion_tag, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.session_id,
                    message.message_idx,
                    message.role.value,
                    message.english_content,
                    message.localized_content,
                    message.image_path,
                    message.image_alt_text,
                    message.emotion_tag,
                    created_str,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            row = conn.execute(
                "SELECT * FROM chat_messages WHERE id = ?",
                (new_id,),
            ).fetchone()
            return self._message_to_entity(row)

    def update_message(self, message: Message) -> Message:
        if message.id is None:
            return self.add_message(message)
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM chat_messages WHERE id = ?",
                (message.id,),
            ).fetchone()
            if existing is None:
                return self.add_message(message)
            conn.execute(
                """
                UPDATE chat_messages
                SET english_content = ?, localized_content = ?, image_path = ?,
                    image_alt_text = ?, emotion_tag = ?
                WHERE id = ?
                """,
                (
                    message.english_content,
                    message.localized_content,
                    message.image_path,
                    message.image_alt_text,
                    message.emotion_tag,
                    message.id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM chat_messages WHERE id = ?",
                (message.id,),
            ).fetchone()
            return self._message_to_entity(row)

    def get_message_by_idx(self, session_id: int, message_idx: int) -> Message | None:
        with get_db_session() as conn:
            row = conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE session_id = ? AND message_idx = ?
                ORDER BY id DESC LIMIT 1
                """,
                (session_id, message_idx),
            ).fetchone()
            if row is None:
                return None
            return self._message_to_entity(row)

    def get_messages(
        self,
        session_id: int,
        limit: int | None = 10,
    ) -> list[Message]:
        with get_db_session() as conn:
            if limit is not None and limit > 0:
                rows = conn.execute(
                    """
                    SELECT * FROM chat_messages
                    WHERE session_id = ?
                    ORDER BY message_idx DESC, id DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                ).fetchall()
                rows = list(reversed(rows))
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM chat_messages
                    WHERE session_id = ?
                    ORDER BY message_idx ASC, id ASC
                    """,
                    (session_id,),
                ).fetchall()
            return [self._message_to_entity(row) for row in rows]

    def get_next_message_idx(self, session_id: int) -> int:
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT MAX(message_idx) AS max_idx FROM chat_messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            max_idx = row["max_idx"] if row is not None else None
            return 0 if max_idx is None else int(max_idx) + 1

    def delete_messages_after(
        self,
        session_id: int,
        message_idx: int,
        inclusive: bool = True,
    ) -> int:
        operator = ">=" if inclusive else ">"
        with get_db_session() as conn:
            cursor = conn.execute(
                f"DELETE FROM chat_messages WHERE session_id = ? AND message_idx {operator} ?",
                (session_id, message_idx),
            )
            return int(cursor.rowcount or 0)

    @staticmethod
    def _session_to_entity(row: sqlite3.Row) -> ChatSession:
        try:
            trig_ids = set(int(x) for x in json.loads(str(row["triggered_event_ids_json"])))
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            trig_ids = set()

        keys = row.keys()
        try:
            disabled_lb_ids = (
                set(int(x) for x in json.loads(str(row["disabled_lorebook_ids_json"])))
                if "disabled_lorebook_ids_json" in keys and row["disabled_lorebook_ids_json"]
                else set()
            )
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            disabled_lb_ids = set()

        try:
            custom_lb_ids = (
                [int(x) for x in json.loads(str(row["custom_lorebook_ids_json"]))]
                if "custom_lorebook_ids_json" in keys and row["custom_lorebook_ids_json"]
                else []
            )
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            custom_lb_ids = []

        return ChatSession(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            character_id=int(row["character_id"]),
            persona_id=int(row["persona_id"]),
            active_worldinfo_id=(
                int(row["active_worldinfo_id"])
                if row["active_worldinfo_id"] is not None
                else None
            ),
            current_location_id=(
                int(row["current_location_id"])
                if row["current_location_id"] is not None
                else None
            ),
            title=str(row["title"]),
            relationship_value=float(row["relationship_value"]),
            events_enabled=bool(row["events_enabled"]),
            cooldown_counter=int(row["cooldown_counter"]),
            last_message_at=parse_datetime(row["last_message_at"]),
            parent_session_id=(
                int(row["parent_session_id"])
                if row["parent_session_id"] is not None
                else None
            ),
            persona_locked=bool(row["persona_locked"]),
            triggered_event_ids=trig_ids,
            disabled_lorebook_ids=disabled_lb_ids,
            custom_lorebook_ids=custom_lb_ids,
            created_at=parse_datetime(row["created_at"]),
        )

    @staticmethod
    def _message_to_entity(row: sqlite3.Row) -> Message:
        return Message(
            id=int(row["id"]),
            session_id=int(row["session_id"]),
            message_idx=int(row["message_idx"]),
            role=MessageRole.resolve(str(row["role"])),
            english_content=str(row["english_content"]),
            localized_content=str(row["localized_content"]),
            image_path=str(row["image_path"]) if row["image_path"] is not None else None,
            image_alt_text=(
                str(row["image_alt_text"]) if row["image_alt_text"] is not None else None
            ),
            emotion_tag=str(row["emotion_tag"]) if row["emotion_tag"] is not None else None,
            created_at=parse_datetime(row["created_at"]),
        )
