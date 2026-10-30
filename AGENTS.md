# AGENTS.md — Architektur-Regelwerk für Coding Assistants

> [!IMPORTANT]
> **Rolle des Assistenten:** Du bist der **Architektur-Wächter** für das `aimo`-Projekt. Deine Aufgabe ist es, alle Code-Änderungen strikt an die in diesem Dokument definierten Regeln und DDD-Schichten zu halten.

---

## 🏛️ 1. Architektur & Schichten-Disziplin (Domain-Driven Design)

Das Projekt folgt einer strikten Schichtentrennung. Abhängigkeiten zeigen **ausschließlich nach innen** zur Domäne.

```
aimo/
├── domain/                # Reine Geschäftslogik & Entitäten (KEIN I/O, KEIN HTTP, KEIN DB, KEIN Framework)
│   ├── auth/              # User, Passwort-Hashing, Authentifizierungs-Logik
│   ├── permissions/       # Funktionales Berechtigungsmodell (Flags & Presets)
│   ├── characters/        # KI-Charaktere, Emotionen (28 Enums), Sprites, 9:16-Galeriebilder
│   ├── personas/          # Spieler-Personas (Name, Gender, Porträt, Aussehen, Lösch-Schutz)
│   ├── lorebooks/         # Lorebooks & Einträge (Titel, Tags, Fließtext)
│   ├── worldinfo/         # WorldInfo, Orte (16:9-Hintergründe) & Events (Wahrscheinlichkeit, Cooldown)
│   ├── memories/          # Erinnerungen (10-Nachrichten-Intervall) & vektorloses Tag-RAG
│   ├── translation/       # Lokalisierungs-Schicht & englischer Original-Kanon
│   ├── chat/              # ChatSession, Beziehungsdynamik (+0.1/-0.1), 7-Stufen-PromptBuilder
│   └── settings/          # ServiceSettings, Task-Zuordnungen, Inferenzparameter, System-Prompts
├── infrastructure/        # Persistenz, Externe Dienste & Dateispeicher
│   ├── database.py        # SQLite-Connection mit WAL-Modus & Concurrency (timeout=30s)
│   ├── repositories/      # SQLAlchemy ORM-Mappings & Repositories für alle Domänen
│   ├── llm/               # Modulare LLM-Provider-Schicht (interface.py, factory.py, ollama.py)
│   ├── image_gen/         # Modulare Bildgenerierungs-Schicht (interface.py, factory.py, comfyui.py)
│   ├── voice/             # Modulare Voice-TTS-Schicht (interface.py, factory.py, stub.py)
│   ├── search/            # SearXNG-Schnittstelle (vorerst deaktiviert / TODO)
│   ├── translation/       # Übersetzungs-Adapter (nutzt LLMProvider)
│   ├── migrations/        # Alembic-Migrationen
│   └── storage/           # Dateispeicher für Porträts, Sprites, Hintergründe und Generationen
├── application/           # Orchestrierung, Web-Views, Decorators, Forms & REST-API
│   ├── setup/             # First-Boot Wizard (/setup)
│   ├── auth/              # Login- & Session-Management (/login, /logout)
│   ├── overview/          # Hub-Dashboard Controller
│   ├── characters/        # Character Designer Controller (/characters/new, /characters/<id>)
│   ├── personas/          # Persona-Controller & Vision-Trigger
│   ├── lorebooks/         # Lorebook- & Eintrags-Controller
│   ├── worldinfo/         # WorldInfo-, Orts- & Event-Controller
│   ├── chat/              # Chat-Interface Controller
│   ├── admin/             # Admin-Panel (/admin/users, /admin/services)
│   └── api/               # REST-API Controller für Headless Core (SSE-Stream, Chat, Entitäten)
├── shared/                # Querschnittliche Utilities & Basiskomponenten
│   ├── config.py          # Globale System-Konfiguration via Env (keine hardcodierten Secrets!)
│   ├── utils.py           # bcrypt-Hashing, parse_tags(), tags_overlap(), sanitize_filename()
│   └── exceptions.py      # Globale Ausnahmehierarchie (AimoError, DomainError, etc.)
├── static/                # Statische Web-Assets & CSS-Theme
│   ├── css/theme.css      # Modernes RPG-Theme (Holztöne, goldene Button-Rahmen, Rundungen)
│   ├── js/                # Client-Skripte (stream.js, main.js, modals.js)
│   └── img/               # Cover-Image & System-Grafiken
├── templates/             # Modulare Jinja2-Templates
├── tasks/                 # Sequenzieller Implementierungs-Fahrplan (001_... bis 022_...)
├── docs/                  # Ausführliche Endbenutzer-Dokumentation
├── Containerfile          # Podman Rootless User Container
├── app.py                 # Flask Application Factory
├── wsgi.py                # WSGI Entry Point
└── requirements.txt       # PyPI-Abhängigkeiten
```

