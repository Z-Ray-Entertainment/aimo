from dataclasses import dataclass

from domain.characters.models import Character
from domain.chat.focus_analyzer import PythonFocusAnalyzer, SceneFocus
from domain.chat.models import Message, MessageRole
from domain.chat.prompt_sections import (
    format_character_definition,
    format_dialogue_examples,
    format_knowledge_pool,
    format_relation_section,
    format_single_message,
    format_user_persona,
    format_world_info,
)
from domain.chat.relationship import RelationshipTier
from domain.lorebooks.models import LorebookEntry
from domain.memories.models import Memory
from domain.personas.models import UserPersona
from domain.worldinfo.models import Event, Location, WorldInfo
from shared.i18n import gettext_noop as _, t
from shared.utils import estimate_tokens, replace_roleplay_placeholders


@dataclass
class PromptBudgetReport:
    scene_focus: SceneFocus
    effective_num_ctx: int
    max_prompt_tokens: int
    generation_headroom: int
    estimated_total_tokens: int
    history_strategy: str
    knowledge_pool_tokens: int
    knowledge_pool_budget: int
    memories_count: int
    lorebooks_full_count: int
    lorebooks_distilled_count: int
    worldinfo_mode: str
    active_examples_count: int

    def format_header(self) -> str:
        pct = (
            round((self.estimated_total_tokens / self.max_prompt_tokens) * 100, 1)
            if self.max_prompt_tokens > 0
            else 0.0
        )
        return (
            "=== AIMO PROMPT BUDGET MONITOR ===\n"
            f"Detected Scene Focus : {self.scene_focus.value.upper()}\n"
            f"Context Window       : {self.effective_num_ctx} Tokens "
            f"(Max Prompt: {self.max_prompt_tokens} | Output Reserve: {self.generation_headroom})\n"
            f"Estimated Prompt Size: {self.estimated_total_tokens} / {self.max_prompt_tokens} Tokens ({pct}%)\n"
            f"Chat History Strategy: {self.history_strategy}\n"
            f"Knowledge Pool       : {self.knowledge_pool_tokens} / {self.knowledge_pool_budget} Tokens "
            f"(Memories: {self.memories_count}, Lorebooks: {self.lorebooks_full_count} full + {self.lorebooks_distilled_count} distilled)\n"
            f"WorldInfo Mode       : {self.worldinfo_mode}\n"
            f"Dialogue Examples    : {self.active_examples_count} active\n"
            "=================================="
        )


def _wrap_section(tag: str, body: str) -> str:
    return f"[{tag}]\n{body}\n[/{tag}]"


