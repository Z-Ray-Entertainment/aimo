# 🛡️ Administration & Einstellungen

[← Zurück zur Übersicht](README.md) | [← Das Chat-Interface](chat.md)

Das Admin-Panel ist Benutzern mit der Berechtigung `ADMIN_ACCESS` vorbehalten. Hier verwaltest du Benutzerkonten, funktionale Rechte und deine lokalen KI-Modelle.

---

## 👥 Benutzerverwaltung (`/admin/users`)

aimo verzichtet bewusst auf starre Rollenhierarchien und setzt auf ein **funktionales Berechtigungsmodell**:
- **Benutzer anlegen:** Erstelle neue Benutzerkonten mit Name, E-Mail und Initialpasswort.
- **Berechtigungs-Presets:**
  - `Admin`: Weist automatisch alle Rechte zu (Super User).
  - `Creator`: Erlaubt das Erstellen und Bearbeiten von Charakteren, Lorebooks, WorldInfos und Personas.
  - `User`: Grundlegender Zugriff für Chats und eigene Personas.
- **Granulare Checkboxen:** Jedes Recht (`character_create`, `chat_access`, `worldinfo_edit` etc.) kann auch einzeln vergeben oder entzogen werden.
- **Schutzregel für den initialen Admin:** Der beim First-Boot erstellte Administrator kann weder gelöscht noch können ihm Rechte entzogen werden.

---

## 🔌 Service- & Modell-Management (`/admin/services`)

### 1. Ollama-Modellverwaltung
- **Installierte Modelle:** Sieh auf einen Blick alle auf deinem Server vorhandenen Modelle.
- **Neues Modell installieren (Pull):** Gib den Modellnamen ein (z. B. `llama3:8b`, `qwen2.5:7b`), um es direkt über die Web-UI auf deinen Ollama-Server herunterzuladen.
- **Modell löschen:** Entferne nicht mehr benötigte Modelle per Klick, um Festplattenplatz freizugeben.

### 2. Task-spezifische Zuweisung
Weise unterschiedlichen Aufgaben spezialisierte Modelle zu:
- **Roleplay:** Dein bestes Modell für atmosphärische Dialoge und Charakterdarstellung.
- **Memory:** Ein schnelles Modell für 10-Nachrichten-Zusammenfassungen und Tag-Extraktion.
- **Assistant:** Modell für Werkzeugaufrufe, Übersetzung und Koordination.
- **Vision:** Multimodales Modell (z. B. `llava`, `llama3.2-vision`) für Bildbeschreibungen und Persona-Aussehen.

### 3. Inferenzparameter & System-Prompts
- Passe Hyperparameter feinfühlig an:
  - `num_ctx`: Kontextfenster-Größe (z. B. 4096, 8192).
  - `temperature`: Kreativität / Zufälligkeit (z. B. 0.7).
  - `top_p` und `repeat_penalty`.
- **System-Prompts editieren:** Passe die grundlegenden Direktiven für den Roleplay-Prompt, Memory-Prompt, ComfyUI-Diffuser-Prompt und den Sparkle-Assistenten ✨ direkt in Textareas an.
