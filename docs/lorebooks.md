# 📚 Lorebooks & Encyclopedias

[← Back to Overview](README.md) | [← AI Characters](characters.md) | [Worlds, Places & Events →](worldinfo.md)

**Lorebooks** serve as thematic encyclopedias. They allow creators to provide rich background knowledge regarding factions, magic systems, historical events, or technology — without cluttering the LLM's context window with unnecessary data.

---

## 🛠️ Header & Actions

- **Back Button (`←`):** Returns to the hub overview.
- **Lorebook Title & Badges:** Displays the name of the lorebook and a readonly badge (`🔒 Schreibgeschützt`) if viewing another user's lorebook without edit permissions.
- **Save (`💾 Speichern`):** Saves all basic settings and collaborator tags.
- **Duplicate (`📄 Duplizieren`):** Allows any creator to clone any visible lorebook and its complete entries into their own private collection.
- **Delete (`🗑️ Lorebook löschen`):** Strictly reserved for the author and initial administrators.

---

## 🏗️ Structure & Tabs of the Lorebook Editor

The Lorebook editor is organized into three specialized tabs:

### 1. Tab 1: Basic Settings (`📋 Grundeinstellungen`)
- **Lorebook Name:** The title of this compendium (e.g., *"History of Eldoria"*, *"Magic & Arcane Spells"*).
- **Visibility:**
  - `Private`: Visible only to you and designated collaborators.
  - `Public`: Available in the library for other users to explore and reference in their characters.
- **Short Description:** A concise summary of the lorebook's theme for orientation in the library catalog.

### 2. Tab 2: Entries (`📜 Einträge`)
- **Tile Overview:**
  - **First Tile (`+`):** Opens a modal to author a new lorebook entry.
  - **Entry Tiles:** Display entry title, linked tags, and a short snippet preview. Clicking a tile opens the editor modal.
- **Entry Editor (Modal Dialog):**
  - **Title:** E.g., *"The Order of Shadow Mages"*.
  - **Visibility:** `🌍 Public` (readable in library) or `🔒 Private` (secret lore / spoiler protection).
  - **Tags (Keywords):** Comma-separated list of keywords for Vectorless Tag-RAG.
  - **AI Tag Suggestion (`✨ Tags vorschlagen`):** Automatically infers relevant keywords from title and content.
  - **Prose Content:** The factual knowledge text injected into the LLM context when triggered.

### 3. Tab 3: Collaboration (`👥 Kollaboration`)
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

aimo utilizes **strict rule-based tag matching** without external vector databases:
- If words mentioned in the ongoing dialogue match any tags in an active lorebook entry (`tags_overlap >= 1`), that entry is automatically injected into the `[RELEVANT_LOREBOOKS]` stage of the prompt context for the next AI generation.
- If the topic is not mentioned, the entry remains dormant. This keeps the LLM's working memory lean and focused.
- Only entries from **currently active** lorebooks (not disabled by the user and meeting all world conditions) are evaluated.

Continue to: [**Worlds, Places & Events (WorldInfo) →**](worldinfo.md)
