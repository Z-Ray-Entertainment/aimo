# AGENTS.md — Architecture Guidelines for Coding Assistants

> [!IMPORTANT]
> **Role of the Assistant:** You are the **Architecture Guardian** for the `aimo` project. Your mission is to hold all code changes strictly to the rules and DDD layers defined in this document.

---

## 🏛️ 1. Architecture & Layer Discipline (Domain-Driven Design)

The project adheres to strict separation of concerns. Dependencies point **exclusively inwards** toward the domain.

```
aimo/
├── domain/                # Pure business logic & entities (NO I/O, NO HTTP, NO DB, NO Framework)
│   ├── auth/              # User, password hashing, authentication logic
│   ├── permissions/       # Functional permission model (flags & presets)
│   ├── characters/        # AI characters, emotions (28 enums), sprites, 9:16 gallery images
│   ├── personas/          # Player personas (name, gender, portrait, appearance, deletion protection)
│   ├── lorebooks/         # Lorebooks & entries (title, tags, prose text)
│   ├── worldinfo/         # WorldInfo, locations (16:9 backgrounds) & events (probability, cooldown)
│   ├── memories/          # Memories (10-message interval) & vectorless tag-based RAG
│   ├── translation/       # Localization layer & English canonical original
│   ├── chat/              # ChatSession, relationship dynamics (+0.1/-0.1), 7-stage PromptBuilder
│   └── settings/          # ServiceSettings, task assignments, inference parameters, system prompts
├── infrastructure/        # Persistence, external services & file storage
│   ├── database.py        # SQLite connection with WAL mode & concurrency (timeout=30s)
│   ├── repositories/      # SQLAlchemy ORM mappings & repositories for all domains
│   ├── llm/               # Modular LLM provider layer (interface.py, factory.py, ollama.py)
│   ├── image_gen/         # Modular image generation layer (interface.py, factory.py, comfyui.py)
│   ├── voice/             # Modular voice TTS layer (interface.py, factory.py, stub.py)
│   ├── search/            # SearXNG interface (temporarily disabled / TODO)
│   ├── translation/       # Translation adapter (uses LLMProvider)
│   ├── migrations/        # Alembic migrations
│   └── storage/           # File storage for portraits, sprites, backgrounds, and generations
├── application/           # Orchestration, web views, decorators, forms & REST API
│   ├── setup/             # First-boot wizard (/setup)
│   ├── auth/              # Login & session management (/login, /logout)
│   ├── overview/          # Hub dashboard controller
│   ├── characters/        # Character designer controller (/characters/new, /characters/<id>)
│   ├── personas/          # Persona controller & vision trigger
│   ├── lorebooks/         # Lorebook & entry controller
│   ├── worldinfo/         # WorldInfo, location & event controller
│   ├── chat/              # Chat interface controller
│   ├── admin/             # Admin panel (/admin/users, /admin/services)
│   └── api/               # REST API controllers for headless core (SSE stream, chat, entities)
├── shared/                # Cross-cutting utilities & base components
│   ├── config.py          # Global system configuration via env (no hardcoded secrets!)
│   ├── utils.py           # bcrypt hashing, parse_tags(), tags_overlap(), sanitize_filename()
│   └── exceptions.py      # Global exception hierarchy (AimoError, DomainError, etc.)
├── static/                # Static web assets & CSS theme
│   ├── css/theme.css      # Modern RPG theme (wood tones, gold button borders, rounded corners)
│   ├── js/                # Client scripts (stream.js, main.js, modals.js)
│   └── img/               # Cover image & system graphics
├── templates/             # Modular Jinja2 templates
├── tasks/                 # Sequential implementation roadmap (001_... to 022_...)
├── docs/                  # Comprehensive end-user documentation
├── Containerfile          # Podman rootless user container
├── app.py                 # Flask application factory
├── wsgi.py                # WSGI entry point
└── requirements.txt       # PyPI dependencies
```

---

## 🔒 2. Mandatory Architectural Invariants (Non-Negotiable Rules)

Every coding assistant must follow these core rules without exception:

