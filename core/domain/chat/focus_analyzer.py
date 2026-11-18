from enum import Enum
import re

from domain.chat.models import Message, MessageRole


class SceneFocus(str, Enum):
    INTIMACY_BIO = "intimacy_bio"
    WORLD_EXPLORATION = "world_exploration"
    EVENT_ACTION = "event_action"
    LORE_MYSTERY = "lore_mystery"
    GENERAL_ROLEPLAY = "general_roleplay"


_FALSE_POSITIVE_PHRASES_RE = re.compile(
    r"\b(?:fuck\s+you|fuck\s+off|fick\s+dich|geh\s+weg|geh\s+mir\s+aus|hau\s+ab|verpiss\s+dich|what\s+the\s+fuck)\b",
    re.IGNORECASE,
)

_STRONG_INDICATORS: dict[SceneFocus, frozenset[str]] = {
    SceneFocus.INTIMACY_BIO: frozenset({
        # German strong (Intimacy, Romance, Personal Biography & Trauma)
        "sex", "jungfrau", "jungfräulich", "intimität", "intim", "beziehung", "vergangenheit",
        "kindheit", "geburt", "familie", "eltern", "mutter", "vater", "schwester", "bruder",
        "narbe", "narben", "trauma", "exfreund", "expartner", "erfahrung", "erfahrungen",
        "liebe", "lieben", "verliebt", "geküsst", "küssen", "kuss", "schlafen", "bett",
        "zuneigung", "vertrauen", "ehrlichkeit", "geheimnis", "sehnsucht", "begehren",
        "demisexuell", "demisexualität", "unberührt", "verletzlich", "verletzlichkeit",
        "scham", "eifersucht", "eifersüchtig", "bindung", "herz", "seele", "zärtlich",
        "zärtlichkeit", "selbstwert", "schuld", "verzeihen",
        # English strong
        "virgin", "virginity", "intimacy", "intimate", "relationship", "relationships",
        "backstory", "childhood", "birth", "upbringing", "parents", "mother", "father",
        "sister", "brother", "scar", "scars", "trauma", "boyfriend", "girlfriend",
        "lover", "lovers", "sexual", "sexuality", "demisexual", "demisexuality",
        "kiss", "kissed", "kissing", "romance", "romantic", "affection", "vulnerable",
        "vulnerability", "jealous", "jealousy", "heartbreak", "untouched",
        "confess", "confession", "attraction", "desire", "passionate", "forgive", "guilt",
    }),
    SceneFocus.WORLD_EXPLORATION: frozenset({
        # German strong
        "erkunden", "umsehen", "umschauen", "wandern", "reisen", "spazieren", "betreten",
        "verlassen", "schauplatz", "landschaft", "architektur", "taverne", "bibliothek",
        "wald", "gebäude", "draußen", "horizont", "orientierung", "wegweiser", "landkarte",
        "pfad", "ankommen", "weitergehen", "aufbrechen", "hingehen",
        # English strong
        "explore", "exploring", "exploration", "surroundings", "environment", "scenery",
        "landscape", "travel", "traveling", "journey", "architecture", "tavern", "library",
        "forest", "building", "corridor", "outdoors", "horizon", "pathway", "destination",
        "arrive", "depart",
    }),
    SceneFocus.EVENT_ACTION: frozenset({
        # German strong
        "angriff", "angreifen", "kampf", "kämpfen", "gefahr", "fliehen", "flucht",
        "waffe", "schwert", "pistole", "explosion", "alarm", "notfall",
        "hinterhalt", "überfall", "retten", "deckung",
        # English strong
        "attack", "attacking", "combat", "fight", "fighting", "danger", "flee", "escape",
        "weapon", "sword", "gun", "explosion", "ambush", "emergency", "defend", "dodge", "rescue",
    }),
    SceneFocus.LORE_MYSTERY: frozenset({
        # German strong
        "magie", "zauber", "fluch", "ritual", "artefakt", "legende", "mythos", "prophezeiung",
        "orden", "gilde", "fraktion", "königreich", "imperium", "gott", "götter", "dämon",
        "chronik", "alchemie", "relikt", "altertum", "forschungsprojekt", "bioinformatik",
        # English strong
        "magic", "spell", "curse", "ritual", "artifact", "legend", "myth", "prophecy",
        "order", "guild", "faction", "kingdom", "empire", "deity", "gods", "demon",
        "chronicle", "alchemy", "relic", "ancient", "lore", "bioinformatics",
    }),
}

