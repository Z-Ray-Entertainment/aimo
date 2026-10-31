# Task 014: REST API Endpoints (Headless Core)

## 🎯 Goal & Scope
Provide the central REST API (`/api/...`) to control the system as an autonomous background daemon ("Headless Core"). Enables consistent access for the Web UI and alternative frontends (such as a native GTK4/Libadwaita app for Flathub).

## 📂 Affected Layer & Files
- **Layer:** `application/api/`
- **Files:**
  - `application/api/chat.py`
  - `application/api/characters.py`
  - `application/api/personas.py`
  - `application/api/worldinfo.py`
  - `application/api/lorebooks.py`
  - `application/api/admin.py`

## 🔗 Dependencies
- `tasks/013_infrastructure_repositories.md`
- `tasks/012_domain_chat_sessions_messages_and_prompt_builder.md`

## 📝 Functional Specifications & Requirements

### 1. `application/api/chat.py`
- `POST /api/chat/<id>/messages`:
  - Receives user message (optionally with image upload).
  - Translates message into canonical English.
  - Checks cooldown & optionally triggers an event from the unified pool.
  - Assembles 7-stage prompt.
  - Yields SSE stream (`/api/chat/<id>/stream`):
    - Event `token`: Raw English tokens for live streaming.
    - Event `generation_done`: Generation finished.
    - **Downstream Classification Call:** Identifies emotion and location transitions in isolation.
    - **Translation:** Translates English response into the user's localized language.
    - Event `message_complete`: Delivers localized text, selected sprite, and optional location suggestion.
    - **Asynchronous Background Task:** Memory inspection every 10 messages.
- `POST /api/chat/<id>/switch-location`: Confirms location change, switches background.
- `POST /api/chat/<id>/cancel-image`: Aborts active ComfyUI image generation.
- `POST /api/chat/<id>/fork`: Creates a chat clone starting from `fork_point_idx`.
- `DELETE /api/chat/<id>/messages/<idx>`: Deletes message and cascades deletion to subsequent messages and memories.

### 2. `application/api/characters.py` & Related Endpoints
- `GET /api/characters`: List of visible characters with relationship scores and message counts.
- `POST /api/characters`: Character creation (including sprites and gallery images).
- `GET /api/personas`, `POST /api/personas`: Persona CRUD & Vision scan trigger.
- `GET /api/worldinfo`, `POST /api/worldinfo/events`: Worlds, locations, and events.
- `GET /api/lorebooks`: Lorebook management.

## ✅ Acceptance Criteria
- [x] SSE streaming delivers raw tokens followed by downstream classification and translation swap.
- [x] All core functionalities accessible via pure JSON/REST endpoints.
- [x] Full architectural decoupling for alternative frontends (GTK4/Flathub).
