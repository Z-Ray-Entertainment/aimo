# 🎭 AI Characters & Character Designer

[← Back to Overview](README.md) | [← Player Personas](personas.md) | [Lorebooks & Encyclopedias →](lorebooks.md)

The **Character Designer** allows creators to craft detailed interactive AI characters complete with emotional sprites, unlockable gallery artwork, and dynamic location preferences.

---

## 🏛️ Structure & Vertical Sidebar Navigation

The Character Designer uses a modern two-column layout consistent with the Administration and Settings panels:
- **Left Sidebar Navigation:**
  - **Sidebar Header:** Displays the character's name and icon (`🎭`).
  - **Vertical Navigation Menu:** Direct access to all eight functional areas:
    1. **📋 Main Information (`Hauptinformationen`):** Core persona details, name, gender, bio, and welcome message.
    2. **🖼️ Unlockable Gallery Images (`Galeriebilder`):** High-resolution 9:16 artwork tied to affection thresholds.
    3. **🎭 Emotional Sprites (`Emotionale Sprites`):** Dynamic 28-emotion sprites that adapt during chat.
    4. **💬 Dialogue Styles (`Gesprächsstile`):** Representative conversation examples.
    5. **🗺️ World Settings (`World`):** Recommended world and location preferences.
    6. **🎲 Random Events (`Zufalls-Events`):** Character-specific dynamic random events with optional location constraints.
    7. **📖 Linked Lorebooks (`Lorebooks`):** Encyclopedias bound directly to the character.
    8. **👥 Collaboration (`Kollaboration`):** Co-creator access management.
  - **Sidebar Footer:** Includes a quick return button (`← Zurück zur Übersicht`) to navigate back to the character gallery or creations overview.
- **Right Main Stage:**
  - **Header Bar:** Shows the character title, read-only status (for non-editable characters), and action buttons:
    - **Save (`💾 Speichern`):** Saves character data and dialogue styles.
    - **Duplicate (`📄 Kopieren`):** Deep-clones the character into an independent duplicate you own.
    - **Delete (`🗑️ Löschen`):** Reserved for the author and administrators.

---

## 📝 1. Main Information (`📋 Hauptinformationen`)

- **Name:** Character's name.
- **Gender:** Icon-only single-select pill-badges (`♀️`, `♂️`, `⚧️`, with `Non-Binary` selected by default). Hovering over a pill-badge displays the corresponding label (`Female`, `Male`, or `Non-Binary`).
- **Primary Portrait (Mandatory):** Main 9:16 portrait and 1:1 avatar image used for tiles and default chat presentation. Clicking either preview thumbnail opens it in the fullscreen Image Viewer.
- **Description & AI Sparkle ✨:**
  - Define personality, speech patterns, quirks, and mannerisms.
  - **KI-Autor Optimierung (AI Writing Assistant ✨):** Clicking this button above the description textarea automatically drafts or enhances the character description based on the provided character name and draft text. The assistant writes exclusively in natural, continuous prose paragraphs without markdown, headings, bullet lists, or bolding. While generating, the button displays animated bouncing dots alongside "Optimiere Beschreibung" and upon completion populates the description field directly with status feedback.
- **First Message (Welcome Message):** The character's opening greeting, automatically presented when starting a new chat session.

---

## 🖼️ 2. Unlockable Gallery Images (`🖼️ Galeriebilder`)

- Smartphone/portrait-oriented images (9:16 aspect ratio).
- **Affection Threshold:** Assign a relationship tier (from *Pure Hatred* to *Blind Devotion*) to each image. As soon as your relationship in a chat reaches this tier, the image unlocks under the *"Media"* tab!
- **Fullscreen Gallery:** Clicking any gallery image opens all uploaded gallery images in a browsable fullscreen Image Viewer.

---

## 🎭 3. Emotional Sprites (`🎭 Emotionale Sprites`)

aimo supports dynamic, transparent sprites (PNG or WEBP) that adapt to the AI character's current emotional state during conversations.

### The 28 Supported Emotions
`admire`, `amused`, `anger`, `annoyed`, `approval`, `caring`, `confused`, `curious`, `desire`, `disappointed`, `disapproval`, `disgust`, `embarrassed`, `excited`, `fear`, `gratitude`, `grief`, `joy`, `love`, `nervousness`, `neutral` (Default & Fallback), `optimistic`, `pride`, `realize`, `relief`, `remorse`, `sad`, `surprise`.