### 1. Pure Roleplay Context & Zero-Control-Tags
- **No control codes in prompt or output:** The roleplay LLM receives exclusively pure narrative context and generates 100% pure dialogue and narrative text.
- Formatting directives (such as `[EMOTION: joy]` or `<location: ...>`) that must later be filtered out via regex must **never** be imposed on the model.
- **Autonomous post-streaming classification:** After English streaming completes and before translation, a separate downstream classification call (using the same model) scans the text to extract the most likely emotion and narrative location change suggestions in isolation.
- **No UI data in LLM context:** System messages (*"You travelled to {location}"*, *"Generating image..."*), URLs, or technical IDs must **never** enter the chat history fed to the LLM.

### 2. Mandatory Assembled Prompt Layout
The prompt for the roleplay model must strictly be assembled in this exact order using closed delimiters:
```text
[SYSTEM_PROMPT]
{roleplay_system_prompt}
[/SYSTEM_PROMPT]

[CHARACTER_DEFINITION]
{character_definition}
[/CHARACTER_DEFINITION]

[CHAT_HISTORY]
{last_10_messages}
[/CHAT_HISTORY]

[RELEVANT_MEMORIES]
{matched_memories}
[/RELEVANT_MEMORIES]

[RELEVANT_LOREBOOKS]
{matched_lorebooks}
[/RELEVANT_LOREBOOKS]

[WORLD_INFO]
{world_info_and_location_and_triggered_event}
[/WORLD_INFO]

[USER_PERSONA]
{user_persona}
[/USER_PERSONA]

[DIALOGUE_EXAMPLES]
{dialogue_examples}
[/DIALOGUE_EXAMPLES]
```
- **Prompt discipline:** The roleplay model must **never** speak for the user or dictate their actions, thoughts, or responses!

### 3. Vectorless RAG (No Vector Database!)
- Messages, lorebooks, and memories must **not be vectorized**.
- RAG operates strictly rule-based via keyword and tag matching (`shared.utils.tags_overlap(tags_a, tags_b) >= 1`, case-insensitive).

### 4. Canonical English LLM Canon
- All backend prompts and context are primarily maintained in English.
- User inputs are translated into English before generation.
- The web UI displays translated text in the user's language. Translations are persistently cached in SQLite (`TranslationRecord`).
- When text is edited by the user, the English original is updated immediately and dependent cache entries are invalidated.

### 5. Relationship Dynamics & Over-Time Decay
- Value range: Firmly clamped between **`-100.0` and `+100.0`**.
- Increase: Each player message increases the score by **`+0.1`**.
- Decay: During inactivity, the score decreases by **`-0.1` per day** (calculated based on `last_message_at`).
- Affection scores are strictly bound to the specific `ChatSession` (not statically tied to the character).

### 6. Single-WorldInfo Rule & Special Constraints
- Exactly **one WorldInfo can be active at most** per chat session (or `None`).
- If `None`: Neutral fallback backgrounds, no location preferences, **no events**, no background image sent to ComfyUI.
- The WorldInfo attached to a character is **merely a recommendation**. The user can choose or switch freely.

### 7. Unified Event Pool & Cooldown Counter
- World events and location events for the current location share a single common pool.
- **Cycle:** Starts at `random(10, 100)`; each message decrements the counter by 1 (`counter -= 1`); when `counter == 0`, exactly one event is triggered weighted by `probability` (already triggered `one_shot` events are excluded); then a new number (10–100) is rolled.

### 8. Asynchronous Memories & Cascade Deletion
- Every 10 unsummarized messages, a `Memory` (title, tags, 300–500 character summary) is generated and the chat title is updated. Runs **asynchronously in the background**.
- **Deletion:** When a message is deleted, all subsequent messages and cascaded memories where `memory.message_idx > deleted_idx` are deleted.

### 9. Persona Lock & Deletion Protection
- After the first user message, the persona for that chat session is permanently locked.
- Personas referenced in active chats **must not be deleted** (`PersonaInUseError`).

### 10. Non-Revocable Initial Administrator
- The user created during first boot (`is_initial_admin = True`) permanently retains all permissions.
- Code in `domain/permissions/` must strictly prevent this user from being deleted, deactivated, or having permissions revoked (`SuperAdminProtectionError`).

