# Task 006: Spieler-Personas & Vision-Aussehensanalyse

## 🎯 Ziel & Umfang
Verwaltung von Spieler-Personas (Identität des Spielers im Rollenspiel) inklusive automatischer Aussehens-Extraktion via Vision-Modell und Lösch-Schutz für Personas, die in aktiven Chats verwendet werden.

## 📂 Betroffene Schicht & Dateien
- **Schicht:** `domain/personas/`
- **Dateien:**
  - `domain/personas/models.py`
  - `domain/personas/services.py`
  - `domain/personas/exceptions.py`

## 🔗 Abhängigkeiten
- `tasks/001_foundation_config_and_shared_utils.md`
- `tasks/005_infrastructure_provider_interfaces_and_adapters.md`

## 📝 Fachliche Vorgaben & Spezifikation

### 1. `domain/personas/models.py`
- **`Gender` (Enum):**
  - `MALE = "male"`
  - `FEMALE = "female"`
  - `NON_BINARY = "non-binary"`
- **`UserPersona` (Entity):**
  - `id: int | None`
  - `user_id: int`
  - `name: str`
  - `gender: Gender`
  - `portrait_path: str` (visuelles Referenzbild)
  - `description: str` (Hintergrund, Persönlichkeit des Nutzers)
  - `appearance: str` (textuelle Beschreibung physischer Merkmale)
  - `is_default: bool = False` (Standard-Persona für Dashboard-Button)
  - `created_at: datetime`

### 2. `domain/personas/services.py`
- **`PersonaService`:**
  - `create_persona(user_id: int, name: str, gender: Gender, portrait_path: str, description: str, appearance: str = "", is_default: bool = False) -> UserPersona`
  - `update_persona(persona: UserPersona, name: str, gender: Gender, portrait_path: str, description: str, appearance: str) -> UserPersona`
  - `analyze_appearance(persona: UserPersona, vision_provider: LLMProvider, vision_model: str, prompt: str) -> str`:
    - Ruft `vision_provider.analyze_image()` mit dem Porträtbild auf.
    - **Fokus-Regel:** Extrahiert Gesichtsmerkmale, Haare, Teint, Statur. Bildhintergründe oder situative Körperposen werden ignoriert.
    - Aktualisiert `persona.appearance`.
  - `delete_persona(persona: UserPersona, has_active_chats: bool) -> None`:
    - **Lösch-Sperre:** Wenn `has_active_chats == True`, wird `PersonaInUseError` geworfen.
  - `set_default_persona(user_id: int, persona_id: int) -> None`

### 3. `domain/personas/exceptions.py`
- `PersonaNotFoundError`, `InvalidPersonaDataError`, `PersonaInUseError`.

## ✅ Akzeptanzkriterien
- [ ] Vollständige Domänenlogik für Personas mit `Gender`-Enum.
- [ ] Automatisierte Vision-Analyse befüllt das Aussehen ohne Hintergrund/Posen.
- [ ] Lösch-Schutz greift verlässlich, wenn die Persona in Chats verwendet wurde.
- [ ] Manuell editierte Aussehensbeschreibungen bleiben geschützt.
