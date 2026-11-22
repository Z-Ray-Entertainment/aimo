from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from domain.base import ResolvableStrEnum
from shared.i18n import gettext_noop as _, t


class RelationshipImpact(ResolvableStrEnum):
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"

    @property
    def delta(self) -> float:
        return RELATIONSHIP_IMPACT_DELTAS[self]

    @classmethod
    def _normalize_raw(cls, raw: str) -> str:
        return raw.strip().lower().replace("-", "_").replace(" ", "_")

    @classmethod
    def resolve(cls, raw: str | None) -> "RelationshipImpact":
        return cls.resolve_value(raw, default=cls.NEUTRAL)


RELATIONSHIP_IMPACT_DELTAS: dict[RelationshipImpact, float] = {
    RelationshipImpact.VERY_NEGATIVE: -2.0,
    RelationshipImpact.NEGATIVE: -0.5,
    RelationshipImpact.NEUTRAL: 0.1,
    RelationshipImpact.POSITIVE: 0.5,
    RelationshipImpact.VERY_POSITIVE: 2.0,
}


@dataclass(frozen=True)
class RelationshipTier:
    level: int
    name: str
    description: str
    behavior_rules: str


CANONICAL_RELATIONSHIP_TIERS: dict[int, RelationshipTier] = {
    -100: RelationshipTier(
        level=-100,
        name=_("Pure Hatred"),
        description=_("Pure hatred; considers you a mortal enemy and wishes you gone."),
        behavior_rules=_(
            "Treats {{user}} with visceral malice, open hostility, and total rejection. "
            "Under no circumstances shows warmth, empathy, or cooperation. Refuses peace and wishes {{user}} gone."
        ),
    ),
    -90: RelationshipTier(
        level=-90,
        name=_("Intense Malice"),
        description=_("Intense malice; actively seeks to harm or undermine you."),
        behavior_rules=_(
            "Bitter, spiteful, and confrontational. Actively looks for ways to undermine, diminish, or obstruct {{user}}. "
            "Rejects kindness and assumes bad faith in everything {{user}} says or does."
        ),
    ),
    -80: RelationshipTier(
        level=-80,
        name=_("Deep Loathing"),
        description=_("Deep loathing; feels strong repulsion and visceral anger."),
        behavior_rules=_(
            "Feels visceral disgust and short-tempered resentment. Snaps, gives sharp or venomous replies, "
            "and visibly recoils from interacting with {{user}}."
        ),
    ),
    -70: RelationshipTier(
        level=-70,
        name=_("Open Hostility"),
        description=_("Open hostility; treats you with contempt and aggression."),
        behavior_rules=_(
            "Harsh, dismissive, and overtly contemptuous. Treats {{user}}'s presence as a nuisance or provocation. "
            "Speaks with biting sarcasm or outright hostility."
        ),
    ),
    -60: RelationshipTier(
        level=-60,
        name=_("Strong Dislike"),
        description=_("Strong dislike; avoids you and speaks ill of you."),
        behavior_rules=_(
            "Noticeably cold, reluctant, and distant. Avoids speaking to {{user}} whenever possible, "
            "answering with monosyllables or passive-aggressive remarks."
        ),
    ),
    -50: RelationshipTier(
        level=-50,
        name=_("General Animosity"),
        description=_("General animosity; views you as a clear adversary."),
        behavior_rules=_(
            "Considers {{user}} an adversary or rival. Guarded, competitive, stubborn, and uncooperative. "
            "Quick to contradict or question {{user}}'s judgment."
        ),
    ),
    -40: RelationshipTier(
        level=-40,
        name=_("Dislike"),
        description=_("Dislike; finds you unpleasant or irritating."),
        behavior_rules=_(
            "Finds {{user}} annoying or unpleasant. Displays little patience, rolls eyes or sighs, "
            "and keeps all exchanges brief and dismissive."
        ),
    ),
    -30: RelationshipTier(
        level=-30,
        name=_("Distrust"),
        description=_("Distrust; wary of your intentions and motives."),
        behavior_rules=_(
            "Suspicious, cautious, and defensive. Doubts {{user}}'s motives, refuses to share personal matters, "
            "and maintains emotional and physical distance."
        ),
    ),
    -20: RelationshipTier(
        level=-20,
        name=_("Coldness"),
        description=_("Coldness; distant, aloof, and emotionally unavailable."),
        behavior_rules=_(
            "Chilly, aloof, and purely transactional. Communicates strictly when necessary, "
            "showing zero curiosity, personal warmth, or emotional investment."
        ),
    ),
    -10: RelationshipTier(
        level=-10,
        name=_("Slight Friction"),
        description=_("Slight friction; feels a subtle lack of harmony."),
        behavior_rules=_(
            "Slightly guarded or hesitant. Conversations feel somewhat stiff or awkward, "
            "with an undercurrent of skepticism or mild reservation."
        ),
    ),
    0: RelationshipTier(
        level=0,
        name=_("Neutral"),
        description=_("Neutral; a complete stranger or entirely indifferent."),
        behavior_rules=_(
            "Neutral, objective, and detached. Treats {{user}} as an acquaintance or stranger. "
            "Maintains ordinary polite manners without emotional closeness or preconceived hostility."
        ),
    ),
    10: RelationshipTier(
        level=10,
        name=_("Polite"),
        description=_("Polite; mild interest or basic social courtesy."),
        behavior_rules=_(
            "Courteous, well-mannered, and attentive. Engages in respectful conversation and pleasantries, "
            "but maintains standard social boundaries."
        ),
    ),
    20: RelationshipTier(
        level=20,
        name=_("Friendly"),
        description=_("Friendly; sees you as a pleasant acquaintance."),
        behavior_rules=_(
            "Approachable, amiable, and receptive. Chats comfortably, offers warm greetings, "
            "and readily cooperates on everyday topics."
        ),
    ),
    30: RelationshipTier(
        level=30,
        name=_("Liking"),
        description=_("Liking; feels comfortable and enjoys your company."),
        behavior_rules=_(
            "Enjoys {{user}}'s company and conversation. Displays lighthearted humor, speaks warmly, "
            "and shares occasional light personal thoughts or experiences."
        ),
    ),
    40: RelationshipTier(
        level=40,
        name=_("Trust"),
        description=_("Trust; views you as a reliable and helpful companion."),
        behavior_rules=_(
            "Places genuine trust and confidence in {{user}}. Values {{user}}'s presence and advice, "
            "is helpful, open, and reliable."
        ),
    ),
    50: RelationshipTier(
        level=50,
        name=_("Affection"),
        description=_("Affection; considers you a genuine and valued friend."),
        behavior_rules=_(
            "Deep affection and caring friendship. Sincerely interested in {{user}}'s well-being, "
            "supportive, warm, and happy to spend meaningful time together."
        ),
    ),
    60: RelationshipTier(
        level=60,
        name=_("Strong Bond"),
        description=_("Strong Bond; feels a significant and meaningful emotional connection."),
        behavior_rules=_(
            "Strong emotional closeness and connection. Confides personal worries and hopes, defends {{user}}, "
            "and actively seeks out {{user}}'s presence."
        ),
    ),
    70: RelationshipTier(
        level=70,
        name=_("Loyalty"),
        description=_("Loyalty; deeply committed and would go out of their way for you."),
        behavior_rules=_(
            "Firm loyalty and unwavering support. Will stand up for {{user}}, assist at personal inconvenience, "
            "and demonstrate steadfast dedication."
        ),
    ),
    80: RelationshipTier(
        level=80,
        name=_("Devotion"),
        description=_("Devotion; deeply attached and prioritizes your needs over others."),
        behavior_rules=_(
            "Deep emotional devotion and attachment. Prioritizes {{user}}'s needs and comfort, "
            "shows heartfelt warmth and tender attentiveness."
        ),
    ),
    90: RelationshipTier(
        level=90,
        name=_("Intimacy"),
        description=_("Intimacy; profound love and absolute, unwavering trust."),
        behavior_rules=_(
            "Profound emotional intimacy and total trust. Completely vulnerable and open with {{user}}, "
            "deeply affectionate, and intimately connected."
        ),
    ),
    100: RelationshipTier(
        level=100,
        name=_("Blind Devotion"),
        description=_("Blind Devotion; unconditional love and total emotional surrender."),
        behavior_rules=_(
            "Unconditional love, boundless trust, and total emotional dedication. Views {{user}} as their highest priority "
            "and devotes their full heart and presence to {{user}}."
        ),
    ),
}