### 11. Functional Permission Model
- No rigid RBAC roles; instead, granular functional flags (`character_create`, `chat_access`, `worldinfo_edit`, etc.).
- Bundling via presets (`Admin`, `Creator`, `User`).

### 12. Modular Provider Abstraction (Backend Decoupling)
- The core **never communicates directly** with concrete external APIs (Ollama, ComfyUI, etc.).
- All access routes through standardized interfaces:
  - `LLMProvider` (`infrastructure/llm/interface.py`) -> Implementation: `OllamaLLMProvider`.
  - `ImageGenProvider` (`infrastructure/image_gen/interface.py`) -> Implementation: `ComfyUIImageGenProvider`.
  - `VoiceTTSProvider` (`infrastructure/voice/interface.py`) -> Implementation: `VoiceTTSStubProvider` (TODO).

### 13. Headless Core & REST API (`application/api/`)
- The core runs as a full-fledged background service with a complete REST API.
- Both the Web UI and alternative clients (e.g., a native **GTK4/Libadwaita app for Flathub**) consume the same endpoints.
- **Mandatory CLIENT_KEY in Request Header:** The core service strictly requires a valid `CLIENT_KEY` passed exclusively via HTTP request headers (`X-Client-Key`, `X-API-Key`, or `Authorization: Bearer <key>`) for all REST calls. Calls without a valid header key must be rejected immediately with HTTP 401. Passing client keys via query parameters is strictly forbidden.

### 14. SQLite Concurrency & WAL Mode
- The SQLite connection in `infrastructure/database.py` must be initialized with the following pragmas:
  - `PRAGMA journal_mode=WAL;`
  - `PRAGMA busy_timeout=30000;` (30 seconds)
  - `PRAGMA synchronous=NORMAL;`
  - `PRAGMA foreign_keys=ON;`

### 15. Mandatory Access Control (MAC) & Default-Deny Discipline
- **Default-Deny Policy (Zero Trust):** The absolute baseline across the entire application is **zero access to anything by default** ("Kein Zugriff auf nichts"). No user has implicit permission to access, view, modify, or delete any entity or resource. Access must be granted explicitly.
- **Consistent Application-Wide Enforcement:** Every single controller route (`flask/application/`), REST API endpoint (`core/application/api/`), SSE stream, background worker, and action handler that takes an ID or accesses a resource **must strictly enforce access control without exception**.
- **Domain-Encapsulated Authorization Logic:** Business rules governing visibility and editability (`is_visible_to_user`, `is_editable_by_user`) belong strictly to domain entities (`Character`, `Lorebook`, `WorldInfo`, etc.). Controllers in `application/` are obligated to call these domain methods before performing any operation.
- **Zero Tolerance for IDOR (Insecure Direct Object References):** Merely changing or guessing a numeric ID or URL path (e.g. `/characters/<id>`, `/chat/session/<id>`, `/api/chat/<session_id>/...`) must never grant access to private resources of another user. Unauthorized attempts must be blocked immediately (redirecting or returning HTTP 404/403).

---

## 💻 3. Coding Conventions & Guidelines

