# 💬 The Chat & Roleplay Interface

[← Back to Overview](README.md) | [← Worlds & Places](worldinfo.md) | [Administration & Settings →](admin.md)

The chat screen is the centerpiece of AImo. Here, the interactive text adventure unfolds with live token streaming, emotional sprites, dynamic location transitions, and generative imagery.

---

## 🚀 Starting a Chat ("New Chat" Configuration)

When starting a new conversation with a character:
1. **Reiter 1: Settings (Einstellungen):**
   - **Persona Selection:** Select your playing persona. (Once the first message is sent, the persona is permanently locked for that session).
   - **WorldInfo Selection:** Choose the setting. The character's suggested world is pre-selected. You can also explicitly choose *"Without WorldInfo"* (applies the global System Backdrop and disables random events). When a world is active, the chat background follows the priority **System → World → Location** (a location's own background overrides the world's backdrop, which in turn overrides the System Backdrop).
   - **Session Title:** Optional custom title for the adventure.
   - **Thinking (Reasoning) Toggle:** Option to activate or deactivate deep chain-of-thought reasoning for compatible models (e.g., Gemma 4, DeepSeek-R1). Deactivating provides faster replies without internal thinking steps.
2. **Reiter 2: Lorebooks (Wissensbücher):**
   - Inspect all default lorebooks inherited from the character and the selected world.
   - Toggle individual lorebooks on or off specifically for this session.
   - Add custom lorebooks from the system catalog or remove them.
3. **Launch & Welcome Message:** Upon clicking *"Abenteuer starten"*, the chat opens and the character greets you with their opening message at the designated starting location.

---

## 🖥️ Screen Layout

- **Header:** Back button (`←`) to the main overview.
- **Left Sidebar (Multi-Chat):** Lists all your chat sessions and forks with this character. Titles update dynamically based on key events.
- **Central Five-Tab Container:**
  - **Tab 1: Chat:** The ongoing dialogue in message bubbles (AI on the left with portrait/sprite, player on the right). Clicking an uploaded or generated image in a message, or the character's 1:1 avatar next to a reply, opens it in the fullscreen Image Viewer.
  - **Tab 2: Media:** Aggregates all unlocked 9:16 character gallery images as well as uploaded photos and generated images from the session, plus a button below the session images to view the active world's backdrop (`🖼️`) when available. Clicking any image opens the corresponding section as a browsable fullscreen gallery.
  - **Tab 3: Memories:** Lists all system-generated memory summaries and allows manual edits.
  - **Tab 4: Lorebooks:** Live lorebook manager showing active, toggled, and custom lorebooks for this session.
  - **Tab 5: Settings (`⚙️`):** Central session configuration containing your **Active Persona** (switchable until the first message is sent, plus an edit button `✏️`), **World** selection (with a warning notice about potential memory inconsistencies when switching worlds mid-chat), **Random Events** toggle (shown whenever world or character events exist), and—exclusively for character authors and administrators—**Relationship Settings** (per-message relationship debug labels toggle and, for administrators, relationship recalculation).