### Variants & Stackview
- **Multiple Variants per Emotion:** You can upload multiple sprites for any single emotion (e.g., `joy_1.png`, `joy_2.webp`).
- **Paper-Plus Button (📄➕):** Becomes visible once at least one sprite exists for an emotion, enabling you to add additional variants.
- **Stackview & Eye Button (👁️):** When multiple variants exist, a layered stack effect indicates the variety. Clicking the eye button opens a modal popup to inspect variants and delete individual images. Clicking a sprite preview or variant image opens it in the fullscreen Image Viewer (browsable across all variants of that emotion).
- **Runtime Random Selection:** When the AI expresses an emotion, the system selects one of the available variants at random.

---

## 💬 4. Dialogue Styles (`💬 Gesprächsstile`)

Representative conversation snippets (Few-Shot trigger and response pairs) that calibrate the character's tone, vernacular, dialect, mannerisms, and emotional reactions:
- **Add Dialogue Style (`➕ Gesprächsstil hinzufügen`):** Opens an overlay modal to define a player trigger (`{{user}}`) and character response (`{{char}}`).
- **AI Author (`✨ Mit KI ausfüllen`):** Inside the modal, creators can tap the AI Author button to generate situational dialogue examples directly from the character's description in the user's configured language.
  - **Context-Aware:** If a trigger prompt is already provided, the AI drafts exclusively the authentic response; if empty, it invents a complete, fresh interaction.
  - **Dynamic Placeholders:** Generated examples utilize `{{user}}` and `{{char}}` tokens so they remain universally adaptable across any player persona.
  - **Roleplay Styling:** Formats responses with spoken dialogue in quotation marks and narrative actions, gestures, and expressions in asterisks.
- **Edit & Delete:** Existing dialogue examples can be reviewed, edited, or deleted from the list at any time.

---

## 🗺️ 5. World Settings (`🗺️ World`)

- **Recommended WorldInfo:** Select a suggested [WorldInfo](worldinfo.md) setting.
- **Location Preferences:** Specify **preferred locations** (places the character enjoys visiting) and **disliked locations** (places they avoid).

---

## 🎲 6. Random Events (`🎲 Zufalls-Events`)

Character-specific random events introduce dynamic situations exclusive to chats with this character (for example, an old acquaintance suddenly appearing, a secret personal memory resurfacing, or an unexpected character habit triggering).
- **Tile Grid & Modal Editor:** Uses the same unified event editor as [WorldInfo](worldinfo.md). Click the `+` tile to create a new character event or click any existing event tile to edit or delete it.
- **Scope & Optional Location Binding:**
  - `🎭 Charakterweit (Überall)`: The event can trigger anywhere during chats with this character, regardless of the active location or whether a world is selected.
  - `📍 Ort: [Location Name]`: Optionally restricts the character event so it can only trigger when chatting with this character at that specific location. Only locations belonging to the character's currently configured *Recommended WorldInfo* (and accessible to this character) are available. If the recommended WorldInfo is changed or removed, existing location bindings on character events automatically reset to location-independent while preserving the events themselves.
- **Relationship Range (Optional):** Inside the event modal, a dual-ended slider lets you optionally restrict the event to a specific relationship tier range (displayed as `[From Tier] – [To Tier]` above the slider, from *Pure Hatred* to *Blind Devotion*). Leaving both ends at the outer limits allows the event at any relationship stage. Event tiles with an active relationship restriction display a compact `❤️` pill badge (with the tooltip *"Beziehungsgebunden"*).
- **Probability (0–100%):** Relative weight inside the chat's combined event pool.
- **One-Shot:** When enabled, the event triggers at most once per chat session.
- **Scenic Description:** When triggered, the narrative description is revealed in the chat history and woven organically into the character's next response.

---

## 📖 7. Linked Lorebooks & World Conditions (`📖 Lorebooks`)

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

## 👥 8. Collaboration (`👥 Kollaboration`)

- **Collaborator Management:** Authors can invite other creators by adding their private **Creator-Tag** (UUID4).
- **Shared Creation:** Collaborators can edit all tabs, upload sprites, add gallery images, and adjust prompts.
- **Author Protection:** Only the author can delete the character or manage the collaborator list. Collaborators see their status in a clean read-only view.

Continue to: [**Lorebooks & Encyclopedias →**](lorebooks.md)
