# 🎭 KI-Charaktere & Character Designer

[← Zurück zur Übersicht](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/README.md) | [← Spieler-Personas](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/personas.md) | [Lorebooks & Wissensbücher →](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/lorebooks.md)

Der **Character Designer** erlaubt Autoren das detaillierte Erschaffen interaktiver KI-Charaktere mit emotionalen Sprites, freischaltbaren Galeriebildern und dynamischen Ortspräferenzen.

---

## 🛠️ Kopfzeile & Aktionen

- **Zurück-Button (`←`):** Kehrt zur Hauptübersicht zurück.
- **Sichtbarkeit:**
  - `Privat` (Standard): Nur du kannst diesen Charakter sehen und bespielen.
  - `Öffentlich`: Alle Benutzer des Systems können mit dem Charakter interagieren.
- **Speichern / Kopieren / Löschen:** Schnelle Aktionsbuttons mit feinem Goldrand im oberen Header.

---

## 📝 Tab 1: Hauptinformationen

- **Name:** Name der Spielfigur.
- **Geschlecht:** `male`, `female` oder `non-binary`.
- **Primary Portrait (Pflicht):** Das primäre Porträtbild für Kacheln und Standard-Chatanzeige.
- **Beschreibung & KI-Sparkle ✨:**
  - Beschreibe das Wesen, Sprechweise und Verhaltensmuster.
  - **KI-Schreibassistent:** Klick auf den Zauberstab mit Sparkles ✨ optimiert deine Vorlage über einen spezialisierten Autoren-Prompt automatisch zu einer fesselnden Beschreibung.
- **Gesprächsbeispiele:** Typische Dialoge zur Kalibrierung von Tonalität und Wortwahl.
- **First Message (Welcome Message):** Die Eröffnungsnachricht des Charakters, die beim Anlegen eines neuen Chats automatisch erscheint.
- **Empfohlene WorldInfo & Ortspräferenzen:**
  - Wähle eine [WorldInfo](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/worldinfo.md) als Empfehlung.
  - Definiere **bevorzugte Orte** (an denen sich der Charakter gerne aufhält) und **gemiedene Orte** (die er ungern besucht).
- **Freischaltbare 9:16-Galeriebilder:**
  - Lade Bilder im Smartphone-/Hochformat (9:16) hoch.
  - Für jedes Bild kannst du einen **Beziehungsschwellenwert** von `-100 bis +100` festlegen. Sobald dein Beziehungsstand im Chat diesen Wert erreicht, wird das Bild im Reiter *"Medien"* freigeschaltet!

---

## 🎭 Tab 2: Emotionale Sprites

aimo unterstützt dynamische, transparente Sprites (Format PNG oder WEBP), die im Chat passend zur jeweiligen Stimmung der KI eingeblendet werden.

### Die 28 unterstützten Emotionen
`admire`, `amused`, `anger`, `annoyed`, `approval`, `caring`, `confused`, `curious`, `desire`, `disappointed`, `disapproval`, `disgust`, `embarrassed`, `excited`, `fear`, `gratitude`, `grief`, `joy`, `love`, `nervousness`, `neutral` (Default & Fallback), `optimistic`, `pride`, `realize`, `relief`, `remorse`, `sad`, `surprise`.

### Varianten & Stackview
- **Mehrere Varianten pro Emotion:** Du kannst mehrere Sprites für dieselbe Emotion hinterlegen (z. B. `joy_1.png`, `joy_2.webp`).
- **Papier-Plus-Button (📄➕):** Erscheint, sobald mindestens ein Sprite vorliegt, um weitere Varianten hinzuzufügen.
- **Stackview & Augen-Button (👁️):** Bei mehreren Bildern deutet ein Stapel-Effekt die Vielfalt an. Ein Klick auf das Auge öffnet ein modales Popup, in dem du alle Varianten betrachten und einzeln löschen kannst.
- **Zufallsauswahl zur Laufzeit:** Wenn die KI eine Emotion zeigt, wählt das System automatisch zufällig eine der vorhandenen Varianten aus.

Weiter zu: [**Lorebooks & Wissensbücher →**](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/lorebooks.md)
