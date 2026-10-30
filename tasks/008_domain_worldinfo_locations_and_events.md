# Task 008: WorldInfo, Orte & Zufalls-Event-Mechanik

## 🎯 Ziel & Umfang
Verwaltung von Welten (`WorldInfo`), Orten (`Location`) mit 16:9-Hintergründen und der Zufalls-Event-Mechanik mit einheitlichem Event-Pool und deterministischem Cooldown-Zähler-Kreislauf (10–100 Nachrichten).

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `domain/worldinfo/`
- **Dateien:**
  - `domain/worldinfo/models.py`
  - `domain/worldinfo/services.py`
  - `domain/worldinfo/exceptions.py`

## 🔗 Abhängigkeiten
- `tasks/001_foundation_config_and_shared_utils.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. `domain/worldinfo/models.py`
- **`WorldInfo` (Entity):**
  - `id: int | None`
  - `user_id: int`
  - `name: str`
  - `icon: str | None = None`
  - `created_at: datetime`
- **`Location` (Entity):**
  - `id: int | None`
  - `worldinfo_id: int`
  - `name: str`
  - `tags: list[str]`
  - `description: str`
  - `background_image_path: str | None = None` (Querformat 16:9)
  - `vision_alt_text: str | None = None`
- **`Event` (Entity):**
  - `id: int | None`
  - `worldinfo_id: int`
  - `location_id: int | None = None` (**Regel:** `None` = Welt-Event; `int` = an konkreten Ort gebunden).
  - `title: str`
  - `probability: int` (0 bis 100%)
  - `one_shot: bool` (darf in einer Session maximal 1x feuern)
  - `description: str` (fließt bei Auslösung in den Rollenspiel-Prompt ein)
- **`EventCooldownState` (Value Object):**
  - `current_counter: int`
  - `triggered_event_ids: set[int]`

### 2. `domain/worldinfo/services.py`
- **`WorldInfoService`:**
  - `create_worldinfo(user_id: int, name: str, icon: str | None = None) -> WorldInfo`
  - `add_location(worldinfo_id: int, name: str, tags: list[str], description: str, bg_path: str | None = None) -> Location`
  - `add_event(worldinfo_id: int, title: str, description: str, probability: int, one_shot: bool = False, location_id: int | None = None) -> Event`
  - **Cooldown- & Event-Mechanik:**
    - `initialize_cooldown() -> int`: Würfelt Zufallszahl zwischen **10 und 100** (`random.randint(10, 100)`).
    - `decrement_cooldown(state: EventCooldownState) -> bool`: Verringert den Zähler um 1 (`state.current_counter -= 1`). Gibt `True` zurück, wenn `current_counter <= 0` erreicht ist.
    - `draw_event(worldinfo_events: list[Event], current_location_id: int | None, state: EventCooldownState) -> Event | None`:
      - **Einheitlicher Pool:** Bündelt Welt-Events (`location_id is None`) und Orts-Events (`location_id == current_location_id`).
      - **Filter:** Schließt Events aus, die `one_shot == True` sind und deren ID in `state.triggered_event_ids` liegt.
      - **Gewichtete Ziehung:** Zufällige Auswahl gewichtet anhand der `probability` (hohe Wahrscheinlichkeit = höhere Eintrittschance). Es wird stets **genau EIN Event** gezogen.
      - Merkt die ID bei `one_shot`-Events in `state.triggered_event_ids` vor.
      - Weist `state.current_counter` eine neue Zufallszahl (10 bis 100) zu.

### 3. `domain/worldinfo/exceptions.py`
- `WorldInfoNotFoundError`, `LocationNotFoundError`, `EventNotFoundError`.

## ✅ Akzeptanzkriterien
- [ ] Saubere Trennung zwischen Welt-Events und Orts-Events in einem gemeinsamen Ziehungspool.
- [ ] Cooldown-Zähler dekrementiert pro Chat-Nachricht (Spieler & KI) deterministisch um 1.
- [ ] Bei `counter == 0` wird genau ein gewichtetes Event ausgelöst und der Cooldown neu gewürfelt (10–100).
- [ ] One-Shot-Events können in derselben Chat-Session kein zweites Mal feuern.
