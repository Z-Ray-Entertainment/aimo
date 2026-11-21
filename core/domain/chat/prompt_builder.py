from dataclasses import dataclass
import re

from domain.characters.models import Character
from domain.chat.focus_analyzer import PythonFocusAnalyzer, SceneFocus
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
from shared.i18n import gettext_noop as _, t
from shared.utils import (
    distill_message_dialogue,
    estimate_tokens,
    extract_first_sentence,
    get_gender_forms,
    replace_roleplay_placeholders,
)


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
        if thinking_enabled:
            generation_headroom = max(1150, min(1800, int(ctx_size * 0.25)))
        else:
            generation_headroom = max(768, min(1500, int(ctx_size * 0.18)))

        max_prompt_tokens = max(1500, ctx_size - generation_headroom)
        knowledge_pool_budget = max(400, min(1200, int(max_prompt_tokens * 0.15)))

        analyzer = PythonFocusAnalyzer()
        if scene_focus is None:
            scene_focus = analyzer.analyze(
                recent_messages=recent_messages,
                active_tags=active_tags,
                has_triggered_event=(triggered_event is not None),
            )

        system_section = roleplay_system_prompt.strip()
        character_section = self._format_character_definition(
            character=character,
            condense_intimate_backstory=False,
            language=language,
        )
        persona_section = self._format_user_persona(persona=persona, language=language)
        relation_section = self._format_relation_section(
            relationship_value=relationship_value,
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
        world_section = self._format_world_info(
            worldinfo=worldinfo,
            current_location=current_location,
            triggered_event=triggered_event,
            available_locations=available_locations or [],
            character=character,
            compact_mode=compact_world,
            language=language,
        )
        worldinfo_mode = "Compact (Intimacy Focus)" if compact_world else "Full Detail"

        memories_section, lorebooks_section, mem_count, lb_full_count, lb_dist_count, pool_tokens = (
            self._format_knowledge_pool(
                memories=matched_memories,
                lorebooks=matched_lorebooks,
                pool_budget_tokens=knowledge_pool_budget,
                scene_focus=scene_focus,
            )
        )

        narrative_messages = [
            msg
            for msg in recent_messages
            if msg.role in (MessageRole.USER, MessageRole.CHARACTER)
        ][-10:]

        examples_section, active_examples_count = self._format_dialogue_examples(
            dialogue_examples=character.dialogue_examples,
            narrative_msg_count=len(narrative_messages),
            scene_focus=scene_focus,
            active_tags=active_tags,
        )

        fixed_text = "\n\n".join([
            f"[SYSTEM_PROMPT]\n{system_section}\n[/SYSTEM_PROMPT]" if system_section else "",
            f"[CHARACTER_DEFINITION]\n{character_section}\n[/CHARACTER_DEFINITION]",
            f"[RELEVANT_MEMORIES]\n{memories_section}\n[/RELEVANT_MEMORIES]",
            f"[RELEVANT_LOREBOOKS]\n{lorebooks_section}\n[/RELEVANT_LOREBOOKS]",
            f"[WORLD_INFO]\n{world_section}\n[/WORLD_INFO]",
            f"[USER_PERSONA]\n{persona_section}\n[/USER_PERSONA]",
            f"[RELATION]\n{relation_section}\n[/RELATION]",
        ]).strip()

        fixed_tokens = estimate_tokens(fixed_text)
        examples_tokens = estimate_tokens(f"[DIALOGUE_EXAMPLES]\n{examples_section}\n[/DIALOGUE_EXAMPLES]")

        if len(narrative_messages) >= 4 and (fixed_tokens + examples_tokens) > (max_prompt_tokens - 600):
            examples_section = t(_("None."), language)
            active_examples_count = 0
            examples_tokens = estimate_tokens(f"[DIALOGUE_EXAMPLES]\n{examples_section}\n[/DIALOGUE_EXAMPLES]")

        available_history_tokens = max(350, max_prompt_tokens - fixed_tokens - examples_tokens)

        history_section, history_strategy = self._format_adaptive_chat_history(
            narrative_messages=narrative_messages,
            character_name=character.name,
            persona_name=persona.name,
            history_budget_tokens=available_history_tokens,
            effective_num_ctx=ctx_size,
            language=language,
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
            f"[DIALOGUE_EXAMPLES]\n{examples_section}\n[/DIALOGUE_EXAMPLES]",
        ])
        assembled = "\n\n".join(parts)

        # Emergency safety net: if in WORLD_EXPLORATION and still over budget due to massive character description
        total_est = estimate_tokens(assembled)
        if total_est > max_prompt_tokens and scene_focus == SceneFocus.WORLD_EXPLORATION:
            condensed_char_section = self._format_character_definition(
                character=character,
                condense_intimate_backstory=True,
                language=language,
            )
            parts[1 if system_section else 0] = (
                f"[CHARACTER_DEFINITION]\n{condensed_char_section}\n[/CHARACTER_DEFINITION]"
            )
            assembled = "\n\n".join(parts)
            total_est = estimate_tokens(assembled)

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
    def _format_character_definition(
        character: Character,
        condense_intimate_backstory: bool = False,
        language: str = "en",
    ) -> str:
        c_forms = get_gender_forms(character.gender.value)
        desc_block = character.description.strip()

        if condense_intimate_backstory and len(desc_block) > 1500:
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", desc_block) if p.strip()]
            intimate_markers = {
                "virgin", "virginity", "demisexual", "demisexuality", "sexual",
                "jungfrau", "jungfräulich", "demisexuell", "intimität",
            }
            if len(paragraphs) > 2:
                filtered = [
                    p for idx, p in enumerate(paragraphs)
                    if idx == 0 or not (set(re.findall(r"[a-zA-ZäöüÄÖÜß]+", p.lower())) & intimate_markers)
                ]
                if filtered:
                    desc_block = "\n\n".join(filtered)

        if hasattr(character, "appearance") and character.appearance and character.appearance.strip():
            app_label = t(_("Physical Appearance:"), language)
            desc_block = f"{desc_block}\n\n{app_label}\n{character.appearance.strip()}"

        role_line = t(_("Role: You play this character ({name}). Embody these traits, canon backstory, and voice exclusively:"), language).format(name=character.name)
        name_label = t(_("Name:"), language)
        gender_label = t(_("Gender:"), language)
        desc_label = t(_("Description, Personality & Canon Backstory (All origin facts, personal history, and traits below are canon truth):"), language)
        lines = [
            role_line,
            f"{name_label} {character.name}",
            f"{gender_label} {character.gender.value} ({c_forms['pronouns']})",
            f"{desc_label}\n{desc_block}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _format_relation_section(
        relationship_value: float,
        translations: dict[int, RelationshipTier] | None = None,
        scene_focus: SceneFocus = SceneFocus.GENERAL_ROLEPLAY,
        character_name: str = "{{char}}",
        language: str = "en",
    ) -> str:
        tier = get_relationship_tier(relationship_value, translations=translations, language=language)
        base_rel = format_relationship_prompt(tier, language=language)
        directive = PythonFocusAnalyzer.get_focus_directive(scene_focus, character_name, language=language)
        if directive:
            return f"{base_rel}\n\n{directive}"
        return base_rel

    @classmethod
    def _parse_example_blocks(cls, dialogue_examples: list | str) -> list[str]:
        blocks: list[str] = []
        if isinstance(dialogue_examples, str):
            raw_text = dialogue_examples.strip()
            if not raw_text:
                return []
            if "<START>" in raw_text:
                parts = [p.strip() for p in raw_text.split("<START>") if p.strip()]
                return [f"<START>\n{p}" for p in parts]
            return [raw_text]

        if isinstance(dialogue_examples, list):
            # Reconstruct if list was accidentally split line-by-line from <START> blocks
            if any(isinstance(x, str) and x.strip() == "<START>" for x in dialogue_examples):
                joined = "\n".join(str(x).strip() for x in dialogue_examples if str(x).strip())
                parts = [p.strip() for p in joined.split("<START>") if p.strip()]
                return [f"<START>\n{p}" for p in parts]

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
        return blocks

    @classmethod
    def _format_dialogue_examples(
        cls,
        dialogue_examples: list | str,
        narrative_msg_count: int = 0,
        scene_focus: SceneFocus = SceneFocus.GENERAL_ROLEPLAY,
        active_tags: list[str] | None = None,
    ) -> tuple[str, int]:
        blocks = cls._parse_example_blocks(dialogue_examples)
        if not blocks:
            return "None.", 0

        if narrative_msg_count < 4:
            selected = blocks[:2]
            return "\n\n".join(selected), len(selected)

        focus_kw = PythonFocusAnalyzer.get_focus_keywords(scene_focus)
        tag_set = {t.strip().lower() for t in (active_tags or []) if t and t.strip()}
        search_terms = focus_kw | tag_set

        best_block = blocks[0]
        best_score = -1
        if search_terms:
            for blk in blocks:
                words = set(re.findall(r"[a-zA-ZäöüÄÖÜß]{3,}", blk.lower()))
                score = len(words & search_terms)
                if score > best_score:
                    best_score = score
                    best_block = blk

        return best_block, 1

    @staticmethod
    def _format_user_persona(persona: UserPersona, language: str = "en") -> str:
        u_forms = get_gender_forms(persona.gender.value)
        role_line = t(
            _("Role: This is your conversation partner ({name}). You are NOT this person. NEVER speak, act, think, or decide on behalf of {name}:"),
            language,
        ).format(name=persona.name)
        name_label = t(_("Name:"), language)
        gender_label = t(_("Gender:"), language)
        lines = [
            role_line,
            f"{name_label} {persona.name}",
            f"{gender_label} {persona.gender.value} ({u_forms['pronouns']})",
        ]
        if persona.description.strip():
            desc = persona.description.strip()[:1200]
            bg_label = t(_("Background & Personality:"), language)
            lines.append(f"{bg_label} {desc}")
        if persona.appearance.strip():
            app_label = t(_("Physical Appearance:"), language)
            lines.append(f"{app_label} {persona.appearance.strip()}")
        return "\n".join(lines)

    @staticmethod
    def _format_world_info(
        worldinfo: WorldInfo | None,
        current_location: Location | None,
        triggered_event: Event | None,
        available_locations: list[Location],
        character: Character,
        compact_mode: bool = False,
        language: str = "en",
    ) -> str:
        if worldinfo is None:
            return t(_("Active World: None (Neutral setting, no specific world events)."), language)

        world_label = t(_("World Name:"), language)
        lines = [f"{world_label} {worldinfo.name}"]
        if current_location is not None:
            loc_label = t(_("Current Location:"), language)
            lines.append(f"{loc_label} {current_location.name}")
            if current_location.description.strip():
                if compact_mode:
                    short_desc = extract_first_sentence(current_location.description.strip(), max_chars=180)
                    atmo_label = t(_("Location Atmosphere:"), language)
                    lines.append(f"{atmo_label} {short_desc}")
                else:
                    loc_desc_label = t(_("Location Description:"), language)
                    lines.append(f"{loc_desc_label} {current_location.description.strip()}")
            if not compact_mode and current_location.vision_alt_text:
                vis_label = t(_("Visual Environment:"), language)
                lines.append(f"{vis_label} {current_location.vision_alt_text.strip()}")
        else:
            lines.append(t(_("Current Location: Unspecified"), language))

        if not compact_mode and available_locations:
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
                pref_label = t(_("Character's Preferred Locations:"), language)
                lines.append(f"{pref_label} {', '.join(pref_names)}")
            if disliked_names:
                disliked_label = t(_("Character's Disliked Locations:"), language)
                lines.append(f"{disliked_label} {', '.join(disliked_names)}")

        if triggered_event is not None:
            ev_label = t(_("Active Narrative Event ({title}):"), language).format(title=triggered_event.title)
            ev_hint = t(_("(Notice and organically weave this unfolding event into your immediate reaction and dialogue.)"), language)
            lines.append(f"{ev_label} {triggered_event.description.strip()} {ev_hint}")

        return "\n".join(lines)

    @staticmethod
    def _format_single_message(
        msg: Message,
        character_name: str,
        persona_name: str,
        distill: bool = False,
        language: str = "en",
    ) -> str:
        player_tag = t(_("Player"), language)
        you_tag = t(_("You"), language)
        speaker = f"{persona_name} ({player_tag})" if msg.role == MessageRole.USER else f"{character_name} ({you_tag})"
        raw_content = (
            (msg.localized_content or msg.english_content)
            if language != "en"
            else (msg.english_content or msg.localized_content)
        )
        content = (raw_content or "").strip()
        if distill and msg.role == MessageRole.CHARACTER:
            content = distill_message_dialogue(content, max_chars=380)
        elif distill and msg.role == MessageRole.USER and len(content) > 340:
            content = distill_message_dialogue(content, max_chars=320)

        if msg.image_alt_text and msg.image_alt_text.strip():
            alt = msg.image_alt_text.strip()
            img_prefix = t(_("[Player shows an image: {alt}]"), language).format(alt=alt)
            if content:
                content = f"{img_prefix} {content}"
            else:
                content = img_prefix
        return f"{speaker}: {content}" if content else ""

    @classmethod
    def _format_adaptive_chat_history(
        cls,
        narrative_messages: list[Message],
        character_name: str,
        persona_name: str,
        history_budget_tokens: int,
        effective_num_ctx: int = 4096,
        language: str = "en",
    ) -> tuple[str, str]:
        if not narrative_messages:
            return t(_("No messages yet."), language), "Empty (0 messages)"

        # Step 1: Try all up to 10 messages verbatim
        full_lines = [
            cls._format_single_message(m, character_name, persona_name, distill=False, language=language)
            for m in narrative_messages
        ]
        full_lines = [line for line in full_lines if line]
        full_text = "\n".join(full_lines)
        if estimate_tokens(full_text) <= history_budget_tokens:
            return full_text, f"{len(full_lines)} messages (100% verbatim)"

        # Step 2: Use 6-message window verbatim
        window_size = 6 if effective_num_ctx <= 6144 else min(8, len(narrative_messages))
        window_msgs = narrative_messages[-window_size:]
        win_lines = [
            cls._format_single_message(m, character_name, persona_name, distill=False, language=language)
            for m in window_msgs
        ]
        win_lines = [line for line in win_lines if line]
        win_text = "\n".join(win_lines)
        if estimate_tokens(win_text) <= history_budget_tokens:
            return win_text, f"{len(win_lines)} messages (windowed verbatim)"

        # Step 3: 2-Zone Dialogue Distillation (Zone 1: last 2 verbatim, Zone 2: older messages distilled)
        distilled_flags = [False] * len(window_msgs)
        zone2_limit = max(0, len(window_msgs) - 2)
        distilled_count = 0

        for i in range(zone2_limit):
            distilled_flags[i] = True
            distilled_count += 1
            candidate_lines = [
                cls._format_single_message(m, character_name, persona_name, distill=distilled_flags[idx], language=language)
                for idx, m in enumerate(window_msgs)
            ]
            candidate_lines = [line for line in candidate_lines if line]
            candidate_text = "\n".join(candidate_lines)
            if estimate_tokens(candidate_text) <= history_budget_tokens:
                return (
                    candidate_text,
                    f"{len(candidate_lines)} messages ({distilled_count} distilled in Zone 2, {len(candidate_lines) - distilled_count} verbatim)",
                )

        # Step 4: If still over budget even with all Zone 2 distilled, progressively drop oldest from Zone 2 (keep min 2)
        while len(window_msgs) > 2:
            window_msgs = window_msgs[1:]
            distilled_flags = distilled_flags[1:]
            candidate_lines = [
                cls._format_single_message(m, character_name, persona_name, distill=distilled_flags[idx], language=language)
                for idx, m in enumerate(window_msgs)
            ]
            candidate_lines = [line for line in candidate_lines if line]
            candidate_text = "\n".join(candidate_lines)
            if estimate_tokens(candidate_text) <= history_budget_tokens:
                dist_n = sum(1 for f in distilled_flags if f)
                return (
                    candidate_text,
                    f"{len(candidate_lines)} messages ({dist_n} distilled, {len(candidate_lines) - dist_n} verbatim)",
                )

        final_lines = [
            cls._format_single_message(m, character_name, persona_name, distill=False, language=language)
            for m in window_msgs[-2:]
        ]
        final_lines = [line for line in final_lines if line]
        return "\n".join(final_lines) if final_lines else t(_("No messages yet."), language), f"{len(final_lines)} messages (minimum acute window)"

    @classmethod
    def _format_chat_history(
        cls,
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
        lines = [
            cls._format_single_message(m, character_name, persona_name, distill=False)
            for m in narrative_messages
        ]
        lines = [line for line in lines if line]
        return "\n".join(lines) if lines else "No messages yet."

    @staticmethod
    def _format_knowledge_pool(
        memories: list[Memory],
        lorebooks: list[LorebookEntry],
        pool_budget_tokens: int = 500,
        scene_focus: SceneFocus = SceneFocus.GENERAL_ROLEPLAY,
    ) -> tuple[str, str, int, int, int, int]:
        if scene_focus == SceneFocus.LORE_MYSTERY:
            lore_budget = int(pool_budget_tokens * 0.65)
            mem_budget = pool_budget_tokens - lore_budget
        elif scene_focus == SceneFocus.INTIMACY_BIO:
            mem_budget = int(pool_budget_tokens * 0.55)
            lore_budget = pool_budget_tokens - mem_budget
        else:
            mem_budget = pool_budget_tokens // 2
            lore_budget = pool_budget_tokens - mem_budget

        selected_mem_lines: list[str] = []
        mem_tokens = 0
        for mem in memories[:4]:
            line = f"- {mem.title}: {mem.summary.strip()}"
            t_cost = estimate_tokens(line)
            if selected_mem_lines and (mem_tokens + t_cost) > mem_budget:
                break
            selected_mem_lines.append(line)
            mem_tokens += t_cost

        unused_mem_budget = max(0, mem_budget - mem_tokens)
        effective_lore_budget = lore_budget + unused_mem_budget

        selected_lore_lines: list[str] = []
        lore_tokens = 0
        full_count = 0
        distilled_count = 0

        for idx, entry in enumerate(lorebooks[:5]):
            content = entry.content.strip()
            if idx < 2:
                full_line = f"- {entry.title}: {content}"
                t_cost = estimate_tokens(full_line)
                if not selected_lore_lines or (lore_tokens + t_cost) <= effective_lore_budget:
                    if t_cost > effective_lore_budget and len(content) > 500:
                        short_c = extract_first_sentence(content, max_chars=420)
                        full_line = f"- {entry.title}: {short_c}"
                        t_cost = estimate_tokens(full_line)
                    selected_lore_lines.append(full_line)
                    lore_tokens += t_cost
                    full_count += 1
                    continue

            # Secondary entries (ranks 3-5 or when full entry exceeds remaining budget): 1-line bullet distillation
            bullet_summary = extract_first_sentence(content, max_chars=160)
            distilled_line = f"- {entry.title}: {bullet_summary}"
            d_cost = estimate_tokens(distilled_line)
            if (lore_tokens + d_cost) <= effective_lore_budget:
                selected_lore_lines.append(distilled_line)
                lore_tokens += d_cost
                distilled_count += 1

        mem_str = "\n\n".join(selected_mem_lines) if selected_mem_lines else "None."
        lore_str = "\n\n".join(selected_lore_lines) if selected_lore_lines else "None."
        return (
            mem_str,
            lore_str,
            len(selected_mem_lines),
            full_count,
            distilled_count,
            mem_tokens + lore_tokens,
        )

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
