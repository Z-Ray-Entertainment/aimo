# Task 002: SQLite Setup with WAL Mode & Concurrency

## 🎯 Goal & Scope
Set up SQLAlchemy engine and session management for SQLite with mandatory Write-Ahead Logging (WAL) mode configuration and concurrency protection to reliably prevent database locks during parallel SSE streaming, asynchronous memory generation, and vision analysis.

## 📂 Affected Layer & Files
- **Layer:** `infrastructure/`
- **Files:**
  - `infrastructure/database.py`

## 🔗 Dependencies
- `tasks/001_foundation_config_and_shared_utils.md`

## 📝 Functional Specifications & Requirements

### 1. SQLite Concurrency & WAL Mode
- SQLite connections must be initialized via event listeners (`engine.connect()` / `connect` event) with the following pragmas:
  - `PRAGMA journal_mode=WAL;` (allows concurrent readers alongside a single writer).
  - `PRAGMA busy_timeout=30000;` (30-second wait on write conflicts before failing with lock errors).
  - `PRAGMA synchronous=NORMAL;` (optimal performance with complete WAL durability).
  - `PRAGMA foreign_keys=ON;` (enforces relational integrity).

### 2. SQLAlchemy Engine & Session
- `Base`: Declarative base class for ORM mappings (`DeclarativeBase`).
- `engine`: Instance configured with connection URI from `Config.DATABASE_URI`.
- `session_factory`: `sessionmaker(autocommit=False, autoflush=False, bind=engine)`.
- Scoped session or transaction context manager (`get_db_session()`) that automatically rolls back on error and reliably closes the session.
- `init_db()` function to create all registered tables on application startup.

## ✅ Acceptance Criteria
- [x] SQLite engine initializes required pragmas (`journal_mode=WAL`, `busy_timeout=30000`, `foreign_keys=ON`).
- [x] `get_db_session()` provides thread-safe sessions as a generator / context manager.
- [x] `init_db()` successfully creates all registered ORM tables.
