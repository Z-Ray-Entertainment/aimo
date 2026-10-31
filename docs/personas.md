# 👤 Spieler-Personas

[← Zurück zur Übersicht](README.md) | [← Das Hub-Dashboard](hub.md) | [KI-Charaktere & Designer →](characters.md)

Eine **Spieler-Persona** repräsentiert deine eigene Identität im Rollenspiel. Du kannst mehrere unterschiedliche Personas (z. B. Magier, Ritterin, Detektiv) anlegen und vor Chat-Beginn auswählen, in welcher Rolle du agieren möchtest.

---

## 🎨 Eigenschaften einer Persona

- **Name:** Dein Name im Rollenspiel, mit dem dich KI-Charaktere ansprechen.
- **Geschlecht:** Zur konsistenten grammatikalischen Anrede im Prompt (`männlich`, `weiblich`, `nicht-binär`).
- **Porträtbild:** Bilddatei (PNG, JPG, WEBP), die als visueller Avatar im Chat und als Referenzbild für [Bildgenerierungen](chat.md#bildgenerierung) dient.
- **Beschreibung:** Textfeld für die Hintergrundgeschichte, Motive, Verhaltensweisen und Eigenheiten deiner Figur.
- **Aussehen (KI-Vision-Extraktion):** Detaillierte Beschreibung physischer Merkmale.

---

## 👁️ Automatische Vision-Analyse des Aussehens

Sobald du ein Porträtbild für deine Persona hochlädst und speicherst:
1. **KI-Scan:** Ein Vision-Modell (über Ollama) analysiert das Gesicht und die sichtbaren physischen Merkmale (Haarfarbe, Augenfarbe, Teint, Statur).
2. **Fokus-Regel:** Hintergründe, Räume oder situative Posen werden bewusst ignoriert.
3. **Automatischer Eintrag:** Das Textfeld *"Aussehen"* wird automatisch mit diesen Merkmalen befüllt.
4. **Volle Kontrolle:** Du kannst das Feld *"Aussehen"* jederzeit manuell anpassen oder ergänzen. Erst wenn du das Porträt austauschst, stößt das System einen erneuten Scan an.

---

## 🛡️ Schutzregel: Lösch-Sperre aktiver Personas

Um die narrative Konsistenz bestehender Gesprächsverläufe zu schützen, gilt:
- **Personas, die bereits in mindestens einem Chat verwendet wurden, können nicht gelöscht werden.**
- Der Lösch-Button ist in diesem Fall ausgegraut und mit einem Hinweistext versehen.

Weiter zu: [**KI-Charaktere & Designer →**](characters.md)
