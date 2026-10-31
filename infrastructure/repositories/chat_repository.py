import json

from sqlalchemy import delete, func, select

from domain.chat.models import ChatSession, Message, MessageRole
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import ChatSessionORM, MessageORM


class ChatRepository:
    def list_sessions_for_character(
        self,
        character_id: int,
        user_id: int,
    ) -> list[ChatSession]:
        with get_db_session() as session:
            stmt = (
                select(ChatSessionORM)
                .where(
                    ChatSessionORM.character_id == character_id,
                    ChatSessionORM.user_id == user_id,
                )
                .order_by(ChatSessionORM.last_message_at.desc(), ChatSessionORM.id.desc())
            )
            rows = session.execute(stmt).scalars().all()
            return [self._session_to_entity(row) for row in rows]

    def get_session(self, session_id: int) -> ChatSession | None:
        with get_db_session() as session:
            orm_sess = session.get(ChatSessionORM, session_id)
            if orm_sess is None:
                return None
            return self._session_to_entity(orm_sess)

    def create_session(self, chat_session: ChatSession) -> ChatSession:
        with get_db_session() as session:
            orm_sess = ChatSessionORM(
                user_id=chat_session.user_id,
                character_id=chat_session.character_id,
                persona_id=chat_session.persona_id,
                active_worldinfo_id=chat_session.active_worldinfo_id,
                current_location_id=chat_session.current_location_id,
                title=chat_session.title,
                relationship_value=chat_session.relationship_value,
                events_enabled=chat_session.events_enabled,
                cooldown_counter=chat_session.cooldown_counter,
                last_message_at=chat_session.last_message_at,
                parent_session_id=chat_session.parent_session_id,
                persona_locked=chat_session.persona_locked,
                triggered_event_ids_json=json.dumps(sorted(chat_session.triggered_event_ids)),
                created_at=chat_session.created_at,
            )
            session.add(orm_sess)
            session.flush()
            return self._session_to_entity(orm_sess)

    def update_session(self, chat_session: ChatSession) -> ChatSession:
        if chat_session.id is None:
            return self.create_session(chat_session)
        with get_db_session() as session:
            orm_sess = session.get(ChatSessionORM, chat_session.id)
            if orm_sess is None:
                return self.create_session(chat_session)
            orm_sess.persona_id = chat_session.persona_id
            orm_sess.active_worldinfo_id = chat_session.active_worldinfo_id
            orm_sess.current_location_id = chat_session.current_location_id
            orm_sess.title = chat_session.title
            orm_sess.relationship_value = chat_session.relationship_value
            orm_sess.events_enabled = chat_session.events_enabled
            orm_sess.cooldown_counter = chat_session.cooldown_counter
            orm_sess.last_message_at = chat_session.last_message_at
            orm_sess.persona_locked = chat_session.persona_locked
            orm_sess.triggered_event_ids_json = json.dumps(
                sorted(chat_session.triggered_event_ids)
            )
            session.flush()
            return self._session_to_entity(orm_sess)

    def delete_session(self, session_id: int) -> bool:
        with get_db_session() as session:
            orm_sess = session.get(ChatSessionORM, session_id)
            if orm_sess is None:
                return False
            session.delete(orm_sess)
            return True

    def add_message(self, message: Message) -> Message:
        with get_db_session() as session:
            if message.message_idx < 0:
                stmt = select(func.max(MessageORM.message_idx)).where(
                    MessageORM.session_id == message.session_id
                )
                max_idx = session.execute(stmt).scalar_one_or_none()
                message.message_idx = 0 if max_idx is None else int(max_idx) + 1

            orm_msg = MessageORM(
                session_id=message.session_id,
                message_idx=message.message_idx,
                role=message.role.value,
                english_content=message.english_content,
                localized_content=message.localized_content,
                image_path=message.image_path,
                image_alt_text=message.image_alt_text,
                emotion_tag=message.emotion_tag,
                created_at=message.created_at,
            )
            session.add(orm_msg)
            session.flush()
            return self._message_to_entity(orm_msg)

    def update_message(self, message: Message) -> Message:
        if message.id is None:
            return self.add_message(message)
        with get_db_session() as session:
            orm_msg = session.get(MessageORM, message.id)
            if orm_msg is None:
                return self.add_message(message)
            orm_msg.english_content = message.english_content
            orm_msg.localized_content = message.localized_content
            orm_msg.image_path = message.image_path
            orm_msg.image_alt_text = message.image_alt_text
            orm_msg.emotion_tag = message.emotion_tag
            session.flush()
            return self._message_to_entity(orm_msg)

    def get_message_by_idx(self, session_id: int, message_idx: int) -> Message | None:
        with get_db_session() as session:
            stmt = select(MessageORM).where(
                MessageORM.session_id == session_id,
                MessageORM.message_idx == message_idx,
            )
            orm_msg = session.execute(stmt).scalar_one_or_none()
            if orm_msg is None:
                return None
            return self._message_to_entity(orm_msg)

    def get_messages(
        self,
        session_id: int,
        limit: int | None = 10,
    ) -> list[Message]:
        with get_db_session() as session:
            if limit is not None and limit > 0:
                stmt = (
                    select(MessageORM)
                    .where(MessageORM.session_id == session_id)
                    .order_by(MessageORM.message_idx.desc(), MessageORM.id.desc())
                    .limit(limit)
                )
                rows = list(reversed(session.execute(stmt).scalars().all()))
            else:
                stmt = (
                    select(MessageORM)
                    .where(MessageORM.session_id == session_id)
                    .order_by(MessageORM.message_idx.asc(), MessageORM.id.asc())
                )
                rows = session.execute(stmt).scalars().all()
            return [self._message_to_entity(row) for row in rows]

    def get_next_message_idx(self, session_id: int) -> int:
        with get_db_session() as session:
            stmt = select(func.max(MessageORM.message_idx)).where(
                MessageORM.session_id == session_id
            )
            max_idx = session.execute(stmt).scalar_one_or_none()
            return 0 if max_idx is None else int(max_idx) + 1

    def delete_messages_after(
        self,
        session_id: int,
        message_idx: int,
        inclusive: bool = True,
    ) -> int:
        with get_db_session() as session:
            condition = (
                MessageORM.message_idx >= message_idx
                if inclusive
                else MessageORM.message_idx > message_idx
            )
            stmt = delete(MessageORM).where(
                MessageORM.session_id == session_id,
                condition,
            )
            res = session.execute(stmt)
            return int(res.rowcount or 0)

    @staticmethod
    def _session_to_entity(orm_sess: ChatSessionORM) -> ChatSession:
        try:
            trig_ids = set(int(x) for x in json.loads(orm_sess.triggered_event_ids_json))
        except (json.JSONDecodeError, TypeError, ValueError):
            trig_ids = set()

        return ChatSession(
            id=orm_sess.id,
            user_id=orm_sess.user_id,
            character_id=orm_sess.character_id,
            persona_id=orm_sess.persona_id,
            active_worldinfo_id=orm_sess.active_worldinfo_id,
            current_location_id=orm_sess.current_location_id,
            title=orm_sess.title,
            relationship_value=orm_sess.relationship_value,
            events_enabled=orm_sess.events_enabled,
            cooldown_counter=orm_sess.cooldown_counter,
            last_message_at=orm_sess.last_message_at,
            parent_session_id=orm_sess.parent_session_id,
            persona_locked=orm_sess.persona_locked,
            triggered_event_ids=trig_ids,
            created_at=orm_sess.created_at,
        )

    @staticmethod
    def _message_to_entity(orm_msg: MessageORM) -> Message:
        return Message(
            id=orm_msg.id,
            session_id=orm_msg.session_id,
            message_idx=orm_msg.message_idx,
            role=MessageRole.resolve(orm_msg.role),
            english_content=orm_msg.english_content,
            localized_content=orm_msg.localized_content,
            image_path=orm_msg.image_path,
            image_alt_text=orm_msg.image_alt_text,
            emotion_tag=orm_msg.emotion_tag,
            created_at=orm_msg.created_at,
        )