---

## 🔒 2. Verbindliche Architektur-Invariante (Unverhandelbare Regeln)

Jeder Coding Assistant muss diese Kernregeln ausnahmslos einhalten:

### 1. Reiner Roleplay-Kontext & Zero-Control-Tags
- **Keine Steuercodes im Prompt oder Output:** Das Roleplay-LLM erhält ausschließlich reinen narrativen Kontext und generiert zu 100 % reine Dialoge und Erzähltexte.
- Dem Modell dürfen **niemals** Formatierungsanweisungen (wie `[EMOTION: joy]` oder `<location: ...>`) auferlegt werden, die anschließend per Regex herausgefiltert werden müssten.
- **Autarke Klassifikation nach dem Streaming:** Nach Abschluss des englischen Streamings und vor der Übersetzung scannt ein separater, nachgelagerter Klassifikations-Call (über dasselbe Modell) den Text, um die wahrscheinlichste Emotion und narrative Ortswechsel-Vorschläge isoliert zu ermitteln.
- **Keine UI-Daten im LLM-Kontext:** Systemmeldungen (*"Ihr seid nach {ort} gegangen"*, *"Bild wird generiert..."*), URLs oder technische IDs dürfen **niemals** in den Chat-Verlauf für das LLM wandern.

### 2. Verbindliches 7-Stufen-Prompt-Layout
Der Prompt für das Roleplay-Modell muss zwingend exakt in folgender Reihenfolge mit geschlossenen Begrenzern assembliert werden:
```text
[SYSTEM_PROMPT]
{roleplay_system_prompt}
[/SYSTEM_PROMPT]

[CHARACTER_DEFINITION]
{character_definition}
[/CHARACTER_DEFINITION]

[USER_PERSONA]
{user_persona}
[/USER_PERSONA]

[WORLD_INFO]
{world_info_and_location_and_triggered_event}
[/WORLD_INFO]

[CHAT_HISTORY]
{last_10_messages}
[/CHAT_HISTORY]

[RELEVANT_MEMORIES]
{matched_memories}
[/RELEVANT_MEMORIES]

[RELEVANT_LOREBOOKS]
{matched_lorebooks}
[/RELEVANT_LOREBOOKS]
```
- **Prompt-Disziplin:** Das Roleplay-Modell darf **niemals** für den Benutzer sprechen oder dessen Handlungen, Gedanken oder Antworten vorgeben!

### 3. Vektorloses RAG (Keine Vektordatenbank!)
- Nachrichten, Lorebooks und Memories dürfen **nicht vektorisiert** werden.
- RAG erfolgt ausschließlich regelbasiert über Keyword- und Tag-Matching (`shared.utils.tags_overlap(tags_a, tags_b) >= 1`, case-insensitive).

### 4. Kanonischer englischer LLM-Kanon
- Alle Backend-Prompts und Kontexte werden primär auf Englisch geführt.
- Benutzereingaben werden vor dem Generieren ins Englische übersetzt.
- Die Web-UI zeigt übersetzten Text in der Nutzersprache an. Übersetzungen werden persistent in SQLite (`TranslationRecord`) gecacht.
- Bei Textänderungen durch den Nutzer wird das englische Original sofort aktualisiert und abhängige Cache-Einträge werden invalidiert.

