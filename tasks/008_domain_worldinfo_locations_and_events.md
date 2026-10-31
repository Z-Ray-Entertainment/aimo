# Task 008: WorldInfo, Locations & Random Event Mechanics

## 🎯 Goal & Scope
Management of worlds (`WorldInfo`), locations (`Location`) with 16:9 backgrounds, and random event mechanics featuring a unified event pool and a deterministic cooldown counter cycle (10–100 messages).

## 📂 Affected Layer & Files
- **Layer:** `domain/worldinfo/`
- **Files:**
  - `domain/worldinfo/models.py`
  - `domain/worldinfo/services.py`
  - `domain/worldinfo/exceptions.py`

## 🔗 Dependencies
- `tasks/001_foundation_config_and_shared_utils.md`

## 📝 Functional Specifications & Requirements

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
  - `background_image_path: str | None = None` (landscape 16:9)
  - `vision_alt_text: str | None = None`
- **`Event` (Entity):**
  - `id: int | None`
  - `worldinfo_id: int`
  - `location_id: int | None = None` (**Rule:** `None` = world event; `int` = bound to specific location).
  - `title: str`
  - `probability: int` (0 to 100%)
  - `one_shot: bool` (triggers at most once per session)
  - `description: str` (injected into roleplay prompt upon triggering)
- **`EventCooldownState` (Value Object):**
  - `current_counter: int`
  - `triggered_event_ids: set[int]`

### 2. `domain/worldinfo/services.py`
- **`WorldInfoService`:**
  - `create_worldinfo(user_id: int, name: str, icon: str | None = None) -> WorldInfo`
  - `add_location(worldinfo_id: int, name: str, tags: list[str], description: str, bg_path: str | None = None) -> Location`
  - `add_event(worldinfo_id: int, title: str, description: str, probability: int, one_shot: bool = False, location_id: int | None = None) -> Event`
  - **Cooldown & Event Mechanics:**
    - `initialize_cooldown() -> int`: Rolls a random integer between **10 and 100** (`random.randint(10, 100)`).
    - `decrement_cooldown(state: EventCooldownState) -> bool`: Decrements counter by 1 (`state.current_counter -= 1`). Returns `True` when `current_counter <= 0`.
    - `draw_event(worldinfo_events: list[Event], current_location_id: int | None, state: EventCooldownState) -> Event | None`:
      - **Unified Pool:** Combines world events (`location_id is None`) and location events (`location_id == current_location_id`).
      - **Filter:** Excludes events where `one_shot == True` and the ID is already in `state.triggered_event_ids`.
      - **Weighted Draw:** Random draw weighted by `probability` (higher probability = higher chance). Always draws **exactly ONE event**.
      - Records ID for `one_shot` events in `state.triggered_event_ids`.
      - Assigns a newly rolled random number (10 to 100) to `state.current_counter`.

### 3. `domain/worldinfo/exceptions.py`
- `WorldInfoNotFoundError`, `LocationNotFoundError`, `EventNotFoundError`.

## ✅ Acceptance Criteria
- [x] Clean separation of world events and location events in a single drawing pool.
- [x] Cooldown counter deterministically decrements by 1 per chat message (user & AI).
- [x] At `counter == 0`, exactly one weighted event is triggered and cooldown is re-rolled (10–100).
- [x] One-shot events cannot trigger a second time within the same chat session.
