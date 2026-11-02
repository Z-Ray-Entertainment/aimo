# 💬 The Chat & Roleplay Interface

[← Back to Overview](README.md) | [← Worlds & Places](worldinfo.md) | [Administration & Settings →](admin.md)

The chat screen is the centerpiece of aimo. Here, the interactive text adventure unfolds with live token streaming, emotional sprites, dynamic location transitions, and generative imagery.

---

## 🚀 Starting a Chat ("New Chat" Configuration)

When starting a new conversation with a character:
1. **Reiter 1: Settings (Einstellungen):**
   - **Persona Selection:** Select your playing persona. (Once the first message is sent, the persona is permanently locked for that session).
   - **WorldInfo Selection:** Choose the setting. The character's suggested world is pre-selected. You can also explicitly choose *"Without WorldInfo"* (applies neutral backgrounds and disables random events).
   - **Session Title:** Optional custom title for the adventure.
2. **Reiter 2: Lorebooks (Wissensbücher):**
   - Inspect all default lorebooks inherited from the character and the selected world.
   - Toggle individual lorebooks on or off specifically for this session.
   - Add custom lorebooks from the system catalog or remove them.
3. **Launch & Welcome Message:** Upon clicking *"Abenteuer starten"*, the chat opens and the character greets you with their opening message at the designated starting location.

---

## 🖥️ Screen Layout

- **Header:** Back button (`←`) to the main overview.
- **Left Sidebar (Multi-Chat):** Lists all your chat sessions and forks with this character. Titles update dynamically based on key events.
- **Central Four-Tab Container:**
  - **Tab 1: Chat:** The ongoing dialogue in message bubbles (AI on the left with portrait/sprite, player on the right).
  - **Tab 2: Media:** Aggregates all unlocked 9:16 gallery images, uploaded photos, and generated images.
  - **Tab 3: Memories:** Lists all system-generated memory summaries and allows manual edits.
  - **Tab 4: Lorebooks:** Live lorebook manager showing active, toggled, and custom lorebooks for this session.
- **Right Info Box:**
  - Character portrait / transparent emotion sprite.
  - Dynamic relationship bar (-100 to +100 with heart icon).
  - Active WorldInfo with edit pencil.
  - Player persona badge.
  - Actions: Events toggle (checkbox), New Chat, Delete Chat.

---

## 📜 In-Chat Lorebook Management

Under the **Lorebooks** tab in the central chat container (and in the New Chat wizard), players have full control over the knowledge injected into their session:
- **Default Lorebooks:**
  - Automatically assembled from the Character's linked lorebooks and the active World's lorebook.
  - **Session Toggle (Slider):** Players can temporarily disable or re-enable individual default lorebooks for this specific chat without modifying the character or world definition.
  - **Conditional Locks (`🔒 Inaktiv — Benötigt Welt: ...`):** If a character lorebook requires a specific world condition not met by the current session, it is locked. The toggle is disabled and its entries are excluded from the prompt.
- **Custom Lorebooks:**
  - Players can click *„➕ Lorebook hinzufügen“* to browse available encyclopedias in a searchable grid overlay and add them to the chat session.
  - Custom lorebooks appear in a separate section below default lorebooks.
  - They feature both an active/inactive toggle slider and a trash button (🗑️) to remove them completely from the session.
- **Order:** Default lorebooks appear at the top, custom lorebooks at the bottom; both sections are sorted alphabetically.

---

## ⚡ Live Streaming & Seamless Localization

Because modern LLMs write with the greatest depth and nuance in English while the UI operates in your localized language, aimo employs a two-stage streaming workflow:
1. **Live Stream (English):** When submitted, a *"Thinking..."* state appears. The raw English token stream streams into the message bubble in real time — **dimmed in gray and rendered in smaller text** so you can follow the generation progress.
2. **Translation Swap:** The instant generation finishes, a brief spinner appears and the dimmed English text is cleanly replaced by the **final translated text** in standard font size.

---

## 🧭 Interactive Location Transitions & Venue Management (Text Adventure)

- **Character-Bound Location Filtering:** Locations bound to another character are completely hidden from the chat's location dropdown and will never be suggested by the AI narrative. Only unrestricted locations and venues bound to the active character are accessible.
- **Manual Location Selector:** Located in the right sidebar under the active WorldInfo. Players can freely choose between all accessible locations within the world at any time.
- **Dynamic AI Location Suggestions:** When the AI narrative suggests travelling to an accessible location (e.g., *"Let us set out into the forest"*):
  - A confirmation button appears in chat: *"Would you like to move to [New Location]? [Yes] [No]"*.
  - **60-Second Countdown:** A red progress bar along the bottom edge of the button steadily shrinks over 60 seconds. If ignored, the prompt silently dissolves.
  - **On "Yes":** The location shifts, the 16:9 background image changes, and a discreet centered system notification appears: *"You travelled to {location}"*. This notice is **never** added to the LLM prompt history.

---

## 🎨 Multimodal Features & Input Bar

- **Paperclip Icon (Image Upload):** Attach any image to your message. A Vision model generates a concise ALT description in the background, providing the AI with situational awareness of what you showed it.
- **Magic Wand with Sparkles ✨ (ComfyUI Image Generation):**
  - Generates a scene illustration via ComfyUI based on current narrative context.
  - During generation, a centered status indicator displays *"Generating image..."* and user input is locked.
  - A **Cancel Button** allows you to abort generation at any time and immediately unlocks input.
  - The generated image renders directly in chat and archives under the *"Media"* tab.

---

## 💔 Relationship Dynamics & Memories

- **Affection Score:** Each message sent by the player increases the score by `+0.1`. Extended inactivity decreases the score by `-0.1` per day (bounded between -100.0 and +100.0).
- **Unlockable Artwork:** Once the relationship reaches the threshold set on a 9:16 character image, it automatically unlocks in the *"Media"* tab.
- **Memories (Every 10 Messages):** Every 10 messages, a background LLM summarizes recent events and refreshes the chat session title in the sidebar.
- **Three-Dot Menu (`...`):**
  - **Delete Message:** Deletes the selected message along with all subsequent messages and cascaded memories.
  - **Fork Chat:** Clones the conversation from this exact point forward into a branching timeline.
  - **Read Aloud:** Synthesizes and plays back the message via Voice AI.

---

## 📡 Connection Status & Notifications

While you chat, floating notification banderoles in the bottom-right corner keep you informed about system status without disrupting your roleplay:
- **Connection Issues:** If the connection to the application server is lost, a red-striped banderole informs you (*„Verbindung zum Backend verloren“*).
- **AI Service Issues:** If the AI text model is unreachable or paused, a red-striped banderole alerts you (*„Verbindung zu Ollama verloren“*).
- **Timeouts:** If a reply takes unusually long, a yellow-striped warning banderole indicates a timeout.
- **Replies from Other Chats:** When another character finishes generating a response while you are looking at a different chat, a notification banderole slides in with their portrait and a *„Zum Chat →“* button to switch over immediately.

Continue to: [**Administration & Settings →**](admin.md)