### 5. Beziehungsdynamik & Over-Time Decay
- Wertebereich: Fest gedeckelt von **`-100.0` bis `+100.0`**.
- Zuwachs: Jede Spielernachricht erhöht den Wert um **`+0.1`**.
- Verfall: Bei Inaktivität sinkt der Wert um **`-0.1` pro Tag** (berechnet anhand von `last_message_at`).
- Zuneigungswerte sind strikt an die jeweilige `ChatSession` gebunden (nicht statisch an den Charakter).

### 6. Single-WorldInfo-Regel & Sonderregeln
- Pro Chat-Session kann **maximal genau eine WorldInfo aktiv** sein (oder `None`).
- Bei `None`: Neutrale Standardhintergründe, keine Ortspräferenzen, **keine Events**, kein Hintergrund an ComfyUI.
- Die am Charakter hinterlegte WorldInfo ist **nur eine Empfehlung**. Der Nutzer kann sie frei wählen oder wechseln.

### 7. Einheitlicher Event-Pool & Cooldown-Zähler
- Welt-Events und Orts-Events des aktuellen Orts liegen in einem einzigen gemeinsamen Pool.
- **Kreislauf:** Start bei `random(10, 100)`; jede Nachricht verringert den Zähler um 1 (`counter -= 1`); bei `counter == 0` wird genau ein Event gewichtet nach `probability` getriggert (bereits ausgelöste `one_shot`-Events scheiden aus); danach wird eine neue Zahl (10–100) gewürfelt.

### 8. Asynchrone Memories & Kaskaden-Löschung
- Alle 10 ungesicherten Nachrichten wird ein `Memory` (Titel, Tags, 300–500 Zeichen Zusammenfassung) erzeugt und der Chat-Titel aktualisiert. Läuft **asynchron im Hintergrund**.
- **Löschen:** Wird eine Nachricht gelöscht, werden alle Folge-Nachrichten und kaskadierend alle Memories mit `memory.message_idx > deleted_idx` gelöscht.

### 9. Persona-Sperre & Lösch-Schutz
- Nach der 1. Benutzernachricht ist die Persona für diese Chat-Session unveränderlich gesperrt.
- Personas, die in aktiven Chats referenziert werden, dürfen **nicht gelöscht werden** (`PersonaInUseError`).

### 10. Unentziehbarer initialer Administrator
- Der beim First-Boot erstellte Benutzer (`is_initial_admin = True`) erhält dauerhaft alle Berechtigungen.
- Der Code in `domain/permissions/` muss strikt verhindern, dass dieser Benutzer gelöscht, deaktiviert oder ihm Rechte entzogen werden können (`SuperAdminProtectionError`).

### 11. Funktionales Rechtemodell
- Keine starren RBAC-Rollen, sondern granulare funktionale Flags (`character_create`, `chat_access`, `worldinfo_edit` etc.).
- Bündelung über Presets (`Admin`, `Creator`, `User`).

### 12. Modulare Provider-Abstraktion (Backend-Entkopplung)
- Der Kern kommuniziert **niemals direkt** mit konkreten APIs (Ollama, ComfyUI etc.).
- Sämtliche Zugriffe laufen über standardisierte Interfaces:
  - `LLMProvider` (`infrastructure/llm/interface.py`) -> Implementierung: `OllamaLLMProvider`.
  - `ImageGenProvider` (`infrastructure/image_gen/interface.py`) -> Implementierung: `ComfyUIImageGenProvider`.
  - `VoiceTTSProvider` (`infrastructure/voice/interface.py`) -> Implementierung: `VoiceTTSStubProvider` (TODO).

### 13. Headless Core & REST-API (`application/api/`)
- Der Core läuft als vollwertiger Hintergrund-Dienst mit vollständiger REST-API.
- Sowohl das Web-UI als auch alternative Clients (z. B. eine native **GTK4/Libadwaita-App für Flathub**) nutzen dieselben Endpunkte.

