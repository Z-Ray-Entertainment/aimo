import json
import sqlite3

from domain.worldinfo.models import Event, Location, WorldInfo
from infrastructure.database import get_db_session
from infrastructure.repositories.base import BaseRepository
from infrastructure.repositories.orm_models import format_datetime, parse_datetime


class WorldInfoRepository(BaseRepository[WorldInfo]):
    def list_visible(self, user_id: int) -> list[WorldInfo]:
        return self._list_visible("worldinfos", user_id, self._to_entity)

    def list_all(self, user_id: int | None = None) -> list[WorldInfo]:
        if user_id is not None:
            return self.list_visible(user_id)
        return self._list_all("worldinfos", self._to_entity)

    def get_by_id(self, worldinfo_id: int) -> WorldInfo | None:
        return self._get_by_id("worldinfos", worldinfo_id, self._to_entity)

    def create(self, worldinfo: WorldInfo) -> WorldInfo:
        created_str = format_datetime(worldinfo.created_at)
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO worldinfos (user_id, name, icon, visibility, initial_location_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    worldinfo.user_id,
                    worldinfo.name,
                    worldinfo.icon,
                    worldinfo.visibility,
                    worldinfo.initial_location_id,
                    created_str,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            row = conn.execute(
                "SELECT * FROM worldinfos WHERE id = ?",
                (new_id,),
            ).fetchone()
            return self._to_entity(row)

    def update(self, worldinfo: WorldInfo) -> WorldInfo:
        if worldinfo.id is None:
            return self.create(worldinfo)
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM worldinfos WHERE id = ?",
                (worldinfo.id,),
            ).fetchone()
            if existing is None:
                return self.create(worldinfo)
            conn.execute(
                """
                UPDATE worldinfos
                SET name = ?, icon = ?, visibility = ?, initial_location_id = ?
                WHERE id = ?
                """,
                (
                    worldinfo.name,
                    worldinfo.icon,
                    worldinfo.visibility,
                    worldinfo.initial_location_id,
                    worldinfo.id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM worldinfos WHERE id = ?",
                (worldinfo.id,),
            ).fetchone()
            return self._to_entity(row)

    def delete(self, worldinfo_id: int) -> bool:
        return self._delete_by_id("worldinfos", worldinfo_id)

    def add_location(self, location: Location) -> Location:
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO locations (
                    worldinfo_id, name, tags_json, description, background_image_path, vision_alt_text
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    location.worldinfo_id,
                    location.name,
                    json.dumps(location.tags),
                    location.description,
                    location.background_image_path,
                    location.vision_alt_text,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            row = conn.execute(
                "SELECT * FROM locations WHERE id = ?",
                (new_id,),
            ).fetchone()
            return self._loc_to_entity(row)

    def update_location(self, location: Location) -> Location:
        if location.id is None:
            return self.add_location(location)
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM locations WHERE id = ?",
                (location.id,),
            ).fetchone()
            if existing is None:
                return self.add_location(location)
            conn.execute(
                """
                UPDATE locations
                SET name = ?, tags_json = ?, description = ?, background_image_path = ?, vision_alt_text = ?
                WHERE id = ?
                """,
                (
                    location.name,
                    json.dumps(location.tags),
                    location.description,
                    location.background_image_path,
                    location.vision_alt_text,
                    location.id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM locations WHERE id = ?",
                (location.id,),
            ).fetchone()
            return self._loc_to_entity(row)

    def get_location(self, location_id: int) -> Location | None:
        return self._get_by_id("locations", location_id, self._loc_to_entity)

    def list_locations(self, worldinfo_id: int) -> list[Location]:
        return self._fetch_all(
            "SELECT * FROM locations WHERE worldinfo_id = ? ORDER BY id ASC",
            (worldinfo_id,),
            self._loc_to_entity,
        )

    def delete_location(self, location_id: int) -> bool:
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM locations WHERE id = ?",
                (location_id,),
            ).fetchone()
            if existing is None:
                return False
            conn.execute(
                "UPDATE worldinfos SET initial_location_id = NULL WHERE initial_location_id = ?",
                (location_id,),
            )
            conn.execute("DELETE FROM locations WHERE id = ?", (location_id,))
            return True

    def add_event(self, event: Event) -> Event:
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO events (
                    worldinfo_id, location_id, title, probability, one_shot, description
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.worldinfo_id,
                    event.location_id,
                    event.title,
                    event.probability,
                    1 if event.one_shot else 0,
                    event.description,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            row = conn.execute(
                "SELECT * FROM events WHERE id = ?",
                (new_id,),
            ).fetchone()
            return self._ev_to_entity(row)

    def update_event(self, event: Event) -> Event:
        if event.id is None:
            return self.add_event(event)
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM events WHERE id = ?",
                (event.id,),
            ).fetchone()
            if existing is None:
                return self.add_event(event)
            conn.execute(
                """
                UPDATE events
                SET location_id = ?, title = ?, probability = ?, one_shot = ?, description = ?
                WHERE id = ?
                """,
                (
                    event.location_id,
                    event.title,
                    event.probability,
                    1 if event.one_shot else 0,
                    event.description,
                    event.id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM events WHERE id = ?",
                (event.id,),
            ).fetchone()
            return self._ev_to_entity(row)

    def get_event(self, event_id: int) -> Event | None:
        return self._get_by_id("events", event_id, self._ev_to_entity)

    def list_events(self, worldinfo_id: int) -> list[Event]:
        return self._fetch_all(
            "SELECT * FROM events WHERE worldinfo_id = ? ORDER BY id ASC",
            (worldinfo_id,),
            self._ev_to_entity,
        )

    def delete_event(self, event_id: int) -> bool:
        return self._delete_by_id("events", event_id)

    @staticmethod
    def _to_entity(row: sqlite3.Row) -> WorldInfo:
        keys = row.keys()
        vis = str(row["visibility"]) if "visibility" in keys and row["visibility"] else "private"
        init_loc = (
            int(row["initial_location_id"])
            if "initial_location_id" in keys and row["initial_location_id"] is not None
            else None
        )
        return WorldInfo(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            name=str(row["name"]),
            icon=row["icon"] if row["icon"] is not None else None,
            visibility=vis,
            initial_location_id=init_loc,
            created_at=parse_datetime(row["created_at"]),
        )

    @staticmethod
    def _loc_to_entity(row: sqlite3.Row) -> Location:
        try:
            tags = json.loads(row["tags_json"])
        except json.JSONDecodeError:
            tags = []
        return Location(
            id=int(row["id"]),
            worldinfo_id=int(row["worldinfo_id"]),
            name=str(row["name"]),
            tags=list(tags) if isinstance(tags, list) else [],
            description=str(row["description"]),
            background_image_path=(
                str(row["background_image_path"])
                if row["background_image_path"] is not None
                else None
            ),
            vision_alt_text=(
                str(row["vision_alt_text"])
                if row["vision_alt_text"] is not None
                else None
            ),
        )

    @staticmethod
    def _ev_to_entity(row: sqlite3.Row) -> Event:
        return Event(
            id=int(row["id"]),
            worldinfo_id=int(row["worldinfo_id"]),
            location_id=int(row["location_id"]) if row["location_id"] is not None else None,
            title=str(row["title"]),
            probability=int(row["probability"]),
            one_shot=bool(row["one_shot"]),
            description=str(row["description"]),
        )
