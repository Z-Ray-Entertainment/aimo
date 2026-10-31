# Tasks — Sequential Implementation Roadmap

This directory contains atomic, step-by-step task packages for the full implementation of `aimo`. Each task file is self-contained and precisely specified, allowing it to be executed with minimal context overhead.

---

## 🧭 Guiding Principles for Implementation

1. **Strict Layer Separation (DDD):**
   - `domain/`: Pure business logic (no I/O, no HTTP, no frameworks, no direct SQL queries).
   - `infrastructure/`: Database, SQLite WAL mode, repositories, providers (LLM, ComfyUI, TTS), file storage.
   - `application/`: Controllers, web views, REST API endpoints (`application/api/`), decorators, forms.
   - `shared/`: Configuration, utilities, global exceptions.
2. **Decoupling via Interfaces:**
   - The core communicates exclusively through abstract interfaces (`LLMProvider`, `ImageGenProvider`, `VoiceTTSProvider`).
3. **Pure Roleplay Context (Zero-Control-Tags):**
   - The roleplay model writes pure narrative text without control tags. Classifications (emotion, location changes) run via separate, autonomous downstream calls.
4. **Headless Core & REST API:**
   - Exposure of a consistent REST API (`/api/...`) so alternative frontends (e.g., GTK4/Libadwaita for Flathub) can utilize identical logic.
5. **Modern RPG Theme:**
   - Semi-transparent background with cover image, warm light brown wood frames with rounded corners, subtle gold borders on buttons, monochrome navigation icons, colored relationship hearts.

---

## 📋 Task Overview

| Task ID | Title | Layer | Status |
| :--- | :--- | :--- | :--- |
| [`001_foundation_config_and_shared_utils.md`](001_foundation_config_and_shared_utils.md) | Base Configuration & Shared Utilities | `shared/` | Completed |
| [`002_infrastructure_database_sqlite_wal.md`](002_infrastructure_database_sqlite_wal.md) | SQLite Setup with WAL Mode & Concurrency | `infrastructure/` | Completed |
| [`003_domain_auth_and_permissions.md`](003_domain_auth_and_permissions.md) | Authentication & Functional Permission Model | `domain/auth`, `domain/permissions` | Completed |
| [`004_domain_settings_and_system_prompts.md`](004_domain_settings_and_system_prompts.md) | ServiceSettings & Editable System Prompts | `domain/settings` | Completed |
| [`005_infrastructure_provider_interfaces_and_adapters.md`](005_infrastructure_provider_interfaces_and_adapters.md) | Modular Provider Layer (LLM, ComfyUI, TTS Stub) | `infrastructure/` | Completed |
| [`006_domain_personas_and_vision_analysis.md`](006_domain_personas_and_vision_analysis.md) | Player Personas & Vision Appearance Analysis | `domain/personas` | Completed |
| [`007_domain_lorebooks_and_entries.md`](007_domain_lorebooks_and_entries.md) | Lorebooks & Lorebook Entries | `domain/lorebooks` | Completed |
| [`008_domain_worldinfo_locations_and_events.md`](008_domain_worldinfo_locations_and_events.md) | WorldInfo, Locations & Random Event Mechanics | `domain/worldinfo` | Completed |
| [`009_domain_characters_and_emotional_sprites.md`](009_domain_characters_and_emotional_sprites.md) | AI Characters, Emotions & Gallery Images | `domain/characters` | Completed |
| [`010_domain_translation_and_localization_layer.md`](010_domain_translation_and_localization_layer.md) | Translation Layer & English Canon | `domain/translation`, `infrastructure/` | Completed |
| [`011_domain_memories_and_tag_rag.md`](011_domain_memories_and_tag_rag.md) | Asynchronous Memories & Vectorless Tag-RAG | `domain/memories` | Completed |
| [`012_domain_chat_sessions_messages_and_prompt_builder.md`](012_domain_chat_sessions_messages_and_prompt_builder.md) | ChatSessions, Relationship Dynamics & 7-Stage Prompt | `domain/chat` | Completed |
| [`013_infrastructure_repositories.md`](013_infrastructure_repositories.md) | SQLAlchemy Repositories for All Domains | `infrastructure/repositories` | Completed |
| [`014_application_api_headless_core_rest_endpoints.md`](014_application_api_headless_core_rest_endpoints.md) | REST API Endpoints (SSE Stream, Chat, Entities) | `application/api/` | Completed |
| [`015_ui_theme_static_assets_and_base_template.md`](015_ui_theme_static_assets_and_base_template.md) | Modern RPG Theme CSS, Scripts & Base Template | `static/`, `templates/` | Completed |
| [`016_application_setup_and_auth_views.md`](016_application_setup_and_auth_views.md) | First-Boot Wizard & Login Controllers | `application/setup`, `application/auth` | Completed |
| [`017_application_overview_hub_dashboard.md`](017_application_overview_hub_dashboard.md) | Hub Dashboard (3-Tab Navigation & Persona Modal) | `application/overview` | Completed |
| [`018_application_characters_designer.md`](018_application_characters_designer.md) | Character Designer (Info Tab, Sparkle ✨, Sprites) | `application/characters` | Completed |
| [`019_application_lorebooks_and_worldinfo_views.md`](019_application_lorebooks_and_worldinfo_views.md) | Lorebook & WorldInfo Editors (Places & Events) | `application/lorebooks`, `application/worldinfo` | Completed |
| [`020_application_chat_interface_and_interaction.md`](020_application_chat_interface_and_interaction.md) | Chat UI, SSE Streaming, Countdown & ComfyUI | `application/chat` | Completed |
| [`021_application_admin_panel_and_service_views.md`](021_application_admin_panel_and_service_views.md) | Admin Dashboard, User Management & Services | `application/admin` | Completed |
| [`022_application_factory_wsgi_and_podman_container.md`](022_application_factory_wsgi_and_podman_container.md) | App Factory, WSGI Entry & Podman Rootless Image | Root | Completed |
