# 📚 Lorebooks & Encyclopedias

[← Back to Overview](README.md) | [← AI Characters](characters.md) | [Worlds, Places & Events →](worldinfo.md)

**Lorebooks** serve as thematic encyclopedias. They allow creators to provide rich background knowledge regarding factions, magic systems, historical events, or technology — without cluttering the LLM's context window with unnecessary data.

---

## 🏗️ Structure of a Lorebook

1. **Lorebook Name:** E.g., *"History of Eldoria"*, *"Magic & Arcane Spells"*.
2. **Tile Overview of Entries:**
   - **First Tile:** A placeholder tile with a plus icon (`+`) to add new entries.
   - All following tiles display the entry's title, linked tags, and a short snippet preview.

---

## 📝 Composing an Entry (Modal Dialog)

Clicking an entry tile opens an overlay modal:
- **Title:** E.g., *"The Order of Shadow Mages"*.
- **Tags (Keywords):** Comma-separated list of keywords (e.g., `magic, order, shadow, wizard`).
- **Description / Prose:** In-depth explanation, background facts, and context.

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
