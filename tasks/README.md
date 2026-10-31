# Tasks — Sequenzieller Implementierungs-Fahrplan

Dieser Ordner enthält die atomaren, schrittweisen Aufgabenpakete für die vollständige Implementierung von `aimo`. Jede Task-Datei ist in sich geschlossen und präzise spezifiziert, sodass sie mit minimalem Kontextaufwand abgearbeitet werden kann.

---

## 🧭 Leitprinzipien für die Bearbeitung

1. **Strikte Schichtentrennung (DDD):**
   - `domain/`: Reine Geschäftslogik (kein I/O, kein HTTP, keine Frameworks, keine SQL-Queries).
   - `infrastructure/`: Datenbank, SQLite WAL-Mode, Repositories, Provider (LLM, ComfyUI, TTS), Dateispeicher.
   - `application/`: Controller, Web-Views, REST-API-Endpunkte (`application/api/`), Decorators, Formulare.
   - `shared/`: Konfiguration, Utilities, globale Exceptions.
2. **Entkopplung über Interfaces:**
   - Der Kern kommuniziert ausschließlich mit abstrakten Interfaces (`LLMProvider`, `ImageGenProvider`, `VoiceTTSProvider`).
3. **Reiner Roleplay-Kontext (Zero-Control-Tags):**
   - Das Roleplay-Modell schreibt reinen Fließtext ohne Steuercodes. Klassifikationen (Emotion, Ortswechsel) laufen über separate, autarke Nachverarbeitungs-Calls.
4. **Headless Core & REST-API:**
   - Bereitstellung einer konsistenten REST-API (`/api/...`), damit alternative Frontends (z. B. GTK4/Libadwaita für Flathub) dieselbe Logik nutzen können.
5. **Modernes RPG-Theme:**
   - Halbtransparenter Hintergrund mit Cover-Image, warme hellbraune Holzrahmen mit abgerundeten Ecken, feiner Goldrand bei Buttons, monochrome Standard-Icons, farbige Status-Herzen.

---

## 📋 Übersicht aller Tasks

| Task-ID | Titel | Schicht | Status |
| :--- | :--- | :--- | :--- |
| [`001_foundation_config_and_shared_utils.md`](001_foundation_config_and_shared_utils.md) | Basiskonfiguration & Shared Utilities | `shared/` | Erledigt |
| [`002_infrastructure_database_sqlite_wal.md`](002_infrastructure_database_sqlite_wal.md) | SQLite-Setup mit WAL-Mode & Concurrency | `infrastructure/` | Erledigt |
| [`003_domain_auth_and_permissions.md`](003_domain_auth_and_permissions.md) | Authentifizierung & Funktionales Rechtemodell | `domain/auth`, `domain/permissions` | Erledigt |
| [`004_domain_settings_and_system_prompts.md`](004_domain_settings_and_system_prompts.md) | ServiceSettings & Editierbare System-Prompts | `domain/settings` | Erledigt |
| [`005_infrastructure_provider_interfaces_and_adapters.md`](005_infrastructure_provider_interfaces_and_adapters.md) | Modulare Provider-Schicht (LLM, ComfyUI, TTS Stub) | `infrastructure/` | Erledigt |
| [`006_domain_personas_and_vision_analysis.md`](006_domain_personas_and_vision_analysis.md) | Spieler-Personas & Vision-Aussehensanalyse | `domain/personas` | Erledigt |
| [`007_domain_lorebooks_and_entries.md`](007_domain_lorebooks_and_entries.md) | Lorebooks & Lorebook-Einträge | `domain/lorebooks` | Erledigt |
| [`008_domain_worldinfo_locations_and_events.md`](008_domain_worldinfo_locations_and_events.md) | WorldInfo, Orte & Zufalls-Event-Mechanik | `domain/worldinfo` | Erledigt |
| [`009_domain_characters_and_emotional_sprites.md`](009_domain_characters_and_emotional_sprites.md) | KI-Charaktere, Emotionen & Galeriebilder | `domain/characters` | Erledigt |
| [`010_domain_translation_and_localization_layer.md`](010_domain_translation_and_localization_layer.md) | Übersetzungsschicht & Englischer Kanon | `domain/translation`, `infrastructure/` | Erledigt |
| [`011_domain_memories_and_tag_rag.md`](011_domain_memories_and_tag_rag.md) | Asynchrone Memories & Vektorloses RAG | `domain/memories` | Erledigt |
| [`012_domain_chat_sessions_messages_and_prompt_builder.md`](012_domain_chat_sessions_messages_and_prompt_builder.md) | ChatSessions, Beziehungsdynamik & 7-Stufen-Prompt | `domain/chat` | Erledigt |
| [`013_infrastructure_repositories.md`](013_infrastructure_repositories.md) | SQLAlchemy Repositories für alle Domänen | `infrastructure/repositories` | Erledigt |
| [`014_application_api_headless_core_rest_endpoints.md`](014_application_api_headless_core_rest_endpoints.md) | REST-API Endpunkte (SSE Stream, Chat, Entities) | `application/api/` | Erledigt |
| [`015_ui_theme_static_assets_and_base_template.md`](015_ui_theme_static_assets_and_base_template.md) | Modernes RPG-Theme CSS, Scripts & Base Template | `static/`, `templates/` | Erledigt |
| [`016_application_setup_and_auth_views.md`](016_application_setup_and_auth_views.md) | First-Boot Wizard & Login-Controller | `application/setup`, `application/auth` | Erledigt |
| [`017_application_overview_hub_dashboard.md`](017_application_overview_hub_dashboard.md) | Hub-Dashboard (3-Tab-Navigation & Persona-Modal) | `application/overview` | Erledigt |
| [`018_application_characters_designer.md`](018_application_characters_designer.md) | Character Designer (Info-Tab, Sparkle ✨, Sprites) | `application/characters` | Erledigt |
| [`019_application_lorebooks_and_worldinfo_views.md`](019_application_lorebooks_and_worldinfo_views.md) | Lorebook- & WorldInfo-Editoren (Places & Events) | `application/lorebooks`, `application/worldinfo` | Erledigt |
| [`020_application_chat_interface_and_interaction.md`](020_application_chat_interface_and_interaction.md) | Chat-Oberfläche, SSE-Streaming, Countdown & ComfyUI | `application/chat` | Erledigt |
| [`021_application_admin_panel_and_service_views.md`](021_application_admin_panel_and_service_views.md) | Admin-Dashboard, Benutzerverwaltung & Services | `application/admin` | Erledigt |
| [`022_application_factory_wsgi_and_podman_container.md`](022_application_factory_wsgi_and_podman_container.md) | App-Fabrik, WSGI-Entry & Podman Rootless Image | Root | Erledigt |
