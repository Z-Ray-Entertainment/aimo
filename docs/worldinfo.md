# 🌍 Welten, Orte & Ereignisse (WorldInfo)

[← Zurück zur Übersicht](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/README.md) | [← Lorebooks](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/lorebooks.md) | [Das Chat-Interface →](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/chat.md)

Eine **WorldInfo** fasst die Geografie, Szenerien und zufälligen Ereignisse einer Spielwelt zusammen. Sie bestimmt die visuellen 16:9-Hintergründe im Chat und ermöglicht überraschende Zufallsbegegnungen.

---

## 🏛️ WorldInfo-Editor (`templates/worldinfo/detail.html`)

- **Name der Welt:** Bezeichnung des Settings (z. B. *"Königreich Acheron"*).
- **WorldInfo-Icon (`icon`):** Ein prägnantes Symbol oder Bild, das im Header und in der Chat-Sidebar angezeigt wird.

Der Editor teilt sich in zwei funktionale Reiter:

---

## 📍 Tab 1: Places (Orte)

Eine Galerie aller Schauplätze dieser Welt:
- Erste Kachel (`+`) zum Anlegen eines neuen Ortes.
- **Orts-Overlay (Modal):**
  - **Name:** Z. B. *"Die Taverne zum Trunkenen Troll"*, *"Vergessener Wald"*.
  - **Tags:** Schlagwörter zur Umgebungsidentifikation.
  - **Beschreibung:** Atmosphärische Beschreibung der Umgebung, Gerüche, Lichtverhältnisse und Stimmung.
  - **16:9-Hintergrundbild:** Bildupload im Querformat (PNG, JPG, WEBP). Dieses Bild dient im Chat als stimmungsvoller Hintergrund und wird an ComfyUI für konsistente Bildgenerierungen übergeben.
  - **Vision-ALT-Tag & Interaktive Text-Erweiterung:** Beim Bildupload generiert ein Vision-Modell automatisch eine Bildbeschreibung. Das System fragt dich anschließend interaktiv: *"Möchtest du die Ortsbeschreibung um diese KI-Bildbeschreibung erweitern?"*.
  - **Event-Zuordnung:** Liste aller Ereignisse, die speziell an diesem Ort auftreten können.

---

## ⚡ Tab 2: Events (Zufallsereignisse)

Events hauchen der Welt unvorhersehbares Leben ein (z. B. ein plötzlicher Sturm, ein Straßenräuber, ein Festzug).
- Erste Kachel (`+`) zum Erstellen eines neuen Events.
- **Event-Kacheln:** Zeigen Titel, Wahrscheinlichkeit (`0 - 100%`), One-Shot-Status und ein klares **Zugehörigkeits-Badge** (verknüpfter Ort oder *"Gesamte Welt"*).
- **Event-Overlay (Modal):**
  - **Titel:** Z. B. *"Plötzlicher Platzregen"*.
  - **Zugehörigkeit:** Wähle aus, ob das Event überall auf der Welt auftreten kann (*"Gesamte Welt"*) oder nur an einem spezifischen Ort.
  - **Wahrscheinlichkeit (0–100%):** Relative Chance bei der Auslosung.
  - **One-Shot:** Wenn aktiviert, feuert das Ereignis in einer Chat-Sitzung genau ein einziges Mal.
  - **Szenische Beschreibung:** Der Fließtext, der bei Triggerung in den Prompt injiziert wird, damit die KI atmosphärisch darauf reagiert.

---

## 🔄 Die Cooldown- & Trigger-Mechanik im Chat

- **Einheitlicher Pool:** Welt-Events und Orts-Events des aktuellen Chat-Orts bilden einen gemeinsamen Ziehungspool.
- **Nachrichten-Zähler (10–100):** Zu Chat-Beginn wird eine Zahl zwischen 10 und 100 gewürfelt. Jede gesendete Nachricht (Spieler oder KI) zählt den Wert um 1 herunter.
- **Ziehung bei 0:** Sobald der Zähler 0 erreicht, wird genau ein Event gewichtet ausgelöst. Danach wird sofort eine neue Zahl zwischen 10 und 100 gewürfelt.
- **Opt-Out:** In der Chat-Sidebar kannst du Events jederzeit über eine Checkbox deaktivieren, wenn du eine ruhige Szene bevorzugst.

Weiter zu: [**Das Chat- & Rollenspiel-Interface →**](file:///opt/datalake/vortex/vortex_acherontic_projects/aimo/docs/chat.md)