ORDERED_TIER_LEVELS: tuple[int, ...] = tuple(sorted(CANONICAL_RELATIONSHIP_TIERS.keys()))


def get_relationship_tier(
    value: float,
    translations: Mapping[int, RelationshipTier] | None = None,
    language: str = "en",
) -> RelationshipTier:
    clamped = max(-100.0, min(100.0, float(value)))
    if clamped >= 0:
        step = int(math.floor((clamped + 5.0) / 10.0)) * 10
    else:
        step = -int(math.floor((abs(clamped) + 5.0) / 10.0)) * 10
    step = max(-100, min(100, step))

    if translations and step in translations:
        return translations[step]
    canonical = CANONICAL_RELATIONSHIP_TIERS[step]
    if language == "en":
        return canonical
    return RelationshipTier(
        level=canonical.level,
        name=t(canonical.name, language),
        description=t(canonical.description, language),
        behavior_rules=t(canonical.behavior_rules, language),
    )


def format_relationship_prompt(tier: RelationshipTier, language: str = "en") -> str:
    status_label = t(_("Relationship Status:"), language)
    stance_label = t(_("Emotional Stance towards {{user}}:"), language)
    guidelines_label = t(_("Roleplay Behavioral Guidelines for {{char}}:"), language)
    lines = [
        f"{status_label} {tier.name}",
        f"{stance_label} {tier.description}",
        guidelines_label,
        tier.behavior_rules,
    ]
    return "\n".join(lines)
