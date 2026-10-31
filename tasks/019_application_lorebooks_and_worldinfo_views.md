# Task 019: Lorebook & WorldInfo Editors (Places & Events)

## 🎯 Goal & Scope
Implementation of editors for Lorebooks and WorldInfo including modal entry editor, 16:9 location uploads with Vision ALT expansion prompt, and Tab 2 for events with scope badges.

## 📂 Affected Layer & Files
- **Layer:** `application/lorebooks/`, `application/worldinfo/`, `templates/lorebooks/`, `templates/worldinfo/`
- **Files:**
  - `application/lorebooks/views.py`
  - `application/lorebooks/forms.py`
  - `templates/lorebooks/detail.html`
  - `application/worldinfo/views.py`
  - `application/worldinfo/forms.py`
  - `templates/worldinfo/detail.html`

## 🔗 Dependencies
- `tasks/007_domain_lorebooks_and_entries.md`
- `tasks/008_domain_worldinfo_locations_and_events.md`
- `tasks/013_infrastructure_repositories.md`
- `tasks/015_ui_theme_static_assets_and_base_template.md`

## 📝 Functional Specifications & Requirements

### 1. Lorebook Editor (`templates/lorebooks/detail.html`)
- Editable lorebook title.
- Tile overview of all entries:
  - **First Tile:** Placeholder with plus icon (`+`) to add entries.
  - Cards showing title, tags, and snippet preview.
- **Modal Overlay Frame for Entries:**
  - Title (`str`), tags (`list[str]`), description / prose (`textarea`).
  - Save and delete actions.

### 2. WorldInfo Editor (`templates/worldinfo/detail.html`)
- World title, icon upload / symbol (`icon`).
- **Tab 1: Places (Locations):**
  - Card gallery of all assigned locations; first card is Add tile (`+`).
  - **Modal Overlay Frame for Locations:**
    - Name, tags, description.
    - Image upload in landscape 16:9 format (PNG, JPG, WEBP).
    - **Vision-ALT & Expansion Dialog:** Following upload, the Vision model outputs an ALT text; dialog prompts: *"Would you like to expand the location description with this AI image description?"*.
    - Event assignment (list of events occurring here).
- **Tab 2: Events (Encounters):**
  - Grid view of all events; first card is Add tile (`+`).
  - Cards display title, probability (0–100%), one-shot status, and a distinct **scope badge** (specific place or *"Entire World"*).
  - **Modal Overlay Frame for Events:**
    - Title, probability (`0 - 100%`), one-shot toggle.
    - Scope: Dropdown ("Entire World" or location within this WorldInfo). **Rule:** Exclusively world or specific location.
    - Scenic prose description of the event.

## ✅ Acceptance Criteria
- [x] Add tile positioned first across all grids.
- [x] 16:9 background upload with interactive Vision ALT expansion prompt.
- [x] Events display scope badges and are exclusively bound to either the world or a specific location.
