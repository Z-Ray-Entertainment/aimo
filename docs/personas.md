# 👤 Player Personas

[← Back to Overview](README.md) | [← The Hub Dashboard](hub.md) | [AI Characters & Designer →](characters.md)

A **Player Persona** represents your personal identity in the roleplay. You can create multiple distinct personas (e.g., mage, knight, detective) and select which identity to embody before initiating a chat.

---

## 🗂️ Persona Overview

Open **⚙️ Einstellungen** from the account menu; **Personas** is the first view. All your personas appear as square portrait tiles in a framed panel titled *Spieler-Personas*:
- **First tile (`+`):** Creates a new persona.
- **Top-left badge:** Shows the gender of the persona.
- **Star (top-right):** A filled golden star (★) marks your default persona. An empty star (☆) on any other persona makes it your default with a single click.
- **Hovering a tile:** Shows the description of the persona.
- **Name:** Displayed at the bottom of each tile.
- **Clicking a tile:** Opens the persona editor.

The first persona you create automatically becomes your default persona.

---

## ✏️ Persona Editor

Creating and editing happens in an overlay window:
- **Fields:** Name, gender, portrait image, description, and appearance (see below).
- **Image Crop (1:1):** After choosing a portrait, a crop window opens where you can move and resize a square selection. The **✂️ Ausschnitt anpassen (1:1)** button reopens it at any time. A green check mark confirms an active crop.
- **Buttons:** *Speichern* saves your changes, *Abbrechen* closes the window without saving.
- **Löschen (editing only):** Deletes the persona. It is locked (🔒) if the persona is used in a chat.

---

## 🎨 Persona Properties

- **Name:** Your character name in the roleplay, used by AI characters when addressing you.
- **Gender:** Ensures consistent grammatical addressing (`male`, `female`, `non-binary`).
- **Portrait Image:** Image file (PNG, JPG, WEBP), cropped to a square, serving as your avatar in chat and as a reference image for [image generation](chat.md#multimodal-features--input-bar).
- **Description:** Backstories, motives, behavioral traits, and personal quirks.
- **Appearance:** Detailed textual description of physical traits.

---

## 👁️ Automated Vision Appearance Analysis

Whenever you upload and save a portrait image for your persona:
1. **AI Scan:** A Vision model (via Ollama) scans the face and visible physical attributes (hair color, eye color, complexion, build).
2. **Focus Rule:** Backgrounds, rooms, and situational poses are intentionally ignored.
3. **Automatic Field Population:** The *"Appearance"* field is automatically populated with these physical traits.
4. **Full Control:** You can manually edit or refine the *"Appearance"* field at any time. The system only triggers a new scan if you replace the portrait image.

---

## 🛡️ Protection Rule: Deletion Lock for Active Personas

To protect the narrative consistency of existing conversations:
- **Personas that are referenced in at least one chat session cannot be deleted.**
- In this case, the delete button is disabled and displays an explanatory tooltip.

Continue to: [**AI Characters & Designer →**](characters.md)