class PromptBuilder:
    def __init__(self) -> None:
        self.last_budget_report: PromptBudgetReport | None = None

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
        scene_focus: SceneFocus | None = None,
        effective_num_ctx: int = 4096,
        thinking_enabled: bool = False,
        active_tags: list[str] | None = None,
        language: str = "en",
    ) -> str:
        ctx_size = max(2048, int(effective_num_ctx or 4096))
        generation_headroom = (
            max(1150, min(1800, int(ctx_size * 0.25)))
            if thinking_enabled
            else max(768, min(1500, int(ctx_size * 0.18)))
        )
        max_prompt_tokens = max(1500, ctx_size - generation_headroom)
        knowledge_pool_budget = max(400, min(1200, int(max_prompt_tokens * 0.15)))

        if scene_focus is None:
            scene_focus = PythonFocusAnalyzer().analyze(
                recent_messages=recent_messages,
                active_tags=active_tags,
                has_triggered_event=(triggered_event is not None),
            )

        system_section = roleplay_system_prompt.strip()
        character_section = format_character_definition(character, False, language)
        persona_section = format_user_persona(persona, language)
        relation_section = format_relation_section(
            relationship_value,
            translations=relation_translations,
            scene_focus=scene_focus,
            character_name=character.name,
            language=language,
        )

        compact_world = (
            scene_focus == SceneFocus.INTIMACY_BIO
            and triggered_event is None
            and ctx_size <= 6144
        )
        world_section = format_world_info(
            worldinfo,
            current_location,
            triggered_event,
            available_locations or [],
            character,
            compact_mode=compact_world,
            language=language,
        )
        worldinfo_mode = "Compact (Intimacy Focus)" if compact_world else "Full Detail"

        memories_section, lorebooks_section, mem_count, lb_full_count, lb_dist_count, pool_tokens = (
            format_knowledge_pool(
                matched_memories,
                matched_lorebooks,
                pool_budget_tokens=knowledge_pool_budget,
                scene_focus=scene_focus,
                language=language,
            )
        )

        narrative_messages = [
            msg for msg in recent_messages if msg.role in (MessageRole.USER, MessageRole.CHARACTER)
        ][-10:]

        examples_section, active_examples_count = format_dialogue_examples(
            character.dialogue_examples,
            narrative_msg_count=len(narrative_messages),
            scene_focus=scene_focus,
            active_tags=active_tags,
            language=language,
        )

        system_block = _wrap_section("SYSTEM_PROMPT", system_section) if system_section else ""
        char_block = _wrap_section("CHARACTER_DEFINITION", character_section)
        mem_block = _wrap_section("RELEVANT_MEMORIES", memories_section)
        lore_block = _wrap_section("RELEVANT_LOREBOOKS", lorebooks_section)
        world_block = _wrap_section("WORLD_INFO", world_section)
        persona_block = _wrap_section("USER_PERSONA", persona_section)
        relation_block = _wrap_section("RELATION", relation_section)

        fixed_text = "\n\n".join(
            b for b in (system_block, char_block, mem_block, lore_block, world_block, persona_block, relation_block) if b
        )
        fixed_tokens = estimate_tokens(fixed_text)
        examples_block = _wrap_section("DIALOGUE_EXAMPLES", examples_section)
        examples_tokens = estimate_tokens(examples_block)

        if len(narrative_messages) >= 4 and (fixed_tokens + examples_tokens) > (max_prompt_tokens - 600):
            examples_section = t(_("None."), language)
            active_examples_count = 0
            examples_block = _wrap_section("DIALOGUE_EXAMPLES", examples_section)
            examples_tokens = estimate_tokens(examples_block)

        available_history_tokens = max(350, max_prompt_tokens - fixed_tokens - examples_tokens)
        history_section, history_strategy = self._format_adaptive_chat_history(
            narrative_messages=narrative_messages,
            character_name=character.name,
            persona_name=persona.name,
            history_budget_tokens=available_history_tokens,
            effective_num_ctx=ctx_size,
            language=language,
        )
        history_block = _wrap_section("CHAT_HISTORY", history_section)

        parts = [
            b
            for b in (
                system_block,
                char_block,
                history_block,
                mem_block,
                lore_block,
                world_block,
                persona_block,
                relation_block,
                examples_block,
            )
            if b
        ]
        assembled = "\n\n".join(parts)

        if estimate_tokens(assembled) > max_prompt_tokens and scene_focus == SceneFocus.WORLD_EXPLORATION:
            condensed_char = format_character_definition(character, True, language)
            parts[1 if system_block else 0] = _wrap_section("CHARACTER_DEFINITION", condensed_char)
            assembled = "\n\n".join(parts)

        final_prompt = replace_roleplay_placeholders(
            assembled,
            character.name,
            persona.name,
            character_gender=character.gender.value,
            persona_gender=persona.gender.value,
        )

        self.last_budget_report = PromptBudgetReport(
            scene_focus=scene_focus,
            effective_num_ctx=ctx_size,
            max_prompt_tokens=max_prompt_tokens,
            generation_headroom=generation_headroom,
            estimated_total_tokens=estimate_tokens(final_prompt),
            history_strategy=history_strategy,
            knowledge_pool_tokens=pool_tokens,
            knowledge_pool_budget=knowledge_pool_budget,
            memories_count=mem_count,
            lorebooks_full_count=lb_full_count,
            lorebooks_distilled_count=lb_dist_count,
            worldinfo_mode=worldinfo_mode,
            active_examples_count=active_examples_count,
        )
        return final_prompt

    @staticmethod
    def _format_adaptive_chat_history(
        narrative_messages: list[Message],
        character_name: str,
        persona_name: str,
        history_budget_tokens: int,
        effective_num_ctx: int = 4096,
        language: str = "en",
    ) -> tuple[str, str]:
        if not narrative_messages:
            return t(_("No messages yet."), language), "Empty (0 messages)"

        def _format_and_fit(msgs: list[Message], distilled_flags: list[bool] | None = None) -> tuple[str, int] | None:
            flags = distilled_flags or [False] * len(msgs)
            lines = [
                format_single_message(m, character_name, persona_name, distill=flags[idx], language=language)
                for idx, m in enumerate(msgs)
            ]
            lines = [line for line in lines if line]
            text = "\n".join(lines)
            if estimate_tokens(text) <= history_budget_tokens:
                return text, len(lines)
            return None

        fitted = _format_and_fit(narrative_messages)
        if fitted is not None:
            return fitted[0], f"{fitted[1]} messages (100% verbatim)"

        window_size = 6 if effective_num_ctx <= 6144 else min(8, len(narrative_messages))
        window_msgs = narrative_messages[-window_size:]
        fitted = _format_and_fit(window_msgs)
        if fitted is not None:
            return fitted[0], f"{fitted[1]} messages (windowed verbatim)"

        distilled_flags = [False] * len(window_msgs)
        zone2_limit = max(0, len(window_msgs) - 2)
        for idx in range(zone2_limit):
            distilled_flags[idx] = True
            fitted = _format_and_fit(window_msgs, distilled_flags)
            if fitted is not None:
                dist_n = idx + 1
                return (
                    fitted[0],
                    f"{fitted[1]} messages ({dist_n} distilled in Zone 2, {fitted[1] - dist_n} verbatim)",
                )

        while len(window_msgs) > 2:
            window_msgs = window_msgs[1:]
            distilled_flags = distilled_flags[1:]
            fitted = _format_and_fit(window_msgs, distilled_flags)
            if fitted is not None:
                dist_n = sum(1 for f in distilled_flags if f)
                return (
                    fitted[0],
                    f"{fitted[1]} messages ({dist_n} distilled, {fitted[1] - dist_n} verbatim)",
                )

        final_lines = [
            format_single_message(m, character_name, persona_name, distill=False, language=language)
            for m in window_msgs[-2:]
        ]
        final_lines = [line for line in final_lines if line]
        return "\n".join(final_lines) if final_lines else t(_("No messages yet."), language), f"{len(final_lines)} messages (minimum acute window)"