- **Right Info Box:**
  - Character portrait / transparent emotion sprite (dynamically scaled in 9:16 aspect ratio to fit the display height), equipped with an aesthetic Brain overlay icon (🧠) in the top-right corner with a live hover tooltip. The icon visually indicates whether Thinking is active (in color with a soft glow) or inactive (in monochrome gray). Clicking the character portrait or active sprite opens it in the fullscreen Image Viewer.
  - Character name bar directly beneath the portrait serving as the dynamic relationship indicator: a background gradient fills behind the centered character name with a dynamic heart icon on the left, and hovering over the bar displays the current qualitative relationship status title (e.g. *„Neutral“*, *„Friendly“*, *„Affection“*, *„Blind Devotion“*).
  - Location & Event block: Manual location selector (with a `🖼️` button next to the location indicator in the header to view the current location's backdrop when available), and a live event cooldown counter for administrators as well as authors and collaborators of the active world or character (updating dynamically as messages are exchanged).

### 🖼️ Fullscreen Image Viewer
- **Single-Image View:** Clicking the character's sidebar portrait/sprite, a character's 1:1 avatar in chat, an uploaded or generated image inside a chat message, or a world/location `🖼️` backdrop button opens that exact image in a clean fullscreen overlay.
- **Gallery View (Media Tab):** Clicking an unlocked 9:16 character image or a session media tile inside the **Media** tab opens a browsable fullscreen gallery for that section, complete with an image counter (e.g., `2 / 5`) and navigation arrows (`‹` / `›`).
- **Controls:** Navigate galleries with the on-screen arrows, keyboard arrow keys (`←` / `→`), or horizontal touch swipes. Close the viewer at any time via the `✕` button, the `Esc` key, or by clicking the dark background outside the image.

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

Because modern LLMs write with the greatest depth and nuance in English while the UI operates in your localized language, AImo employs a two-stage streaming workflow:
1. **Live Stream (English):** When submitted, a *"Thinking..."* state appears. The raw English token stream streams into the message bubble in real time — **dimmed in gray and rendered in smaller text** so you can follow the generation progress.
2. **Translation Swap:** The instant generation finishes, a brief spinner appears and the dimmed English text is cleanly replaced by the **final translated text** in standard font size.

---

## 🧭 Interactive Location Transitions & Venue Management (Text Adventure)

- **Starting Location & Introduction:** The introductory box at the very top of the chat history displays the original starting location where the adventure began.
- **Character-Bound Location Filtering:** Locations bound to another character are completely hidden from the chat's location dropdown and will never be suggested by the AI narrative. Only unrestricted locations and venues bound to the active character are accessible.
- **Manual Location Selector:** Located in the right sidebar under the active WorldInfo. Players can freely choose between all accessible locations within the world at any time, or return to the overarching **World** (`🌐 <World Name> (World)`) to leave a specific venue—restoring the world's backdrop and world-level context without being tied to a particular place.
- **Dynamic AI Location Suggestions:** When the AI narrative suggests travelling to an accessible location (e.g., *"Let us set out into the forest"*):
  - A confirmation button appears in chat: *"Would you like to move to [New Location]? [Yes] [No]"*.
  - **60-Second Countdown:** A red progress bar along the bottom edge of the button steadily shrinks over 60 seconds. If ignored, the prompt silently dissolves.
  - **On "Yes":** The location shifts, the 16:9 background image changes, and a permanent, gold-accented system notification (*"📍 Ortswechsel: [Ort]"*) is created directly at that point in the chat stream.
- **Persistent Chat History:** Location transition notices remain permanently anchored at the exact point in the conversation where they took place and remain visible upon reopening or reloading the chat session. System messages are never fed into the roleplay AI context.
- **Rewinding & Cascading Deletions:**
  - Deleting messages prior to a location transition automatically removes all subsequent messages including the location change notices.
  - When messages are rolled back, the chat's active location and background illustration automatically restore to the venue that was active at that point in time (or back to the initial starting location if all subsequent transitions are removed).
  - Each system notice features a trash icon (`🗑️`) allowing players to rewind the adventure from that transition onward.
- **Re-Generating Replies:** Using the Re-Generate button to rewrite an AI reply replaces only the character's answer; any location transition and system notices remain preserved in the chat.

---

## ⚡ Random Events & System Notifications

- **Unified Event Pool:** Eligible random events are drawn from a single combined pool containing global world events, location-specific world events for the current venue, character-specific events (which also work when chatting without an active WorldInfo), and character events additionally restricted to the current location. Character-specific events can also be restricted to a relationship tier range and only enter the active pool while the session's current relationship tier falls within that range.
- **Persistent Event Notices in Chat:** When a random event triggers, it is saved directly into the chat history as a persistent system message with a bolt badge (*"⚡ Ereignis: [Event-Titel]"*) and its narrative description. The notification appears right before the AI character's response, and the character weaves the event into their dialogue.
- **Rewinding & Cascading Deletions:** Each event message features a trash icon (`🗑️`). Clicking it deletes the chat history from that point forward and returns any consumed one-shot events back to the active pool.
- **Live Event Cooldown Indicator (Admins, World & Character Creators/Collaborators):** In the right chat sidebar below the World and Location selectors, administrators as well as authors and collaborators of the active world or active character see a live countdown indicator showing the exact number of messages remaining until the next event (*"⏳ Nächstes Event: in X Nachrichten"* or *"nächste Nachricht"*). When events are paused via the toggle in the **Settings** tab, the indicator preserves the current count and displays *(pausiert)*.

---

## 🎨 Multimodal Features & Input Bar

- **Persistent AI System Notice:** Directly attached to the top of the chat input box, a small persistent notice reminds you that you are conversing with an AI chatbot: *"Dies ist ein KI-Chatbot. Antworten werden automatisiert durch lokale oder externe Sprachmodelle generiert und können unvollständig oder fehlerhaft sein."*
- **Paperclip Icon (Image Upload):** Attach any image to your message. A Vision model generates a concise ALT description in the background, providing the AI with situational awareness of what you showed it.
- **Magic Wand with Sparkles ✨ (Scene Image Generation):**
  - Generates a 16:9 scene illustration via the configured image backend (Google AI Image or ComfyUI) based on the current narrative context and character/location reference images.
  - During generation, a centered status indicator displays *"Generating image..."* and user input is locked.
  - A **Cancel Button** allows you to abort generation at any time and immediately unlocks input.
  - The generated image renders directly in chat and archives under the *"Media"* tab.

---

## 💔 Relationship Dynamics & Memories

- **Qualitative Relationship Status:** The relationship between the player and character dynamically evolves across 21 stages (from *-100: Pure Hatred* through *0: Neutral* up to *+100: Blind Devotion*).
- **Behavioral Evolution:** Every 10 points, the character's internal emotional stance and narrative behavior change perceptibly:
  - **Negative Tiers (-100 to -10):** From cold indifference and guarded distrust up to bitter hostility and visceral hatred. The character acts distant, sarcastic, uncooperative, or overtly hostile.
  - **Neutral (0):** Treats the player like a stranger with standard polite social distance without emotional investment.
  - **Positive Tiers (+10 to +100):** Evolves through polite courtesy, friendly warmth, deep affection, loyalty, and intimate devotion up to unconditional surrender.
- **Pure Roleplay Immersion:** In the user interface, players see exclusively the qualitative relationship status title (e.g., *Neutral*, *Friendly*, *Affection*) when hovering over the character's name bar beneath the portrait, or in the **Media** gallery header. No raw numbers break immersion.
- **Affection Dynamics:** The relationship evolves dynamically based on how each interaction impacts the character—meaningful kindness, humor, or emotional support builds trust faster, while rudeness, dishonesty, or hostility lowers affection. When a positive or negative shift occurs, the character's name bar beneath the portrait briefly glows green or red as subtle visual feedback. Extended inactivity gently decays the score over time. Character authors and administrators also see a **Relationship Settings** section inside the **Settings** tab (`⚙️`) in the chat window to toggle per-message relationship debug labels and—for administrators—reset and recalculate the relationship from the chat history (`🔄`).
- **Unlockable Artwork:** Once the relationship reaches the required relationship tier set on a 9:16 character image, it automatically unlocks in the *"Media"* tab.
- **Memories (Every 10 Messages):** Every 10 messages, a background LLM summarizes recent events and refreshes the chat session title in the sidebar.
- **Situational Context & Character Consistency:**
  - **Canon Origin & Organic Development:** Characters strictly preserve their pre-chat backstory, origins, and personal history while allowing their feelings, trust, and boundaries to evolve naturally through shared experiences in the conversation.
  - **Automatic Scene Focus:** The chat automatically adapts its attention depending on what you are talking about—focusing on personal biography and emotional depth during intimate conversations, on surroundings and atmosphere during exploration, or on world lore when discussing factions and history.
- **Three-Dot Menu (`...`):**
  - **Delete Message:** Deletes the selected message along with all subsequent messages and cascaded memories.
  - **Fork Chat:** Clones the conversation from this exact point forward into a branching timeline.
  - **Read Aloud:** Synthesizes and plays back the message via Voice AI.
  - **Inspect Prompt (Administrators):** Displays the full context sent to the AI for that turn, including a summary of the detected scene focus and context utilization.

---

## 📡 Connection Status & Notifications

While you chat, floating notification banderoles in the bottom-right corner keep you informed about system status without disrupting your roleplay:
- **Connection Issues:** If the connection to the application server is lost, a red-striped banderole informs you (*„Verbindung zum Backend verloren“*).
- **AI Service Issues:** If the active AI text backend is unreachable, misconfigured, or paused, a red-striped banderole alerts you with a specific connection or credential message.
- **Timeouts:** If a reply takes unusually long, a yellow-striped warning banderole indicates a timeout.
- **Replies from Other Chats:** When another character finishes generating a response while you are looking at a different chat, a notification banderole slides in with their portrait and a *„Zum Chat →“* button to switch over immediately.

Continue to: [**Administration & Settings →**](admin.md)