_WEAK_INDICATORS: dict[SceneFocus, frozenset[str]] = {
    SceneFocus.INTIMACY_BIO: frozenset({
        "gefühl", "gefühle", "fühlen", "angst", "ehrlich", "wahrheit", "früher",
        "damals", "männer", "frauen", "allein", "einsam", "nähe", "berühren", "berührung",
        "ego", "unsicher", "fragil", "schmerz", "tränen", "weinen", "umarmen", "körper", "kind",
        "feel", "feelings", "honest", "truth", "past", "men", "women", "alone", "lonely",
        "closeness", "touch", "insecure", "fragile", "pain", "tears", "cry", "hug", "body",
    }),
    SceneFocus.WORLD_EXPLORATION: frozenset({
        "wohin", "ort", "umgebung", "richtung", "wetter", "regen", "stadt", "dorf", "straße",
        "where", "location", "direction", "weather", "rain", "city", "town", "street",
    }),
    SceneFocus.EVENT_ACTION: frozenset({
        "plötzlich", "vorsicht", "achtung", "hilfe", "schrei", "schreien", "rennen", "bedrohung",
        "suddenly", "careful", "help", "scream", "running", "threat",
    }),
    SceneFocus.LORE_MYSTERY: frozenset({
        "geschichte", "rätsel", "gesetz", "wissenschaft", "studie", "labor", "biotech",
        "history", "mystery", "science", "research", "laboratory",
    }),
}


class PythonFocusAnalyzer:
    """Zero-latency, zero-token bilingual heuristic analyzer with 2-turn momentum."""

    def analyze(
        self,
        recent_messages: list[Message],
        active_tags: list[str] | None = None,
        has_triggered_event: bool = False,
    ) -> SceneFocus:
        if has_triggered_event:
            return SceneFocus.EVENT_ACTION

        if not recent_messages:
            return SceneFocus.GENERAL_ROLEPLAY

        scores: dict[SceneFocus, float] = {
            SceneFocus.INTIMACY_BIO: 0.0,
            SceneFocus.WORLD_EXPLORATION: 0.0,
            SceneFocus.EVENT_ACTION: 0.0,
            SceneFocus.LORE_MYSTERY: 0.0,
        }
        strong_counts: dict[SceneFocus, int] = {f: 0 for f in scores}

        window = recent_messages[-4:]
        turn_weights = [1.0, 0.65, 0.45, 0.3]

        for idx, msg in enumerate(reversed(window)):
            base_weight = turn_weights[idx] if idx < len(turn_weights) else 0.2
            role_multiplier = 1.25 if msg.role == MessageRole.USER else 0.75
            weight = base_weight * role_multiplier

            text = (msg.english_content or msg.localized_content or "").strip()
            if not text:
                continue
            cleaned_text = _FALSE_POSITIVE_PHRASES_RE.sub(" ", text.lower())
            words = set(re.findall(r"[a-zA-ZäöüÄÖÜß]{3,}", cleaned_text))

            for focus in scores:
                strong_hits = len(words & _STRONG_INDICATORS[focus])
                weak_hits = len(words & _WEAK_INDICATORS[focus])
                strong_counts[focus] += strong_hits
                scores[focus] += weight * (strong_hits * 2.2 + weak_hits * 0.8)

        if active_tags:
            tag_set = {t.strip().lower() for t in active_tags if t and t.strip()}
            for focus in scores:
                sh = len(tag_set & _STRONG_INDICATORS[focus])
                strong_counts[focus] += sh
                scores[focus] += sh * 0.5

        # Require at least 1 strong indicator for specialized non-intimacy modes to prevent weak-word drift
        for focus in (SceneFocus.WORLD_EXPLORATION, SceneFocus.EVENT_ACTION, SceneFocus.LORE_MYSTERY):
            if strong_counts[focus] == 0:
                scores[focus] *= 0.4

        best_focus = max(scores, key=lambda f: scores[f])
        if scores[best_focus] >= 1.6:
            return best_focus

        return SceneFocus.GENERAL_ROLEPLAY

    @staticmethod
    def get_focus_directive(focus: SceneFocus, character_name: str) -> str:
        if focus == SceneFocus.INTIMACY_BIO:
            return (
                f"Active Scene Focus — Personal History & Intimacy:\n"
                f"The conversation centers on personal feelings, intimacy, or {character_name}'s past. "
                f"Strictly honor {character_name}'s canon origin, sexual history, and intimacy traits defined in [CHARACTER_DEFINITION]. "
                f"NEVER invent or admit to past sexual or romantic experiences that contradict [CHARACTER_DEFINITION], "
                f"while allowing authentic emotional responses to the current moment."
            )
        if focus == SceneFocus.WORLD_EXPLORATION:
            return (
                f"Active Scene Focus — Environment & Exploration:\n"
                f"Pay close attention to the current location, sensory atmosphere, and {character_name}'s location preferences in [WORLD_INFO]."
            )
        if focus == SceneFocus.EVENT_ACTION:
            return (
                f"Active Scene Focus — Immediate Narrative Event:\n"
                f"React directly and organically to the unfolding event or acute action described in [WORLD_INFO] and [CHAT_HISTORY]."
            )
        if focus == SceneFocus.LORE_MYSTERY:
            return (
                f"Active Scene Focus — World Lore & Background Knowledge:\n"
                f"Incorporate relevant facts and canon details from [RELEVANT_LOREBOOKS] and [RELEVANT_MEMORIES] naturally into {character_name}'s perspective."
            )
        return ""

    @staticmethod
    def get_focus_keywords(focus: SceneFocus) -> frozenset[str]:
        if focus in _STRONG_INDICATORS:
            return _STRONG_INDICATORS[focus] | _WEAK_INDICATORS.get(focus, frozenset())
        return frozenset()
