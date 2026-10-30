# ⚙️ Ersteinrichtung & First-Boot

[← Zurück zur Übersicht](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/README.md)

Beim allerersten Start von **aimo** (wenn noch keine SQLite-Datenbank bzw. keine Benutzer existieren) wird automatisch der **First-Boot-Setup-Wizard** aufgerufen.

---

## 🧙‍♂️ Der First-Boot-Wizard (`/setup`)

Bevor das System für reguläre Nutzer freigegeben wird, muss genau ein initialer Administrator angelegt und die Verbindung zu deinem lokalen KI-Server konfiguriert werden.

### 1. Initialer Administrator (Super User)
- **Benutzername:** Dein gewünschter Anzeigename.
- **E-Mail-Adresse:** Dient zusammen mit dem Passwort zur späteren Anmeldung.
- **Passwort:** Ein sicheres Kennwort (wird per `bcrypt` gehasht).
- **Besonderheit:** Dieser erste Benutzer erhält automatisch sämtliche im System verfügbaren Berechtigungen. Diese Rechte sind dauerhaft geschützt und können weder entzogen noch deaktiviert werden.

### 2. Service-Verbindungen
- **Ollama-URL (Pflicht):**  
  Die Netzwerkadresse deines Ollama-Servers (Standard: `http://localhost:11434`). Ollama wird zwingend für die Textgenerierung, Rollenspiele und Bild-Vision-Analysen benötigt.
- **SearXNG-URL (Optional):**  
  Adresse für Websuchen per Tool-Calling (standardmäßig deaktiviert / TODO).
- **ComfyUI-URL (Optional):**  
  Adresse deines ComfyUI-Servers (Standard: `http://localhost:8188`) für generative Bildworkflows im Chat. Kann auch später im [Admin-Bereich](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/admin.md) nachgetragen werden.

---

## 🔒 Nach dem Setup: Geschlossenes System

Sobald der Setup-Wizard einmalig erfolgreich abgeschlossen wurde:
1. **Dauerhafte Sperre:** Der Pfad `/setup` wird sofort unzugänglich gemacht.
2. **Keine Selbstregistrierung:** Es gibt keinen öffentlichen Registrierungslink. Neue Konten können ausschließlich durch einen Administrator im [Admin-Panel](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/admin.md) erstellt werden.
3. **Regulärer Login:** Alle Benutzer melden sich fortan über die Einstiegsmaske (`/login`) mit E-Mail und Passwort an.

Weiter zu: [**Das Hub-Dashboard →**](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/hub.md)
