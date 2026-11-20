from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

from infrastructure.db.migrations import _ensure_incremental_migrations
from infrastructure.db.schema import SCHEMA_DDL
from shared.config import Config

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
