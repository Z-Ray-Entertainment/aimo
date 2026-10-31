# Task 002: SQLite-Setup mit WAL-Mode & Concurrency

## 🎯 Ziel & Umfang
Erstellung der SQLAlchemy-Engine und Session-Verwaltung für SQLite mit zwingender WAL-Mode-Konfiguration (Write-Ahead Logging) und Concurrency-Absicherung, um Locks bei parallelem SSE-Streaming, asynchroner Memory-Generierung und Vision-Analysen zuverlässig zu verhindern.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `infrastructure/`
- **Dateien:**
  - `infrastructure/database.py`

## 🔗 Abhängigkeiten
- `tasks/001_foundation_config_and_shared_utils.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. SQLite Concurrency & WAL-Modus
- SQLite muss bei jeder Verbindungsherstellung über Event-Listener (`engine.connect()` / `connect` Event) mit folgenden Pragmas initialisiert werden:
  - `PRAGMA journal_mode=WAL;` (erlaubt parallele Leser und einen Schreiber).
  - `PRAGMA busy_timeout=30000;` (30 Sekunden Wartezeit bei Schreibkonflikten statt sofortigem Lock-Abbruch).
  - `PRAGMA synchronous=NORMAL;` (optimale Performance bei voller WAL-Sicherheit).
  - `PRAGMA foreign_keys=ON;` (Integritätssicherung relationaler Verknüpfungen).

### 2. SQLAlchemy Engine & Session
- `Base`: Deklarative Basisklasse für ORM-Mappings (`DeclarativeBase`).
- `engine`: Instanz mit Verbindungs-URI aus `Config.DATABASE_URI`.
- `session_factory`: `sessionmaker(autocommit=False, autoflush=False, bind=engine)`.
- Scoped Session bzw. Kontext-Manager für Transaktionen (`get_db_session()`), der bei Fehlern ein automatisches Rollback durchführt und die Session zuverlässig schließt.
- `init_db()`-Funktion zur Erstellung der Tabellenstruktur beim Systemstart.

## ✅ Akzeptanzkriterien
- [x] SQLite Engine initialisiert pragmas (`journal_mode=WAL`, `busy_timeout=30000`, `foreign_keys=ON`).
- [x] `get_db_session()` als Generator / Kontextmanager stellt threadsichere Sessions bereit.
- [x] `init_db()` erstellt alle registrierten ORM-Tabellen fehlerfrei.
