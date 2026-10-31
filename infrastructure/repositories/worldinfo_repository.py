import json

from sqlalchemy import select

from domain.worldinfo.models import Event, Location, WorldInfo
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import EventORM, LocationORM, WorldInfoORM


class WorldInfoRepository:
    def list_all(self) -> list[WorldInfo]:
        with get_db_session() as session:
            stmt = select(WorldInfoORM).order_by(WorldInfoORM.id.asc())
            rows = session.execute(stmt).scalars().all()
            return [self._to_entity(row) for row in rows]

    def get_by_id(self, worldinfo_id: int) -> WorldInfo | None:
        with get_db_session() as session:
            orm_wi = session.get(WorldInfoORM, worldinfo_id)
            if orm_wi is None:
                return None
            return self._to_entity(orm_wi)

    def create(self, worldinfo: WorldInfo) -> WorldInfo:
        with get_db_session() as session:
            orm_wi = WorldInfoORM(
                user_id=worldinfo.user_id,
                name=worldinfo.name,
                icon=worldinfo.icon,
                created_at=worldinfo.created_at,
            )
            session.add(orm_wi)
            session.flush()
            return self._to_entity(orm_wi)

    def update(self, worldinfo: WorldInfo) -> WorldInfo:
        if worldinfo.id is None:
            return self.create(worldinfo)
        with get_db_session() as session:
            orm_wi = session.get(WorldInfoORM, worldinfo.id)
            if orm_wi is None:
                return self.create(worldinfo)
            orm_wi.name = worldinfo.name
            orm_wi.icon = worldinfo.icon
            session.flush()
            return self._to_entity(orm_wi)

    def delete(self, worldinfo_id: int) -> bool:
        with get_db_session() as session:
            orm_wi = session.get(WorldInfoORM, worldinfo_id)
            if orm_wi is None:
                return False
            session.delete(orm_wi)
            return True

    def add_location(self, location: Location) -> Location:
        with get_db_session() as session:
            orm_loc = LocationORM(
                worldinfo_id=location.worldinfo_id,
                name=location.name,
                tags_json=json.dumps(location.tags),
                description=location.description,
                background_image_path=location.background_image_path,
                vision_alt_text=location.vision_alt_text,
            )
            session.add(orm_loc)
            session.flush()
            return self._loc_to_entity(orm_loc)

    def update_location(self, location: Location) -> Location:
        if location.id is None:
            return self.add_location(location)
        with get_db_session() as session:
            orm_loc = session.get(LocationORM, location.id)
            if orm_loc is None:
                return self.add_location(location)
            orm_loc.name = location.name
            orm_loc.tags_json = json.dumps(location.tags)
            orm_loc.description = location.description
            orm_loc.background_image_path = location.background_image_path
            orm_loc.vision_alt_text = location.vision_alt_text
            session.flush()
            return self._loc_to_entity(orm_loc)

    def get_location(self, location_id: int) -> Location | None:
        with get_db_session() as session:
            orm_loc = session.get(LocationORM, location_id)
            if orm_loc is None:
                return None
            return self._loc_to_entity(orm_loc)

    def list_locations(self, worldinfo_id: int) -> list[Location]:
        with get_db_session() as session:
            stmt = (
                select(LocationORM)
                .where(LocationORM.worldinfo_id == worldinfo_id)
                .order_by(LocationORM.id.asc())
            )
            rows = session.execute(stmt).scalars().all()
            return [self._loc_to_entity(row) for row in rows]

    def delete_location(self, location_id: int) -> bool:
        with get_db_session() as session:
            orm_loc = session.get(LocationORM, location_id)
            if orm_loc is None:
                return False
            session.delete(orm_loc)
            return True

    def add_event(self, event: Event) -> Event:
        with get_db_session() as session:
            orm_ev = EventORM(
                worldinfo_id=event.worldinfo_id,
                location_id=event.location_id,
                title=event.title,
                probability=event.probability,
                one_shot=event.one_shot,
                description=event.description,
            )
            session.add(orm_ev)
            session.flush()
            return self._ev_to_entity(orm_ev)

    def update_event(self, event: Event) -> Event:
        if event.id is None:
            return self.add_event(event)
        with get_db_session() as session:
            orm_ev = session.get(EventORM, event.id)
            if orm_ev is None:
                return self.add_event(event)
            orm_ev.location_id = event.location_id
            orm_ev.title = event.title
            orm_ev.probability = event.probability
            orm_ev.one_shot = event.one_shot
            orm_ev.description = event.description
            session.flush()
            return self._ev_to_entity(orm_ev)

    def get_event(self, event_id: int) -> Event | None:
        with get_db_session() as session:
            orm_ev = session.get(EventORM, event_id)
            if orm_ev is None:
                return None
            return self._ev_to_entity(orm_ev)

    def list_events(self, worldinfo_id: int) -> list[Event]:
        with get_db_session() as session:
            stmt = (
                select(EventORM)
                .where(EventORM.worldinfo_id == worldinfo_id)
                .order_by(EventORM.id.asc())
            )
            rows = session.execute(stmt).scalars().all()
            return [self._ev_to_entity(row) for row in rows]

    def delete_event(self, event_id: int) -> bool:
        with get_db_session() as session:
            orm_ev = session.get(EventORM, event_id)
            if orm_ev is None:
                return False
            session.delete(orm_ev)
            return True

    @staticmethod
    def _to_entity(orm_wi: WorldInfoORM) -> WorldInfo:
        return WorldInfo(
            id=orm_wi.id,
            user_id=orm_wi.user_id,
            name=orm_wi.name,
            icon=orm_wi.icon,
            created_at=orm_wi.created_at,
        )

    @staticmethod
    def _loc_to_entity(orm_loc: LocationORM) -> Location:
        try:
            tags = json.loads(orm_loc.tags_json)
        except json.JSONDecodeError:
            tags = []
        return Location(
            id=orm_loc.id,
            worldinfo_id=orm_loc.worldinfo_id,
            name=orm_loc.name,
            tags=list(tags) if isinstance(tags, list) else [],
            description=orm_loc.description,
            background_image_path=orm_loc.background_image_path,
            vision_alt_text=orm_loc.vision_alt_text,
        )

    @staticmethod
    def _ev_to_entity(orm_ev: EventORM) -> Event:
        return Event(
            id=orm_ev.id,
            worldinfo_id=orm_ev.worldinfo_id,
            location_id=orm_ev.location_id,
            title=orm_ev.title,
            probability=orm_ev.probability,
            one_shot=orm_ev.one_shot,
            description=orm_ev.description,
        )
