# Task 017: Hub Dashboard (3-Tab Navigation & Persona Modal)

## 🎯 Goal & Scope
Implementation of the central hub overview following user login, featuring a persona avatar button in the header, modal persona manager, and a 3-tab container (Characters 👤, Lorebooks 📜, WorldInfo 🌐).

## 📂 Affected Layer & Files
- **Layer:** `application/overview/`, `templates/overview/`
- **Files:**
  - `application/overview/views.py`
  - `templates/overview/index.html`

## 🔗 Dependencies
- `tasks/006_domain_personas_and_vision_analysis.md`
- `tasks/007_domain_lorebooks_and_entries.md`
- `tasks/008_domain_worldinfo_locations_and_events.md`
- `tasks/009_domain_characters_and_emotional_sprites.md`
- `tasks/015_ui_theme_static_assets_and_base_template.md`

## 📝 Functional Specifications & Requirements

### 1. Header & Default Persona Button
- Displays the avatar portrait of the user's current default persona in the top header.
- Clicking the avatar opens a **modal overlay for persona management**:
  - Grid view of all owned personas.
  - New persona creation tile (`+`).
  - Edit and delete actions (delete button disabled with explanatory tooltip when persona is used in active chats).

### 2. Tab 1: AI Characters (`👤`)
- **First Tile (New Character):** Placeholder tile with a green plus icon (`+`) matching the card flow (visible only with `character_create` permission). Clicking navigates to `/characters/new`.
- **Character Cards:**
  - Primary portrait as tile backdrop.
  - **Scrolling Overlay Text:** Presents character description within the frame.
  - **Speech Bubble Icon (Bottom-Left):** Shows total message count exchanged between user and character (only when count > 0).
  - **Relationship Status Bar (-100 to +100):**
    - Displays best relationship score across all user's chats with this character.
    - Dynamic color and heart icon: -100 dark red with broken heart (💔), +100 bright pink with sparkling heart (💖).
  - **Filters & Sorting:** New characters, gender (`Gender`), sort by "chatted before / never chatted".
  - Clicking opens the chat view for that character.

### 3. Tab 2: Lorebooks (`📜`)
- Grid view of all lorebooks.
- First tile: Add tile (`+`) to register a new lorebook (requires `lorebook_create` permission).
- Cards display title, tags, and entry count. Clicking opens `/lorebooks/<id>`.

### 4. Tab 3: WorldInfo (`🌐`)
- Grid view of all world settings.
- First tile: Add tile (`+`) to register a new world (requires `worldinfo_create` permission).
- Cards display icon symbol (`icon`), title, and location count. Clicking opens `/worldinfo/<id>`.

## ✅ Acceptance Criteria
- [x] 3-tab container with icons (`👤`, `📜`, `🌐`) switches seamlessly without full page reloads.
- [x] First tile with plus symbol respects user permissions (`character_create`, etc.).
- [x] Scrolling description text and relationship bar with dynamic hearts render cleanly on portrait cards.
- [x] Persona modal allows switching, creation, and respects active chat deletion locks.
