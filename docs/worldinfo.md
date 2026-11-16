# 🌍 Worlds, Places & Events (WorldInfo)

[← Back to Overview](README.md) | [← Lorebooks](lorebooks.md) | [The Chat Interface →](chat.md)

A **WorldInfo** encapsulates the geography, scenes, and random events of a roleplay setting. It defines the visual 16:9 backgrounds in chat and enables spontaneous random encounters.

---

## 🏛️ WorldInfo Editor (`templates/worldinfo/detail.html`)

- **Header & Actions:**
  - **Back Button (`← Zurück`):** Returns directly to the previous view you came from (such as My Creations or the central World Grid).
  - **World Title & Badges:** Displays the name of the world and a readonly badge (`🔒 Schreibgeschützt`) if viewing another creator's world without edit permissions.
  - **Save (`💾 Speichern`):** Saves world metadata, cover image, and collaborator settings.
  - **Duplicate (`📄 Kopieren`):** Deep-clones the entire world setting — including all locations, 16:9 backgrounds, and random event pools — into an independent duplicate for the creator.
  - **Delete (`🗑️ Löschen`):** Strictly reserved for the author and all administrators.

The editor is organized into four functional tabs:

---

## 📋 Tab 1: Basic Settings (`📋 Grundeinstellungen`)

- **World Name:** Setting title (e.g., *"Kingdom of Acheron"*).
- **1:1 Cover Image:** Square cover artwork for the World Grid tile and world selection dialog. Features an integrated cropping tool (`AimoImageCropper`).
- **Visibility:** Toggle between `Private` (visible only to you and collaborators) and `Public` (available for all players in the hub).
- **Bound Lorebook (Optional):** Creators can attach an encyclopedia ([Lorebook](lorebooks.md)) directly to the world.
  - Whenever a chat session is played in this world, this lorebook is automatically loaded as an active default lorebook.
  - Useful for overarching world lore, political factions, pantheons, and geography that apply to any character visiting this realm.
- **Save Button (`💾 Speichern`):** Direct save trigger at the foot of the settings form.

---

## 📍 Tab 2: Places (Locations)

A gallery of all locales in this world:
- First tile (`+`) to register a new place.
- **Grid Overview & Locked Locations:**
  - Each place is displayed as an atmospheric card tile (capsule) with its 16:9 preview and description snippet.
  - **Character Lock (`🔒`):** Locations bound to a specific character display a lock badge in the upper-left corner of the capsule and a character pill next to the title.
  - **Hover Tooltip:** Hovering the mouse cursor over a locked capsule displays the tooltip: *"Dieser Ort ist an [Name] gebunden"*.
- **Location Overlay (Modal):**
  - **Name:** E.g., *"The Drunken Troll Tavern"*, *"Forgotten Glade"*.
  - **Tags:** Keywords for environment matching.
  - **Character Binding (Optional):** Creators can optionally restrict this location to a specific character. Only chats played with this designated character can visit or enter this venue. For all other characters, the location is inaccessible and omitted from their in-chat location options.
  - **16:9 Background Image:** Landscape image upload (PNG, JPG, WEBP). Serves as the atmospheric chat background and is passed to ComfyUI for consistent image generation.
  - **Vision-ALT Tag & Interactive Text Expansion:** Upon image upload, a Vision model generates a visual scene description. The system then prompts interactively: *"Would you like to expand the location description with this AI image description?"*.
  - **Event Assignment:** List of events tied specifically to this location.

---

## ⚡ Tab 3: Events (Random Encounters)

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

## 👥 Tab 4: Collaboration (`👥 Kollaboration`)

- **Creator-Tag Management:** The author can add trusted creators by their private **Creator-Tag** (UUID4).
- **Collaborative Worldbuilding:** Collaborators can create and edit locations, upload 16:9 backgrounds, and configure random events.
- **Ownership & Deletion Protection:** Deletion of the world setting and managing the collaborator list remains strictly limited to the author. Collaborators see their status in a clean read-only view.

---

## 🔄 In-Chat Cooldown & Trigger Mechanics

- **Unified Pool:** World events and location events for the current venue form a single combined pool.
- **Message Counter (10–100):** When a chat starts, a random integer between 10 and 100 is rolled. Each message sent (by user or AI) decrements the counter by 1.
- **Trigger at 0:** When the counter reaches 0, exactly one eligible event is drawn weighted by probability. Immediately afterward, a new counter is rolled (10–100).
- **Opt-Out:** A toggle checkbox in the chat sidebar allows you to disable events at any time if you prefer uninterrupted scenes.

Continue to: [**The Chat & Roleplay Interface →**](chat.md)
