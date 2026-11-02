# 🌍 Worlds, Places & Events (WorldInfo)

[← Back to Overview](README.md) | [← Lorebooks](lorebooks.md) | [The Chat Interface →](chat.md)

A **WorldInfo** encapsulates the geography, scenes, and random events of a roleplay setting. It defines the visual 16:9 backgrounds in chat and enables spontaneous random encounters.

---

## 🏛️ WorldInfo Editor (`templates/worldinfo/detail.html`)

- **World Name:** Setting title (e.g., *"Kingdom of Acheron"*).
- **WorldInfo Icon (`icon`):** A representative icon or graphic shown in headers and chat sidebars.
- **World Lorebook (Optional):** Creators can attach an encyclopedia ([Lorebook](lorebooks.md)) directly to the world.
  - Whenever a chat session is played in this world, this lorebook is automatically loaded as an active default lorebook.
  - Useful for overarching world lore, political factions, pantheons, and geography that apply to any character visiting this realm.

The editor is divided into two functional tabs:

---

## 📍 Tab 1: Places (Locations)

A gallery of all locales in this world:
- First tile (`+`) to register a new place.
- **Location Overlay (Modal):**
  - **Name:** E.g., *"The Drunken Troll Tavern"*, *"Forgotten Glade"*.
  - **Tags:** Keywords for environment matching.
  - **Description:** Atmospheric prose describing sensory details, sounds, lighting, and mood.
  - **16:9 Background Image:** Landscape image upload (PNG, JPG, WEBP). Serves as the atmospheric chat background and is passed to ComfyUI for consistent image generation.
  - **Vision-ALT Tag & Interactive Text Expansion:** Upon image upload, a Vision model generates a visual scene description. The system then prompts interactively: *"Would you like to expand the location description with this AI image description?"*.
  - **Event Assignment:** List of events tied specifically to this location.

---

## ⚡ Tab 2: Events (Random Encounters)

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

## 🔄 In-Chat Cooldown & Trigger Mechanics

- **Unified Pool:** World events and location events for the current venue form a single combined pool.
- **Message Counter (10–100):** When a chat starts, a random integer between 10 and 100 is rolled. Each message sent (by user or AI) decrements the counter by 1.
- **Trigger at 0:** When the counter reaches 0, exactly one eligible event is drawn weighted by probability. Immediately afterward, a new counter is rolled (10–100).
- **Opt-Out:** A toggle checkbox in the chat sidebar allows you to disable events at any time if you prefer uninterrupted scenes.

Continue to: [**The Chat & Roleplay Interface →**](chat.md)
