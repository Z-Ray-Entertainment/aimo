# Task 015: Modern RPG Theme CSS, Scripts & Base Template

## 🎯 Goal & Scope
Implementation of the mandatory design system for the web interface: Modern RPG interface featuring warm wood frames, rounded corners, gold button borders, monochrome icons, colored status hearts, and a semi-transparent cover background.

## 📂 Affected Layer & Files
- **Layer:** `static/`, `templates/`
- **Files:**
  - `static/css/theme.css`
  - `static/js/main.js`
  - `static/js/stream.js`
  - `static/js/modals.js`
  - `templates/base.html`

## 🔗 Dependencies
- `tasks/001_foundation_config_and_shared_utils.md`

## 📝 Functional Specifications & Requirements

### 1. `static/css/theme.css` (Design Tokens & Styling)
- **Background:**
  - `background-image` featuring the cover illustration.
  - Dimmed, semi-transparent overlay (`backdrop-filter: blur(8px); background: rgba(20, 16, 12, 0.85);`).
- **Frames (Borders) & Radii:**
  - Light brown wood tones (`--border-wood: #A77445;`, `--border-wood-dark: #8B5A2B;`).
  - Rounded corners (`border-radius: 10px - 14px;`).
  - Applied to text fields (`input`), textareas (`textarea`), modals (`.modal-frame`), tiles (`.card-tile`), and portrait frames.
- **Buttons:**
  - Background: Warm leather/light-brown tone (`background: #6E472A;`).
  - Rounded corners (`border-radius: 8px - 12px;`).
  - Subtle gold border (`border: 1px solid #D4AF37;`), warm glowing effect on `:hover`.
- **Icons:**
  - Monochrome by default for navigation and tools (arrows, tabs, trash, plus, pencils).
  - Select icons in vibrant color:
    - Hearts: Color gradient from dark red (💔 at -100) to bright pink (💖 at +100).
    - Sparkles ✨ in glowing gold/violet.

### 2. Client Scripts (`static/js/`)
- `stream.js`: SSE streaming client for `/api/chat/<id>/stream`. Coordinates:
  - *"Thinking..."* state.
  - Dimmed, smaller rendering of raw English tokens.
  - Display of translation spinner.
  - Seamless replacement with localized German translation.
  - Location change countdown with shrinking red progress bar (60 seconds).
- `modals.js`: Generic accessible modals for persona management, sprite eye viewer, lorebook & location overlays.

### 3. `templates/base.html`
- Responsive HTML5 skeleton linking `theme.css`, meta tags, flash messages, and flexible template blocks (`{% block content %}`).

## ✅ Acceptance Criteria
- [x] Theme precisely matches RPG guidelines (wood tones, gold borders, rounded corners, cover background).
- [x] SSE streaming script cleanly replaces dimmed English text following translation.
- [x] 60-second countdown bar for location transitions operates reliably.
- [x] Monochrome default icons and colored status hearts styled accurately.
