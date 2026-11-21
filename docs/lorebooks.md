# 📚 Lorebooks & Encyclopedias

[← Back to Overview](README.md) | [← AI Characters](characters.md) | [Worlds, Places & Events →](worldinfo.md)

**Lorebooks** serve as thematic encyclopedias. They allow creators to provide rich background knowledge regarding factions, magic systems, historical events, or technology — without cluttering the LLM's context window with unnecessary data.

---

## 🏗️ Structure & Vertical Sidebar Navigation

The Lorebook editor is organized into a clean two-column layout with a vertical sidebar on the left and the main editing stage on the right:
- **Left Sidebar Navigation:**
  - **Sidebar Header:** Displays the lorebook name and book icon (`📖`).
  - **Vertical Navigation Menu:**
    1. **📋 Basic Settings:** Title, visibility, and compendium overview description.
    2. **📜 Entries:** Square card grid of all knowledge entries (displays total count). When creating a new lorebook, this tab remains locked until basic settings are saved once.
    3. **👥 Collaboration:** Co-creator access management. Also locked until basic settings are saved once.
  - **Sidebar Footer:** Quick return button to jump back directly to the lorebook library or creations grid.
- **Right Main Stage:**
  - **Header Bar:** Shows the lorebook title, read-only status (for non-editable lorebooks), and action buttons:
    - **Save (`💾`):** Single save action for the lorebook settings and collaborator tags.
    - **Copy (`📄`):** Allows any creator to clone any visible lorebook and its complete entries into their own private collection.
    - **Delete (`🗑️`):** Strictly reserved for the author and all administrators, protected by a confirmation dialog.

---

## 📋 1. Basic Settings (`📋 Grundeinstellungen`)
- **Lorebook Name:** The title of this compendium (e.g., *"History of Eldoria"*, *"Magic & Arcane Spells"*).
- **Visibility (Top Right):** Compact eye icon toggle button at the top right of the settings page (hovering displays the current state):
  - **Closed eye (`Private`):** Visible only to you and designated collaborators.
  - **Open eye (`Public`):** Available in the library for other users to explore and reference in their characters.
- **Short Description:** A concise summary of the lorebook's theme for orientation in the library catalog.

---

## 📜 2. Entries
- **Tile Overview:**
  - **First Tile (`+`):** Opens a modal to author a new lorebook entry.
  - **Entry Tiles:** Display entry title and privacy badge (`🔒`) in a uniform square card layout; hovering reveals the full prose text overlay. Clicking a tile opens the editor modal.
- **Entry Editor (Modal Dialog):**
  - **Title:** E.g., *"The Order of Shadow Mages"*.
  - **Visibility (Top Right):** Eye icon toggle button at the top right of the dialog switching between **Public** (open eye, readable in library) and **Private** (closed eye, secret lore / spoiler protection). Hovering displays the active visibility mode.
  - **Tags (Keywords):** Comma-separated list of keywords for Vectorless Tag-RAG.
  - **AI Tag Suggestion (`✨`):** Automatically infers relevant keywords from title and content.
  - **Prose Content:** The factual knowledge text injected into the LLM context when triggered.
  - **Delete (`🗑️`):** Removes the entry after confirmation via the confirmation dialog.

---

## 👥 3. Collaboration (`👥 Kollaboration`)
- **Collaborator Management:** Authors can add or remove trusted creators using their private **Creator-Tag** (UUID4).
- **Permissions:** Collaborators listed in the table receive edit access to lorebook settings and entries, while deletion and collaborator management remain protected and author-only.
- **Collaborator View:** Collaborators see their active membership in a read-only table without the ability to add third parties.

---

## 🔒 Privacy & Creator Knowledge Protection (`🔒 Ersteller-Wissen`)

Creators can set a Lorebook to **Private** (`is_public = False`):
- **Hidden in Hub:** A private lorebook does not appear in the public hub catalog or entry searches for other users.
- **Context Injection without Leaking:** When a private lorebook is attached to a public character or world, its entries are still securely injected into active roleplay sessions when triggered by matching tags.
- **Spoiler Prevention:** Other players can roleplay with the character while the lorebook entries remain hidden from view in the lorebook explorer (`🔒 Ersteller-Wissen` badge), allowing creators to craft hidden lore, surprise plot points, and secret backstories.

---

## 🔗 Where Lorebooks Are Connected

Lorebooks can be connected at three distinct levels:
1. **Character Lorebooks:** Linked in the Character Designer under the *Lorebooks* tab. Creators can optionally restrict a lorebook to trigger only when a specific world is active (`lorebook_world_conditions`).
2. **WorldInfo Lorebooks:** Linked in the WorldInfo Editor. Automatically applies to any conversation set within that world.
3. **Custom Session Lorebooks:** Added directly by the user inside a chat session or during the *New Chat* configuration.

---

## 🔍 How Knowledge is Injected into Chat (Vectorless Tag-RAG)

AImo utilizes **strict rule-based tag matching** without external vector databases:
- If words mentioned in the ongoing dialogue match any tags in an active lorebook entry, that entry is automatically loaded into the AI's context for the next response.
- **Smart Relevance Prioritization:** Entries matching words from your latest message or fitting the current conversation topic (such as character-linked lorebooks during personal conversations or world lorebooks during exploration) are prioritized. When many entries match at once, the top entries are included in full detail while secondary matches are provided as concise key-fact summaries.
- If a topic is not mentioned, the entry remains dormant. This keeps the AI's working memory lean and focused.
- Only entries from **currently active** lorebooks (not disabled by the user and meeting all world conditions) are evaluated.

Continue to: [**Worlds, Places & Events (WorldInfo) →**](worldinfo.md)
