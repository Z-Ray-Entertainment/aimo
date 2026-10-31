# 💬 The Chat & Roleplay Interface

[← Back to Overview](README.md) | [← Worlds & Places](worldinfo.md) | [Administration & Settings →](admin.md)

The chat screen is the centerpiece of aimo. Here, the interactive text adventure unfolds with live token streaming, emotional sprites, dynamic location transitions, and generative imagery.

---

## 🚀 Starting a Chat ("First Chat")

When you open a character for the first time:
1. **Persona Selection:** If you have more than one persona, a quick dialog prompts you to choose who you want to play. (Once the first user message is sent, your persona is locked for that session).
2. **WorldInfo Selection:** Select your setting (the character's recommendation is pre-selected). You can also explicitly choose *"Without WorldInfo"* (applies neutral backgrounds and no events).
3. **Welcome Message:** The character immediately greets you with their opening message at the designated starting location.

---

## 🖥️ Screen Layout

- **Header:** Back button (`←`) to the main overview.
- **Left Sidebar (Multi-Chat):** Lists all your chat sessions and forks with this character. Titles update dynamically based on key events.
- **Central Three-Tab Container:**
  - **Tab 1: Chat:** The ongoing dialogue in message bubbles (AI on the left with portrait/sprite, player on the right).
  - **Tab 2: Media:** Aggregates all unlocked 9:16 gallery images, uploaded photos, and generated images.
  - **Tab 3: Memories:** Lists all system-generated memory summaries and allows manual edits.
- **Right Info Box:**
  - Character portrait / transparent emotion sprite.
  - Dynamic relationship bar (-100 to +100 with heart icon).
  - Active WorldInfo with edit pencil.
  - Player persona badge.
  - Actions: Events toggle (checkbox), New Chat, Delete Chat.

---

## ⚡ Live Streaming & Seamless Localization

Because modern LLMs write with the greatest depth and nuance in English while the UI operates in your localized language, aimo employs a two-stage streaming workflow:
1. **Live Stream (English):** When submitted, a *"Thinking..."* state appears. The raw English token stream streams into the message bubble in real time — **dimmed in gray and rendered in smaller text** so you can follow the generation progress.
2. **Translation Swap:** The instant generation finishes, a brief spinner appears and the dimmed English text is cleanly replaced by the **final translated text** in standard font size.

---

## 🧭 Interactive Location Transitions (Text Adventure)

When the AI narrative suggests travelling to a new location (e.g., *"Let us set out into the forest"*):
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

Continue to: [**Administration & Settings →**](admin.md)
