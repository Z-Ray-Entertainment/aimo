# 🌍 Worlds, Places & Events (WorldInfo)

[← Back to Overview](README.md) | [← Lorebooks](lorebooks.md) | [The Chat Interface →](chat.md)

A **WorldInfo** encapsulates the geography, scenes, and random events of a roleplay setting. It defines the visual 16:9 backgrounds in chat and enables spontaneous random encounters.

---

## 🏛️ WorldInfo Editor & Vertical Sidebar Navigation

The WorldInfo Editor is organized in a two-column layout with a vertical sidebar on the left and the main editing stage on the right:
- **Left Sidebar Navigation:**
  - **Sidebar Header:** Displays the world name and globe icon (`🗺️`).
  - **Vertical Navigation Menu:**
    1. **📋 Basic Settings (`Grundeinstellungen`):** Title, 1:1 cover artwork, visibility, and bound world lorebooks.
    2. **📍 Places (`Orte & Hintergründe`):** Gallery of all locations and 16:9 backgrounds (displays total count).
    3. **🎲 Random Events (`Zufalls-Events`):** Configured random encounters and probabilities (displays total count).
    4. **👥 Collaboration (`Kollaboration`):** Co-creator access management.
  - **Sidebar Footer:** Quick return button (`← Zurück zur Übersicht`) to jump directly back to the world overview or creations grid.
- **Right Main Stage:**
  - **Header Bar:** Shows the world title, read-only status (for non-editable worlds), and action buttons:
    - **Save (`💾 Speichern`):** Saves world settings and collaborator permissions.
    - **Duplicate (`📄 Kopieren`):** Deep-clones the entire world setting — including all locations, 16:9 backgrounds, and random event pools — into an independent duplicate for the creator.
    - **Delete (`🗑️ Löschen`):** Strictly reserved for the author and administrators.

---

## 📋 1. Basic Settings (`📋 Grundeinstellungen`)

- **World Name:** Setting title (e.g., *"Kingdom of Acheron"*).
- **1:1 Cover Image:** Square cover artwork for the World Grid tile and world selection dialog. Features an integrated cropping tool. Clicking the cover preview opens it in the fullscreen Image Viewer.
- **World Backdrop (16:9):** Optional 16:9 widescreen background for the chat stage when playing in this world. In chat, backgrounds follow the priority **System → World → Location**: a location's own background takes precedence, followed by the World Backdrop if set, and finally the global System Backdrop. You can upload a new image, click the backdrop preview to inspect it in the fullscreen Image Viewer, or remove the World Backdrop at any time.
- **Visibility:** Compact eye icon toggle button switching between **Private** (closed eye, visible only to you and collaborators) and **Public** (open eye, available for all players in the hub). Hovering over the button displays the active visibility state.
- **Bound Lorebook (Optional):** Creators can attach an encyclopedia ([Lorebook](lorebooks.md)) directly to the world.
  - Whenever a chat session is played in this world, this lorebook is automatically loaded as an active default lorebook.
  - Useful for overarching world lore, political factions, pantheons, and geography that apply to any character visiting this realm.
- **Save Button (`💾 Speichern`):** Direct save trigger at the foot of the settings form.

---

## 📍 2. Places (`📍 Orte & Hintergründe`)

A gallery of all locales in this world:
- First tile (`+`) to register a new place.
- **Grid Overview & Locked Locations:**
  - Each place is displayed as an atmospheric card tile (capsule) with its 16:9 preview and description snippet. Places with a background image also display a `🖼️` button in the upper-right corner of the preview to open the backdrop directly in the fullscreen Image Viewer.
  - **Character Lock (`🔒`):** Locations bound to a specific character display a lock badge in the upper-left corner of the capsule and a character pill next to the title.
  - **Hover Tooltip:** Hovering the mouse cursor over a locked capsule displays the tooltip: *"Dieser Ort ist an [Name] gebunden"*.
- **Location Overlay (Modal):**
  - **Name:** E.g., *"The Drunken Troll Tavern"*, *"Forgotten Glade"*.
  - **Tags:** Keywords for environment matching.
  - **Character Binding (Optional):** Creators can optionally restrict this location to a specific character. Only chats played with this designated character can visit or enter this venue. For all other characters, the location is inaccessible and omitted from their in-chat location options.
  - **16:9 Background Image:** Landscape image upload (PNG, JPG, WEBP). Serves as the atmospheric chat background and is passed to ComfyUI for consistent image generation. When a background image is set, a `🖼️` button next to the analyze button opens it in the fullscreen Image Viewer.
  - **Vision-ALT Tag & Interactive Text Expansion:** Upon image upload, a Vision model generates a visual scene description. The system then prompts interactively: *"Would you like to expand the location description with this AI image description?"*.
  - **Event Assignment:** List of world events tied specifically to this location.

---

## 🎲 3. Events (`🎲 Zufalls-Events`)

Events inject unexpected life into the world (e.g., sudden storm, wandering bandit, royal procession).
- First tile (`+`) to author a new event.
- **Event Tiles:** Display title, probability (`0 - 100%`), one-shot indicator, and a clear **scope badge** (tied location or *"Entire World"*).
- **Event Overlay (Modal):**
  - **Title:** E.g., *"Sudden Downpour"*.
  - **Scope:** Choose whether the event can occur anywhere (*"Entire World"*) or only at a specific place.
  - **Probability (0–100%):** Relative weight during random draws.
  - **One-Shot:** When checked, the event triggers at most once per chat session.
  - **Scenic Description:** The prose injected into the prompt when triggered so the AI reacts dynamically.

---

## 👥 4. Collaboration (`👥 Kollaboration`)

- **Creator-Tag Management:** The author can add trusted creators by their private **Creator-Tag** (UUID4).
- **Collaborative Worldbuilding:** Collaborators can create and edit locations, upload 16:9 backgrounds, and configure random events.
- **Ownership & Deletion Protection:** Deletion of the world setting and managing the collaborator list remains strictly limited to the author. Collaborators see their status in a clean read-only view.

---

## 🔄 In-Chat Cooldown & Trigger Mechanics

- **Unified Pool:** For every chat turn, the active pool of eligible random events combines up to four scopes:
  1. **World Global Events** (bound to the active world without a specific location)
  2. **World Location Events** (bound to the active world and the current location)
  3. **Character-Bound Events** (bound to the active character without a location constraint; optionally restricted to a relationship tier range)
  4. **Character & Location-Bound Events** (bound to both the active character and the current location; optionally restricted to a relationship tier range)
- **Message Counter (10–100):** When a chat starts, a random integer between 10 and 100 is rolled. Each player message sent decrements the counter by 1 dynamically during chatting.
- **Trigger at 0:** When the counter reaches 0, exactly one eligible event is drawn weighted by probability. Immediately afterward, a new counter is rolled (10–100). If no eligible event exists in the pool, a silent re-roll occurs.
- **Persistent Event Notice:** Upon trigger, the event is immediately displayed as a permanent system message in the chat history with a bolt icon (*"⚡ Ereignis: [Event-Titel]"*) and its narrative description without requiring a page reload. The AI character receives this event context and weaves it into its immediate reaction.
- **Live Cooldown Counter:** Administrators, authors and collaborators of the active world, and authors and collaborators of the active character can view the live remaining messages until the next event directly in the chat sidebar, which counts down dynamically as you chat.
- **Opt-Out & Pausing:** A toggle checkbox in the chat sidebar allows you to disable events at any time if you prefer uninterrupted scenes. The cooldown counter pauses and retains its current value.

Continue to: [**The Chat & Roleplay Interface →**](chat.md)
