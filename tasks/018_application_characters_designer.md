# Task 018: Character Designer (Info Tab, Sparkle ✨, Sprites)

## 🎯 Goal & Scope
Implementation of the Character Designer (`/characters/new` and `/characters/<id>/edit`) with top action bar, Tab 1 (Main Information, AI Sparkle Button, unlockable gallery images), and Tab 2 (Emotional Sprites in stackview with eye modal).

## 📂 Affected Layer & Files
- **Layer:** `application/characters/`, `templates/characters/`
- **Files:**
  - `application/characters/views.py`
  - `application/characters/forms.py`
  - `templates/characters/creator.html`

## 🔗 Dependencies
- `tasks/009_domain_characters_and_emotional_sprites.md`
- `tasks/013_infrastructure_repositories.md`
- `tasks/015_ui_theme_static_assets_and_base_template.md`

## 📝 Functional Specifications & Requirements

### 1. Header & Action Bar
- Back button (`←`) to hub overview.
- Top action bar:
  - Visibility: Dropdown (`Private` / `Public`).
  - Save: Validates and persists the character.
  - Duplicate: Clones character into a new draft.
  - Delete: Removes character (with confirmation modal).

### 2. Tab 1: Main Information
- Name, gender (`male`, `female`, `non-binary`).
- Primary Portrait (mandatory upload).
- Description with Sparkle Button ✨:
  - Asynchronous invocation of Assistant model with prompt: *"You are a professional author crafting a character description based on this draft: {existing description}"*.
  - Writes refined text directly into the textarea.
- Dialogue examples (`list[str]`), First Message & initial location.
- Linked lorebooks (multi-select) and suggested WorldInfo (dropdown).
- Location preferences (preferred / disliked).
- Unlockable 9:16 Gallery Images:
  - List of images with threshold input (-100 to +100).
  - Add tile (`+`) to upload additional 9:16 artwork.
  - Delete overlay over each image.

### 3. Tab 2: Emotional Sprites
- Grid layout of all 28 emotions (`Emotion` enum); emotion title labeled below each image.
- Clicking an empty tile opens the upload modal (transparent PNG/WEBP).
- **Variants & Stackview:**
  - When a sprite exists: Small button with **Paper-Plus icon** (📄➕) to upload further variants.
  - When multiple sprites exist: Layered visual appearance (**Stackview**).
  - **Eye Button (👁️):** Renders only when multiple variants exist. Clicking opens a modal popup displaying all variants for that emotion with individual delete buttons.
  - For single sprites: Delete button overlays directly on hover.

## ✅ Acceptance Criteria
- [x] Sparkle button ✨ enhances textarea contents via AI author prompt.
- [x] Gallery images feature configurable thresholds (-100 to +100).
- [x] Sprite grid supports uploads, paper-plus variant additions, stackview, and eye viewer modal.
- [x] Form validation enforces name, gender, and primary portrait upload.
