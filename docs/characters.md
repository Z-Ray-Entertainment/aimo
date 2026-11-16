# 🎭 AI Characters & Character Designer

[← Back to Overview](README.md) | [← Player Personas](personas.md) | [Lorebooks & Encyclopedias →](lorebooks.md)

The **Character Designer** allows creators to craft detailed interactive AI characters complete with emotional sprites, unlockable gallery artwork, and dynamic location preferences.

---

## 🏛️ Structure & Vertical Sidebar Navigation

The Character Designer uses a modern two-column layout consistent with the Administration and Settings panels:
- **Left Sidebar Navigation:**
  - **Sidebar Header:** Displays the character's name and icon (`🎭`).
  - **Vertical Navigation Menu:** Direct access to all seven functional areas:
    1. **📋 Main Information (`Hauptinformationen`):** Core persona details, name, gender, bio, and welcome message.
    2. **🖼️ Unlockable Gallery Images (`Galeriebilder`):** High-resolution 9:16 artwork tied to affection thresholds.
    3. **🎭 Emotional Sprites (`Emotionale Sprites`):** Dynamic 28-emotion sprites that adapt during chat.
    4. **💬 Dialogue Styles (`Gesprächsstile`):** Representative conversation examples.
    5. **🗺️ World Settings (`World`):** Recommended world and location preferences.
    6. **📖 Linked Lorebooks (`Lorebooks`):** Encyclopedias bound directly to the character.
    7. **👥 Collaboration (`Kollaboration`):** Co-creator access management.
  - **Sidebar Footer:** Includes a quick return button (`← Zurück zur Übersicht`) to navigate back to the character gallery or creations overview.
- **Right Main Stage:**
  - **Header Bar:** Shows the character title, read-only status (for non-editable characters), and action buttons:
    - **Save (`💾 Speichern`):** Saves character data and dialogue styles.
    - **Duplicate (`📄 Kopieren`):** Deep-clones the character into an independent duplicate you own.
    - **Delete (`🗑️ Löschen`):** Reserved for the author and administrators.

---

## 📝 1. Main Information (`📋 Hauptinformationen`)

- **Name:** Character's name.
- **Gender:** `male`, `female`, or `non-binary`.
- **Primary Portrait (Mandatory):** Main portrait image used for tiles and default chat presentation.
- **Description & AI Sparkle ✨:**
  - Define personality, speech patterns, quirks, and mannerisms.
  - **AI Writing Assistant:** Clicking the magic wand with sparkles ✨ automatically enhances your draft using a specialized author prompt.
- **First Message (Welcome Message):** The character's opening greeting, automatically presented when starting a new chat session.

---

## 🖼️ 2. Unlockable Gallery Images (`🖼️ Galeriebilder`)

- Smartphone/portrait-oriented images (9:16 aspect ratio).
- **Affection Threshold:** Assign a value between `-100 and +100` to each image. As soon as your relationship score in a chat meets this threshold, the image unlocks under the *"Media"* tab!

---

## 🎭 3. Emotional Sprites (`🎭 Emotionale Sprites`)

aimo supports dynamic, transparent sprites (PNG or WEBP) that adapt to the AI character's current emotional state during conversations.

### The 28 Supported Emotions
`admire`, `amused`, `anger`, `annoyed`, `approval`, `caring`, `confused`, `curious`, `desire`, `disappointed`, `disapproval`, `disgust`, `embarrassed`, `excited`, `fear`, `gratitude`, `grief`, `joy`, `love`, `nervousness`, `neutral` (Default & Fallback), `optimistic`, `pride`, `realize`, `relief`, `remorse`, `sad`, `surprise`.

### Variants & Stackview
- **Multiple Variants per Emotion:** You can upload multiple sprites for any single emotion (e.g., `joy_1.png`, `joy_2.webp`).
- **Paper-Plus Button (📄➕):** Becomes visible once at least one sprite exists for an emotion, enabling you to add additional variants.
- **Stackview & Eye Button (👁️):** When multiple variants exist, a layered stack effect indicates the variety. Clicking the eye button opens a modal popup to inspect variants and delete individual images.
- **Runtime Random Selection:** When the AI expresses an emotion, the system selects one of the available variants at random.

---

## 💬 4. Dialogue Styles (`💬 Gesprächsstile`)

- Representative conversation snippets (User / Assistant turns) to calibrate the character's tone, vernacular, dialect, and speech habits.

---

## 🗺️ 5. World Settings (`🗺️ World`)

- **Recommended WorldInfo:** Select a suggested [WorldInfo](worldinfo.md) setting.
- **Location Preferences:** Specify **preferred locations** (places the character enjoys visiting) and **disliked locations** (places they avoid).

---

## 📖 6. Linked Lorebooks & World Conditions (`📖 Lorebooks`)

Under the **Lorebooks** section in the Character Designer, creators can bind one or more [Lorebooks](lorebooks.md) directly to the character:
- **Binding Lorebooks:** Click *„➕ Lorebook hinzufügen“* to attach thematic encyclopedias to this character.
- **World Condition Dropdown:** Beside each attached lorebook, a condition dropdown determines when the lorebook should become active:
  - `🌍 All Worlds (Always active)`: The lorebook is injected into any chat with this character, regardless of the active setting.
  - `🌐 Only in World: [World Name]`: The lorebook is strictly tied to a specific world.
- **Strict AND Evaluation:**
  - If a lorebook requires World *X*, it will **only** be active in chat sessions where both this character **AND** World *X* are simultaneously active.
  - If the player starts a chat without a world or in a different world, the lorebook is marked as locked (`🔒 Inaktiv — Benötigt Welt: [Name]`) and its tag entries are **not** injected into the prompt.
  - In-chat toggle sliders for locked lorebooks are disabled and cannot be forced on.

---

## 👥 7. Collaboration (`👥 Kollaboration`)

- **Collaborator Management:** Authors can invite other creators by adding their private **Creator-Tag** (UUID4).
- **Shared Creation:** Collaborators can edit all tabs, upload sprites, add gallery images, and adjust prompts.
- **Author Protection:** Only the author can delete the character or manage the collaborator list. Collaborators see their status in a clean read-only view.

Continue to: [**Lorebooks & Encyclopedias →**](lorebooks.md)
