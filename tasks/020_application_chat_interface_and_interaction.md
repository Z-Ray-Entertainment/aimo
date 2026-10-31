# Task 020: Chat Interface, SSE Streaming, Countdown & ComfyUI

## 🎯 Goal & Scope
Implementation of the comprehensive chat interface: Left multi-chat sidebar, 3-tab container (Chat, Media, Memories), SSE live streaming with translation swap, interactive text adventure location transition with 60s countdown, paperclip image upload (Vision ALT), and ComfyUI image generation with locked inputs and cancel button.

## 📂 Affected Layer & Files
- **Layer:** `application/chat/`, `templates/chat/`
- **Files:**
  - `application/chat/views.py`
  - `application/chat/forms.py`
  - `templates/chat/session.html`
  - `templates/chat/select_worldinfo.html`

## 🔗 Dependencies
- `tasks/012_domain_chat_sessions_messages_and_prompt_builder.md`
- `tasks/014_application_api_headless_core_rest_endpoints.md`
- `tasks/015_ui_theme_static_assets_and_base_template.md`

## 📝 Functional Specifications & Requirements

### 1. Initial Launch & Welcome Message ("First Chat")
- When opened without an active chat: Automatically creates session and displays character's `first_message` at initial location.
- **Initial Selection Dialogs:**
  - If user owns > 1 persona: Modal dialog to choose persona for this chat. (If user owns 1 persona: automatically assigned).
  - WorldInfo selection: Dropdown with "Without WorldInfo" option (character recommendation pre-selected).
- **Persona Lock:** Irrevocably fixed following the first user message.
- **WorldInfo Change:** Edit pencil icon in right info box with warning (*"Switching WorldInfo may introduce inconsistencies in earlier memories"*).

### 2. Layout & Three-Tab Navigation
- **Left Sidebar (Multi-Chat):** List of all user sessions and forks with this character with dynamic titles (updated via memories).
- **Three-Tab Container:**
  - **Tab 1: Chat:** Message bubble history (AI on left with portrait/sprite, player on right with persona avatar).
  - **Tab 2: Media:** Unlocked 9:16 images, image uploads, and ComfyUI generations.
  - **Tab 3: Memories:** Overview and manual edit view for all system memories.

### 3. Live Streaming, Location Changes & ComfyUI
- **Streaming:**
  - On submit: Displays *"Thinking..."*.
  - Raw English token stream displayed in real time, dimmed in gray and smaller text.
  - On completion: Spinner next to bubble, seamless replacement by German localized translation.
- **Location Change Prompt:**
  - Downstream model scan displays confirmation dialog (*"Move to [Location]? [Yes] [No]"*).
  - Red countdown bar (60 seconds); dissolves if ignored.
  - On "Yes": Switches location and 16:9 background; posts centered system notification (*"You travelled to {location}"*), which is **never** injected into the LLM context.
- **ComfyUI Image Generation (Magic Wand ✨):**
  - Displays centered notification: *"Generating image..."*.
  - **User text input textarea is locked**.
  - **Cancel Button** allows early termination and unlocks input immediately.
- **Paperclip Button (Image Upload):** Vision model generates ALT text; only this description enters the LLM prompt.
- **Right Info Box:** Affection bar (-100 to +100 with dynamic hearts), WorldInfo, Persona, "Enable/disable events" checkbox.

## ✅ Acceptance Criteria
- [x] Welcome message loads immediately on first chat session creation.
- [x] SSE streaming with dimmed preview text and translation swap functions smoothly.
- [x] 60s countdown bar for location changes operates reliably.
- [x] Image generation locks text inputs and provides a functioning cancel button.
- [x] System notices ("You travelled to...") never enter the LLM prompt.
