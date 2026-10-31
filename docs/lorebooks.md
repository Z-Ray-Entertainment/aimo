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

## 🔍 How Knowledge is Injected into Chat (Tag-RAG)

aimo utilizes **strict rule-based tag matching**:
- If words mentioned in the ongoing dialogue match any tags in an active lorebook entry (`tags_overlap >= 1`), that entry is automatically injected into the prompt context for the next AI generation.
- If the topic is not mentioned, the entry remains dormant. This keeps the LLM's working memory lean and focused.

Continue to: [**Worlds, Places & Events (WorldInfo) →**](worldinfo.md)
