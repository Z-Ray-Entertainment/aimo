from collections.abc import Generator
from contextlib import contextmanager
import importlib
import sqlite3
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, scoped_session, sessionmaker

from shared.config import Config


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy ORM models."""


def _build_connect_args(database_uri: str) -> dict[str, Any]:
    if database_uri.startswith("sqlite"):
        return {
            "check_same_thread": False,
            "timeout": 30.0,
        }
    return {}


def configure_sqlite_pragmas(target_engine: Engine) -> None:
    @event.listens_for(target_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA busy_timeout=30000;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA foreign_keys=ON;")
            finally:
                cursor.close()


def create_db_engine(database_uri: str = Config.DATABASE_URI) -> Engine:
    db_engine = create_engine(
        database_uri,
        connect_args=_build_connect_args(database_uri),
        pool_pre_ping=True,
    )
    configure_sqlite_pragmas(db_engine)
    return db_engine


engine: Engine = create_db_engine(Config.DATABASE_URI)

session_factory: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)

ScopedSession = scoped_session(session_factory)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(target_engine: Engine = engine) -> None:
    try:
        importlib.import_module("infrastructure.repositories.orm_models")
    except ModuleNotFoundError:
        pass
    Base.metadata.create_all(bind=target_engine)