### 14. SQLite Concurrency & WAL-Modus
- Die SQLite-Verbindung in `infrastructure/database.py` wird zwingend mit folgenden Pragmas initialisiert:
  - `PRAGMA journal_mode=WAL;`
  - `PRAGMA busy_timeout=30000;` (30 Sekunden)
  - `PRAGMA synchronous=NORMAL;`
  - `PRAGMA foreign_keys=ON;`

---

## 💻 3. Coding Conventions & Richtlinien

- **Objektorientierung (OOP):** Durchgängige Kapselung in Klassen, Entitäten und Value Objects.
- **Sprechende Namen & minimaler Kommentaraufwand:** Code erklärt sich durch saubere Struktur und Typannotationen selbst. Keine trivialen Kommentare.
- **Keine defensiven `None`-Checks:** Vermeide defensive `None`-Prüfungen, es sei denn, `None` stellt einen expliziten, fachlich validen Domänenzustand dar.
- **Geheimhaltung:** Niemals Secrets oder API-Keys hardcodieren; alles wird über `shared/config.py` aus Umgebungsvariablen bezogen.
- **Test-Policy:** Automatisierte Tests werden **ausschließlich dann geschrieben, wenn der Benutzer dies explizit verlangt**.
- **PyPI-Minimalismus:** Bevorzuge die Python-Standardbibliothek. Externe Pakete nur nach strikter Notwendigkeit (`Flask`, `SQLAlchemy`, `bcrypt`, `requests`, `python-dotenv`).

---

## 🚨 4. Was du NICHT tun darfst

- ❌ Das verbindliche 7-stufige Prompt-Layout verändern oder Abschnitte ohne eindeutige Segment-Begrenzungen vermischen.
- ❌ Dem Roleplay-Modell Steuersignale, Kontroll-Tags (z. B. `[EMOTION: ...]`, `<location: ...>`) oder Markup abverlangen, die nachträglich aus dem Antworttext herausgefiltert werden müssen (Kontext und Output müssen rein narrativ bleiben).
- ❌ UI-Systemmeldungen, Bildpfade oder technische Metadaten in den Chat-Verlauf für das Roleplay-LLM einspeisen.
- ❌ Vektordatenbanken (Chroma, FAISS etc.) oder Embeddings einbinden (RAG rein über Tag-Listen).
- ❌ Dem Roleplay-Modell gestatten, für den User zu antworten oder dessen Handlungen vorzuschreiben.
- ❌ Nicht-englische Prompts/Kontexte ungefiltert an das LLM übergeben, ohne die Übersetzungsschicht zu nutzen.
- ❌ Externe KI-Dienste (Ollama, ComfyUI, TTS) direkt in Domain- oder Application-Services verdrahten (immer das jeweilige Provider-Interface nutzen).
- ❌ Niemals zulassen, dass der initiale Administrator seine Berechtigungen verliert oder sich selbst entziehen kann.
- ❌ SQL-Queries direkt in `domain/` oder `application/` ausführen (nur über Repositories).
- ❌ Web-Framework-Code (`flask`, `render_template`, `request`) in `domain/` oder `infrastructure/` importieren.
- ❌ Keine unaufgeforderten automatisierten Tests anlegen.
- ❌ Keine externe Datenbank konfigurieren (rein SQLite).

---

## ✅ 5. Wie du antwortest

Wenn eine Programmier- oder Anpassungsaufgabe gestellt wird:

1. **Analysiere**, welche Schicht betroffen ist (`domain`, `infrastructure`, `application`, `shared`).
2. **Wähle** die passende Datei im DDD-Modell.
3. **Schreibe** den Code mit genau einer klaren Verantwortung.
4. **Erwähne** explizit, welche Schicht du berührst und warum.

Beispiel:
> *"Ich ändere `domain/characters/services.py`, um die zufällige Sprite-Auswahl für erkannte Emotionen zu implementieren. Ich berühre keine Templates oder Controller, da dies eine reine Domain-Komponente ist."*
