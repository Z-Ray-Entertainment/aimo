from domain.characters.models import Character
from domain.chat.models import Message, MessageRole
from domain.chat.relationship import (
    RelationshipTier,
    format_relationship_prompt,
    get_relationship_tier,
)
from domain.lorebooks.models import LorebookEntry
from domain.memories.models import Memory
from domain.personas.models import UserPersona
from domain.worldinfo.models import Event, Location, WorldInfo
from shared.utils import get_gender_forms, replace_roleplay_placeholders


class PromptBuilder:
    def build_roleplay_prompt(
        self,
        roleplay_system_prompt: str,
        character: Character,
        persona: UserPersona,
        worldinfo: WorldInfo | None,
        current_location: Location | None,
        triggered_event: Event | None,
        recent_messages: list[Message],
        matched_memories: list[Memory],
        matched_lorebooks: list[LorebookEntry],
        available_locations: list[Location] | None = None,
        relationship_value: float = 0.0,
        relation_translations: dict[int, RelationshipTier] | None = None,
    ) -> str:
        system_section = roleplay_system_prompt.strip()
        character_section = self._format_character_definition(
            character=character,
        )
        history_section = self._format_chat_history(
            messages=recent_messages,
            character_name=character.name,
            persona_name=persona.name,
        )
        memories_section = self._format_memories(memories=matched_memories)
        lorebooks_section = self._format_lorebooks(entries=matched_lorebooks)
        world_section = self._format_world_info(
            worldinfo=worldinfo,
            current_location=current_location,
            triggered_event=triggered_event,
            available_locations=available_locations or [],
            character=character,
        )
        persona_section = self._format_user_persona(persona=persona)
        relation_section = self._format_relation_section(
            relationship_value=relationship_value,
            translations=relation_translations,
        )
        dialogue_examples_section = self._format_dialogue_examples(
            dialogue_examples=character.dialogue_examples,
        )

        parts: list[str] = []
        if system_section:
            parts.append(f"[SYSTEM_PROMPT]\n{system_section}\n[/SYSTEM_PROMPT]")
        parts.extend([
            f"[CHARACTER_DEFINITION]\n{character_section}\n[/CHARACTER_DEFINITION]",
            f"[CHAT_HISTORY]\n{history_section}\n[/CHAT_HISTORY]",
            f"[RELEVANT_MEMORIES]\n{memories_section}\n[/RELEVANT_MEMORIES]",
            f"[RELEVANT_LOREBOOKS]\n{lorebooks_section}\n[/RELEVANT_LOREBOOKS]",
            f"[WORLD_INFO]\n{world_section}\n[/WORLD_INFO]",
            f"[USER_PERSONA]\n{persona_section}\n[/USER_PERSONA]",
            f"[RELATION]\n{relation_section}\n[/RELATION]",
            f"[DIALOGUE_EXAMPLES]\n{dialogue_examples_section}\n[/DIALOGUE_EXAMPLES]",
        ])
        assembled = "\n\n".join(parts)
        return replace_roleplay_placeholders(
            assembled,
            character.name,
            persona.name,
            character_gender=character.gender.value,
            persona_gender=persona.gender.value,
        )

    @staticmethod
    def _format_character_definition(
        character: Character,
    ) -> str:
        c_forms = get_gender_forms(character.gender.value)
        desc_block = character.description.strip()
        if hasattr(character, "appearance") and character.appearance and character.appearance.strip():
            desc_block = f"{desc_block}\n\n{character.appearance.strip()}"

        lines = [
            f"Role: You play this character ({character.name}). Embody these traits and voice exclusively:",
            f"Name: {character.name}",
            f"Gender: {character.gender.value} ({c_forms['pronouns']})",
            f"Description & Personality:\n{desc_block}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _format_relation_section(
        relationship_value: float,
        translations: dict[int, RelationshipTier] | None = None,
    ) -> str:
        tier = get_relationship_tier(relationship_value, translations=translations)
        return format_relationship_prompt(tier)

    @staticmethod
    def _format_dialogue_examples(dialogue_examples: list | str) -> str:
        blocks: list[str] = []

        if isinstance(dialogue_examples, str):
            raw_text = dialogue_examples.strip()
            if not raw_text:
                return "None."
            return raw_text

        if isinstance(dialogue_examples, list):
            for item in dialogue_examples:
                if isinstance(item, dict):
                    t = str(item.get("trigger", "")).strip()
                    r = str(item.get("response", "")).strip()
                    if not t and not r:
                        continue
                    if not t.lower().startswith("{{user}}:"):
                        t = f"{{{{user}}}}: {t}" if t else "{{user}}:"
                    if not r.lower().startswith("{{char}}:"):
                        r = f"{{{{char}}}}: {r}" if r else "{{char}}:"
                    blocks.append(f"<START>\n{t}\n{r}")
                elif isinstance(item, str):
                    s = item.strip()
                    if not s:
                        continue
                    if "<START>" in s:
                        blocks.append(s)
                    else:
                        blocks.append(f"<START>\n{{{{user}}}}:\n{{{{char}}}}: {s}")

        return "\n\n".join(blocks) if blocks else "None."

    @staticmethod
    def _format_user_persona(persona: UserPersona) -> str:
        u_forms = get_gender_forms(persona.gender.value)
        lines = [
            f"Role: This is your conversation partner ({persona.name}). You are NOT this person. NEVER speak, act, think, or decide on behalf of {persona.name}:",
            f"Name: {persona.name}",
            f"Gender: {persona.gender.value} ({u_forms['pronouns']})",
        ]
        if persona.description.strip():
            lines.append(f"Background & Personality: {persona.description.strip()}")
        if persona.appearance.strip():
            lines.append(f"Physical Appearance: {persona.appearance.strip()}")
        return "\n".join(lines)

    @staticmethod
    def _format_world_info(
        worldinfo: WorldInfo | None,
        current_location: Location | None,
        triggered_event: Event | None,
        available_locations: list[Location],
        character: Character,
    ) -> str:
        if worldinfo is None:
            return "Active World: None (Neutral setting, no specific world events)."

        lines = [f"World Name: {worldinfo.name}"]
        if current_location is not None:
            lines.append(f"Current Location: {current_location.name}")
            if current_location.description.strip():
                lines.append(f"Location Description: {current_location.description.strip()}")
            if current_location.vision_alt_text:
                lines.append(f"Visual Environment: {current_location.vision_alt_text.strip()}")
        else:
            lines.append("Current Location: Unspecified")

        if available_locations:
            loc_map = {loc.id: loc.name for loc in available_locations if loc.id is not None}
            pref_names = [
                loc_map[lid]
                for lid in character.preferred_location_ids
                if lid in loc_map
            ]
            disliked_names = [
                loc_map[lid]
                for lid in character.disliked_location_ids
                if lid in loc_map
            ]
            if pref_names:
                lines.append(f"Character's Preferred Locations: {', '.join(pref_names)}")
            if disliked_names:
                lines.append(f"Character's Disliked Locations: {', '.join(disliked_names)}")

        if triggered_event is not None:
            lines.append(
                f"Active Narrative Event ({triggered_event.title}): "
                f"{triggered_event.description.strip()} "
                f"(Notice and organically weave this unfolding event into your immediate reaction and dialogue.)"
            )

        return "\n".join(lines)

    @staticmethod
    def _format_chat_history(
        messages: list[Message],
        character_name: str,
        persona_name: str,
    ) -> str:
        narrative_messages = [
            msg
            for msg in messages
            if msg.role in (MessageRole.USER, MessageRole.CHARACTER)
        ][-10:]

        if not narrative_messages:
            return "No messages yet."

        lines: list[str] = []
        for msg in narrative_messages:
            speaker = f"{persona_name} (Player)" if msg.role == MessageRole.USER else f"{character_name} (You)"
            content = msg.english_content.strip()
            if msg.image_alt_text and msg.image_alt_text.strip():
                alt = msg.image_alt_text.strip()
                if content:
                    content = f"[Player shows an image: {alt}] {content}"
                else:
                    content = f"[Player shows an image: {alt}]"
            if content:
                lines.append(f"{speaker}: {content}")

        return "\n".join(lines) if lines else "No messages yet."

    @staticmethod
    def _format_memories(memories: list[Memory]) -> str:
        if not memories:
            return "None."
        return "\n\n".join(
            f"- {mem.title}: {mem.summary.strip()}"
            for mem in memories
        )

    @staticmethod
    def _format_lorebooks(entries: list[LorebookEntry]) -> str:
        if not entries:
            return "None."
        return "\n\n".join(
            f"- {entry.title}: {entry.content.strip()}"
            for entry in entries
        )
