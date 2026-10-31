from sqlalchemy import func, select, update

from domain.personas.models import Gender, UserPersona
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import ChatSessionORM, PersonaORM


class PersonaRepository:
    def list_for_user(self, user_id: int) -> list[UserPersona]:
        with get_db_session() as session:
            stmt = (
                select(PersonaORM)
                .where(PersonaORM.user_id == user_id)
                .order_by(PersonaORM.is_default.desc(), PersonaORM.id.asc())
            )
            rows = session.execute(stmt).scalars().all()
            return [self._to_entity(row) for row in rows]

    def get_by_id(self, persona_id: int) -> UserPersona | None:
        with get_db_session() as session:
            orm_persona = session.get(PersonaORM, persona_id)
            if orm_persona is None:
                return None
            return self._to_entity(orm_persona)

    def get_default_for_user(self, user_id: int) -> UserPersona | None:
        personas = self.list_for_user(user_id)
        if not personas:
            return None
        for p in personas:
            if p.is_default:
                return p
        return personas[0]

    def create(self, persona: UserPersona) -> UserPersona:
        with get_db_session() as session:
            if persona.is_default:
                session.execute(
                    update(PersonaORM)
                    .where(PersonaORM.user_id == persona.user_id)
                    .values(is_default=False)
                )
            orm_persona = PersonaORM(
                user_id=persona.user_id,
                name=persona.name,
                gender=persona.gender.value,
                portrait_path=persona.portrait_path,
                description=persona.description,
                appearance=persona.appearance,
                is_default=persona.is_default,
                created_at=persona.created_at,
            )
            session.add(orm_persona)
            session.flush()
            return self._to_entity(orm_persona)

    def update(self, persona: UserPersona) -> UserPersona:
        if persona.id is None:
            return self.create(persona)
        with get_db_session() as session:
            orm_persona = session.get(PersonaORM, persona.id)
            if orm_persona is None:
                return self.create(persona)
            if persona.is_default:
                session.execute(
                    update(PersonaORM)
                    .where(PersonaORM.user_id == persona.user_id)
                    .values(is_default=False)
                )
            orm_persona.name = persona.name
            orm_persona.gender = persona.gender.value
            orm_persona.portrait_path = persona.portrait_path
            orm_persona.description = persona.description
            orm_persona.appearance = persona.appearance
            orm_persona.is_default = persona.is_default
            session.flush()
            return self._to_entity(orm_persona)

    def set_default(self, user_id: int, persona_id: int) -> None:
        with get_db_session() as session:
            session.execute(
                update(PersonaORM)
                .where(PersonaORM.user_id == user_id)
                .values(is_default=False)
            )
            session.execute(
                update(PersonaORM)
                .where(PersonaORM.id == persona_id, PersonaORM.user_id == user_id)
                .values(is_default=True)
            )

    def delete(self, persona_id: int) -> bool:
        with get_db_session() as session:
            orm_persona = session.get(PersonaORM, persona_id)
            if orm_persona is None:
                return False
            session.delete(orm_persona)
            return True

    def is_used_in_any_session(self, persona_id: int) -> bool:
        with get_db_session() as session:
            stmt = (
                select(func.count())
                .select_from(ChatSessionORM)
                .where(ChatSessionORM.persona_id == persona_id)
            )
            count = int(session.execute(stmt).scalar_one() or 0)
            return count > 0

    @staticmethod
    def _to_entity(orm_persona: PersonaORM) -> UserPersona:
        return UserPersona(
            id=orm_persona.id,
            user_id=orm_persona.user_id,
            name=orm_persona.name,
            gender=Gender.resolve(orm_persona.gender),
            portrait_path=orm_persona.portrait_path,
            description=orm_persona.description,
            appearance=orm_persona.appearance,
            is_default=orm_persona.is_default,
            created_at=orm_persona.created_at,
        )
