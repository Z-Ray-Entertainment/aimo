# 💬 Das Chat- & Rollenspiel-Interface

[← Zurück zur Übersicht](README.md) | [← Welten & Orte](worldinfo.md) | [Administration & Einstellungen →](admin.md)

Das Chatfenster ist das Herzstück von aimo. Hier entfaltet sich das interaktive Textadventure mit Live-Streaming, emotionalen Sprites, dynamischen Ortswechseln und generativen Bildern.

---

## 🚀 Chat-Start ("First Chat")

Wenn du einen Charakter zum ersten Mal anklickst:
1. **Persona-Wahl:** Besitzt du mehr als eine Persona, fragt dich ein kurzer Dialog, wer du sein möchtest. (Nach der ersten Benutzernachricht ist deine Persona für diese Sitzung unveränderlich fixiert).
2. **WorldInfo-Wahl:** Wähle die Spielwelt aus (die Empfehlung des Charakters ist vorausgewählt). Du kannst auch explizit *"Ohne WorldInfo"* spielen (dann gelten neutrale Hintergründe und keine Events).
3. **Welcome Message:** Der Charakter begrüßt dich sofort mit seiner definierten Eröffnungsnachricht am passenden Anfangsort.

---

## 🖥️ Bildschirmaufbau

- **Header:** Zurück-Button (`←`) zur Übersicht.
- **Linke Seitenleiste (Multi-Chat):** Zeigt alle deine Chat-Sessions und Forks mit diesem Charakter. Die Titel aktualisieren sich dynamisch anhand wichtiger Geschehnisse.
- **Zentraler Drei-Reiter-Container:**
  - **Tab 1: Chat:** Der fortlaufende Dialog in Sprechblasen (KI links mit Porträt/Sprite, Spieler rechts).
  - **Tab 2: Medien:** Bündelt alle freigeschalteten 9:16-Galeriebilder, hochgeladenen Fotos und generierten Bilder.
  - **Tab 3: Erinnerungen:** Zeigt alle vom System generierten Memories (Zusammenfassungen) und erlaubt manuelle Korrekturen.
- **Rechte Info-Box:**
  - Charakterporträt / transparenter Emotions-Sprite.
  - Dynamischer Beziehungsbalken (-100 bis +100 mit Herz-Icon).
  - Aktuelle WorldInfo mit Wechsel-Stift.
  - Spieler-Persona.
  - Aktionen: Events an/aus (Checkbox), Neuer Chat, Chat löschen.

---

## ⚡ Live-Streaming & Nahtlose Lokalisierung

Da moderne KI-Modelle auf Englisch am nuanciertesten schreiben, das UI aber auf Deutsch operiert, nutzt aimo einen zweistufigen Ablauf:
1. **Live-Stream (Englisch):** Nach Absenden erscheint *"Denkt nach..."*. Der englische Rohstream läuft live in die Chatbubble ein — jedoch **ausgegraut und in kleinerer Schrift**, damit du den Fortschritt siehst.
2. **Übersetzungs-Swap:** Sobald der Text komplett ist, erscheint kurz ein Spinner und der ausgegraute Text wird nahtlos durch die **fertige deutsche Übersetzung** in normaler Schriftgröße ersetzt.

---

## 🧭 Interaktiver Ortswechsel (Textadventure)

Wenn die Erzählung der KI einen Ortswechsel vorschlägt (z. B. *"Lass uns in den Wald aufbrechen"*):
- Ein Button blendet sich im Chat ein: *"Möchtest du zu [Neuer Ort] wechseln? [Ja] [Nein]"*.
- **60-Sekunden-Countdown:** Ein kleiner roter Balken am unteren Rand des Buttons schrumpft 60 Sekunden lang zusammen. Reagierst du nicht, verschwindet die Abfrage rückstandslos.
- **Bei "Ja":** Der Ort schaltet um, das 16:9-Hintergrundbild wechselt und im Chat erscheint eine dezente zentrierte Systemmeldung: *"Ihr seid nach {ort} gegangen"*.

---

## 🎨 Multimodale Features & Eingabeleiste

- **Klammer-Symbol (Bild hochladen):** Hänge ein beliebiges Bild an deine Nachricht an. Ein Vision-Modell erzeugt im Hintergrund einen präzisen ALT-Text, der der KI situativ erklärt, was du zeigst.
- **Zauberstab mit Sparkles ✨ (ComfyUI Bildgenerierung):**
  - Generiert auf Basis der aktuellen Szene ein Bild per ComfyUI.
  - Während der Generierung erscheint *"Bild wird generiert..."* und das Texteingabefeld ist gesperrt.
  - Über den angezeigten **Abbrechen-Button** kannst du den Vorgang jederzeit stoppen.
  - Das fertige Bild erscheint im Chat und im Reiter *"Medien"*.

---

## 💔 Beziehungsdynamik & Memories

- **Beziehungswert:** Jede deiner Nachrichten erhöht den Wert um `+0.1`. Bei längerer Inaktivität sinkt der Wert um `-0.1` pro Tag (maximal von -100 bis +100).
- **Freischaltbare Bilder:** Erreicht der Wert den Schwellenwert eines hinterlegten 9:16-Bildes, wird es im Reiter *"Medien"* freigeschaltet.
- **Memories (alle 10 Nachrichten):** Alle 10 Nachrichten fasst ein Hintergrund-Modell das Geschehen zusammen und aktualisiert den Chat-Titel in der linken Seitenleiste.
- **Drei-Punkte-Menü (`...`):**
  - **Nachricht löschen:** Löscht die Nachricht sowie alle folgenden Beiträge und kaskadierend alle zugehörigen Memories.
  - **Chat forken:** Erstellt eine Kopie des Chats ab genau diesem Zeitpunkt für alternative Handlungsstränge.
  - **Vorlesen:** Liest die Nachricht per Voice AI vor.

Weiter zu: [**Administration & Einstellungen →**](admin.md)