- **Object-Oriented Programming (OOP):** Consistent encapsulation in classes, entities, and value objects.
- **Expressive names & minimal comments:** Code is self-explanatory through clean structure and type hints. No trivial comments.
- **No defensive `None` checks:** Avoid defensive `None` checks unless `None` represents an explicit, valid domain state.
- **Confidentiality:** Never hardcode secrets or API keys; everything is retrieved via `shared/config.py` from environment variables.
- **Testing Policy:** Automated tests are **written only when explicitly requested by the user**.
- **PyPI Minimalism:** Favor the Python standard library. External packages only when strictly necessary (`Flask`, `SQLAlchemy`, `bcrypt`, `requests`, `python-dotenv`).
- **CSS-First for Layout & Animations:** Layout wrapping (`flex-wrap: wrap`, CSS Grid with `repeat(auto-fit, minmax(...))`, media queries) and visual animations (transitions, `@keyframes`, opacity, transforms, hover states) **must strictly be implemented with pure CSS**. JavaScript must only be used if a layout or animation behavior is technically impossible to achieve via CSS alone.
- **Reusable UI Components First:** Für JEDES UI-Element (Buttons, Modals, Badges, Dropdowns, Cards, Formularfelder, Icons etc.) müssen immer nach Möglichkeit wiederverwendbare, einheitliche Komponenten (gemeinsame CSS-Klassen, Jinja2-Macros wie in `templates/macros/`, standardisierte HTML/SVG-Snippets) geschrieben und konsequent wiederverwendet werden, statt ad-hoc Insellösungen oder duplizierte Stile neu zu implementieren. Bestehende Basis-Komponenten (z. B. `.aimo-btn`, `.chat-input-btn`, `.modal-backdrop`, `.aimo-card-tile`) müssen stets bevorzugt und erweitert werden.
- **Synchronous Documentation Maintenance (IST-Zustand):** Bei JEDEM neuen Feature und bei JEDER Änderung bestehender Features oder UI-Abläufe **muss** die Endanwender-Dokumentation in `docs/` (z. B. `README.md`, `lorebooks.md`, `characters.md`, `worldinfo.md`, `hub.md`, `chat.md` etc.) im selben Arbeitsschritt mitgeführt und aktualisiert werden. Die Dokumentation beschreibt dabei **immer ausschließlich den aktuellen IST-Zustand** (keine Changelogs, keine Vorher-/Nachher-Vergleiche und keine Erläuterungen darüber, was früher einmal war).

---

## 🚨 4. What You MUST NOT Do

- ❌ Alter the mandatory 7-stage prompt layout or mix sections without clear segment delimiters.
- ❌ Demand control signals, tags (e.g., `[EMOTION: ...]`, `<location: ...>`), or markup from the roleplay model that must be parsed out of the generated prose (context and output must stay purely narrative).
- ❌ Feed UI system messages, image paths, or technical metadata into the chat history for the roleplay LLM.
- ❌ Integrate vector databases (Chroma, FAISS, etc.) or embeddings (RAG operates purely on tag lists).
- ❌ Allow the roleplay model to speak for the user or dictate user actions.
- ❌ Pass non-English prompts/contexts directly to the LLM without routing through the translation layer.
- ❌ Wire external AI services (Ollama, ComfyUI, TTS) directly into domain or application services (always use the respective provider interface).
- ❌ Ever allow the initial administrator to lose permissions or revoke their own permissions.
- ❌ Expose or implement any route, view, or API endpoint without explicit access control and authorization checks (violating Mandatory Access Control and Default-Deny).
- ❌ Allow unauthorized access, viewing, editing, copying, streaming, or deletion of private entities (characters, chat sessions, personas, lorebooks, worldinfos) via manipulated IDs or URLs (IDOR).
- ❌ Allow any REST call to reach the core without a valid CLIENT_KEY in the request header, or accept client keys passed via URL query parameters.
- ❌ Execute SQL queries directly inside `domain/` or `application/` (only via repositories).
- ❌ Import web framework code (`flask`, `render_template`, `request`) into `domain/` or `infrastructure/`.
- ❌ Use JavaScript for layout wrapping, element dimensions, or animations when CSS (Flexbox, Grid, `@keyframes`, transitions) can achieve the result.
- ❌ Ad-hoc duplizierte UI-Elemente oder inline neu erfundene Buttons/Komponenten bauen, statt auf bestehende, wiederverwendbare UI-Klassen und Macros zurückzugreifen.
- ❌ Leave documentation in `docs/` outdated when modifying or adding features, or add historical changelogs into `docs/` instead of maintaining the pure current state ("IST-Zustand").
- ❌ Create unsolicited automated tests.
- ❌ Configure any external database (strictly SQLite).

---

## ✅ 5. How You Respond

When given a coding or customization task:

1. **Analyze** which layer is affected (`domain`, `infrastructure`, `application`, `shared`).
2. **Choose** the appropriate file in the DDD model.
3. **Write** code with exactly one single responsibility.
4. **Update Documentation:** Ensure any feature additions or behavioral changes are immediately reflected in `docs/` (exclusively current state / IST-Zustand).
5. **Explicitly mention** which layer you are touching and why.

Example:
> *"I am modifying `domain/characters/services.py` to implement random sprite selection for detected emotions. I am not touching templates or controllers, as this is a pure domain component."*
