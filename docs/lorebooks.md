# 📚 Lorebooks & Wissensbücher

[← Zurück zur Übersicht](README.md) | [← KI-Charaktere](characters.md) | [Welten, Orte & Events →](worldinfo.md)

**Lorebooks** dienen als thematische Enzyklopädien. Sie erlauben es, der KI umfangreiches Hintergrundwissen über Fraktionen, Magiesysteme, historische Ereignisse oder Technologie bereitzustellen — ohne das Kontextfenster mit unnötigen Daten zu überlasten.

---

## 🏗️ Aufbau eines Lorebooks

1. **Name des Lorebooks:** Z. B. *"Geschichte von Eldoria"*, *"Magie & Zaubersprüche"*.
2. **Kachel-Übersicht aller Einträge:**
   - **Erste Kachel:** Ein Platzhalter mit Plus-Symbol (`+`), um neue Einträge hinzuzufügen.
   - Alle weiteren Kacheln zeigen Titel, verknüpfte Tags und eine kurze Textvorschau.

---

## 📝 Einen Eintrag verfassen (Modaler Dialog)

Ein Klick auf eine Kachel öffnet das Overlay-Fenster für diesen Eintrag:
- **Titel:** Z. B. *"Der Orden der Schattenmagier"*.
- **Tags (Schlüsselwörter):** Kommagetrennte Liste von Schlagworten (z. B. `magie, orden, schatten, zauberer`).
- **Beschreibung / Fließtext:** Ausführliche Erklärung und Fakten.

---

## 🔍 Wie das Wissen in den Chat gelangt (Tag-RAG)

aimo nutzt ein **strikt regelbasiertes Tag-Matching**:
- Fallen im laufenden Chat Wörter, die mit den Tags eines Lorebook-Eintrags übereinstimmen (`tags_overlap >= 1`), wird dieser Eintrag automatisch in den Kontext für die nächste KI-Antwort geladen.
- Wird das Thema nicht erwähnt, bleibt der Eintrag inaktiv. So bleibt das Gedächtnis der KI schlank und präzise.

Weiter zu: [**Welten, Orte & Ereignisse (WorldInfo) →**](worldinfo.md)
