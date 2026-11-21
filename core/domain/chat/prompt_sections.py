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
)


def format_character_definition(
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

    if character.appearance and character.appearance.strip():
        app_label = t(_("Physical Appearance:"), language)
        desc_block = f"{desc_block}\n\n{app_label}\n{character.appearance.strip()}"

    role_line = t(_("Role: You play this character ({name}). Embody these traits, canon backstory, and voice exclusively:"), language).format(name=character.name)
    name_label = t(_("Name:"), language)
    gender_label = t(_("Gender:"), language)
    desc_label = t(_("Description, Personality & Canon Backstory (All origin facts, personal history, and traits below are canon truth):"), language)
    return "\n".join([
        role_line,
        f"{name_label} {character.name}",
        f"{gender_label} {character.gender.value} ({c_forms['pronouns']})",
        f"{desc_label}\n{desc_block}",
    ])


def format_relation_section(
    relationship_value: float,
    translations: dict[int, RelationshipTier] | None = None,
    scene_focus: SceneFocus = SceneFocus.GENERAL_ROLEPLAY,
    character_name: str = "{{char}}",
    language: str = "en",
) -> str:
    tier = get_relationship_tier(relationship_value, translations=translations, language=language)
    base_rel = format_relationship_prompt(tier, language=language)
    directive = PythonFocusAnalyzer.get_focus_directive(scene_focus, character_name, language=language)
    return f"{base_rel}\n\n{directive}" if directive else base_rel


def parse_example_blocks(dialogue_examples: list | str) -> list[str]:
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
        if any(isinstance(x, str) and x.strip() == "<START>" for x in dialogue_examples):
            joined = "\n".join(str(x).strip() for x in dialogue_examples if str(x).strip())
            parts = [p.strip() for p in joined.split("<START>") if p.strip()]
            return [f"<START>\n{p}" for p in parts]

        for item in dialogue_examples:
            if isinstance(item, dict):
                trig = str(item.get("trigger", "")).strip()
                resp = str(item.get("response", "")).strip()
                if not trig and not resp:
                    continue
                if not trig.lower().startswith("{{user}}:"):
                    trig = f"{{{{user}}}}: {trig}" if trig else "{{user}}:"
                if not resp.lower().startswith("{{char}}:"):
                    resp = f"{{{{char}}}}: {resp}" if resp else "{{char}}:"
                blocks.append(f"<START>\n{trig}\n{resp}")
            elif isinstance(item, str):
                s = item.strip()
                if s:
                    blocks.append(s if "<START>" in s else f"<START>\n{{{{user}}}}:\n{{{{char}}}}: {s}")
    return blocks


def format_dialogue_examples(
    dialogue_examples: list | str,
    narrative_msg_count: int = 0,
    scene_focus: SceneFocus = SceneFocus.GENERAL_ROLEPLAY,
    active_tags: list[str] | None = None,
    language: str = "en",
) -> tuple[str, int]:
    blocks = parse_example_blocks(dialogue_examples)
    if not blocks:
        return t(_("None."), language), 0
    if narrative_msg_count < 4:
        selected = blocks[:2]
        return "\n\n".join(selected), len(selected)

    search_terms = PythonFocusAnalyzer.get_focus_keywords(scene_focus) | {
        tag.strip().lower() for tag in (active_tags or []) if tag and tag.strip()
    }
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


def format_user_persona(persona: UserPersona, language: str = "en") -> str:
    u_forms = get_gender_forms(persona.gender.value)
    role_line = t(
        _("Role: This is your conversation partner ({name}). You are NOT this person. NEVER speak, act, think, or decide on behalf of {name}:"),
        language,
    ).format(name=persona.name)
    lines = [
        role_line,
        f"{t(_('Name:'), language)} {persona.name}",
        f"{t(_('Gender:'), language)} {persona.gender.value} ({u_forms['pronouns']})",
    ]
    if persona.description.strip():
        lines.append(f"{t(_('Background & Personality:'), language)} {persona.description.strip()[:1200]}")
    if persona.appearance.strip():
        lines.append(f"{t(_('Physical Appearance:'), language)} {persona.appearance.strip()}")
    return "\n".join(lines)


def format_world_info(
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

    lines = [f"{t(_('World Name:'), language)} {worldinfo.name}"]
    if current_location is not None:
        lines.append(f"{t(_('Current Location:'), language)} {current_location.name}")
        if current_location.description.strip():
            if compact_mode:
                short_desc = extract_first_sentence(current_location.description.strip(), max_chars=180)
                lines.append(f"{t(_('Location Atmosphere:'), language)} {short_desc}")
            else:
                lines.append(f"{t(_('Location Description:'), language)} {current_location.description.strip()}")
        if not compact_mode and current_location.vision_alt_text:
            lines.append(f"{t(_('Visual Environment:'), language)} {current_location.vision_alt_text.strip()}")
    else:
        lines.append(t(_("Current Location: Unspecified"), language))

    if not compact_mode and available_locations:
        loc_map = {loc.id: loc.name for loc in available_locations if loc.id is not None}
        pref_names = [loc_map[lid] for lid in character.preferred_location_ids if lid in loc_map]
        disliked_names = [loc_map[lid] for lid in character.disliked_location_ids if lid in loc_map]
        if pref_names:
            lines.append(f"{t(_('Character\'s Preferred Locations:'), language)} {', '.join(pref_names)}")
        if disliked_names:
            lines.append(f"{t(_('Character\'s Disliked Locations:'), language)} {', '.join(disliked_names)}")

    if triggered_event is not None:
        ev_label = t(_("Active Narrative Event ({title}):"), language).format(title=triggered_event.title)
        ev_hint = t(_("(Notice and organically weave this unfolding event into your immediate reaction and dialogue.)"), language)
        lines.append(f"{ev_label} {triggered_event.description.strip()} {ev_hint}")

    return "\n".join(lines)


def format_single_message(
    msg: Message,
    character_name: str,
    persona_name: str,
    distill: bool = False,
    language: str = "en",
) -> str:
    speaker = (
        f"{persona_name} ({t(_('Player'), language)})"
        if msg.role == MessageRole.USER
        else f"{character_name} ({t(_('You'), language)})"
    )
    content = (msg.content or "").strip()
    if distill and msg.role == MessageRole.CHARACTER:
        content = distill_message_dialogue(content, max_chars=380)
    elif distill and msg.role == MessageRole.USER and len(content) > 340:
        content = distill_message_dialogue(content, max_chars=320)

    if msg.image_alt_text and msg.image_alt_text.strip():
        img_prefix = t(_("[Player shows an image: {alt}]"), language).format(alt=msg.image_alt_text.strip())
        content = f"{img_prefix} {content}" if content else img_prefix
    return f"{speaker}: {content}" if content else ""


def format_knowledge_pool(
    memories: list[Memory],
    lorebooks: list[LorebookEntry],
    pool_budget_tokens: int = 500,
    scene_focus: SceneFocus = SceneFocus.GENERAL_ROLEPLAY,
    language: str = "en",
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

    effective_lore_budget = lore_budget + max(0, mem_budget - mem_tokens)
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
                    full_line = f"- {entry.title}: {extract_first_sentence(content, max_chars=420)}"
                    t_cost = estimate_tokens(full_line)
                selected_lore_lines.append(full_line)
                lore_tokens += t_cost
                full_count += 1
                continue

        distilled_line = f"- {entry.title}: {extract_first_sentence(content, max_chars=160)}"
        d_cost = estimate_tokens(distilled_line)
        if (lore_tokens + d_cost) <= effective_lore_budget:
            selected_lore_lines.append(distilled_line)
            lore_tokens += d_cost
            distilled_count += 1

    none_label = t(_("None."), language)
    return (
        "\n\n".join(selected_mem_lines) if selected_mem_lines else none_label,
        "\n\n".join(selected_lore_lines) if selected_lore_lines else none_label,
        len(selected_mem_lines),
        full_count,
        distilled_count,
        mem_tokens + lore_tokens,
    )
