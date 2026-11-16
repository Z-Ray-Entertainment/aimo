from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping


@dataclass(frozen=True)
class RelationshipTier:
    level: int
    name: str
    description: str
    behavior_rules: str


CANONICAL_RELATIONSHIP_TIERS: dict[int, RelationshipTier] = {
    -100: RelationshipTier(
        level=-100,
        name="Pure Hatred",
        description="Pure hatred; considers you a mortal enemy and wishes you gone.",
        behavior_rules=(
            "Treats {{user}} with visceral malice, open hostility, and total rejection. "
            "Under no circumstances shows warmth, empathy, or cooperation. Refuses peace and wishes {{user}} gone."
        ),
    ),
    -90: RelationshipTier(
        level=-90,
        name="Intense Malice",
        description="Intense malice; actively seeks to harm or undermine you.",
        behavior_rules=(
            "Bitter, spiteful, and confrontational. Actively looks for ways to undermine, diminish, or obstruct {{user}}. "
            "Rejects kindness and assumes bad faith in everything {{user}} says or does."
        ),
    ),
    -80: RelationshipTier(
        level=-80,
        name="Deep Loathing",
        description="Deep loathing; feels strong repulsion and visceral anger.",
        behavior_rules=(
            "Feels visceral disgust and short-tempered resentment. Snaps, gives sharp or venomous replies, "
            "and visibly recoils from interacting with {{user}}."
        ),
    ),
    -70: RelationshipTier(
        level=-70,
        name="Open Hostility",
        description="Open hostility; treats you with contempt and aggression.",
        behavior_rules=(
            "Harsh, dismissive, and overtly contemptuous. Treats {{user}}'s presence as a nuisance or provocation. "
            "Speaks with biting sarcasm or outright hostility."
        ),
    ),
    -60: RelationshipTier(
        level=-60,
        name="Strong Dislike",
        description="Strong dislike; avoids you and speaks ill of you.",
        behavior_rules=(
            "Noticeably cold, reluctant, and distant. Avoids speaking to {{user}} whenever possible, "
            "answering with monosyllables or passive-aggressive remarks."
        ),
    ),
    -50: RelationshipTier(
        level=-50,
        name="General Animosity",
        description="General animosity; views you as a clear adversary.",
        behavior_rules=(
            "Considers {{user}} an adversary or rival. Guarded, competitive, stubborn, and uncooperative. "
            "Quick to contradict or question {{user}}'s judgment."
        ),
    ),
    -40: RelationshipTier(
        level=-40,
        name="Dislike",
        description="Dislike; finds you unpleasant or irritating.",
        behavior_rules=(
            "Finds {{user}} annoying or unpleasant. Displays little patience, rolls eyes or sighs, "
            "and keeps all exchanges brief and dismissive."
        ),
    ),
    -30: RelationshipTier(
        level=-30,
        name="Distrust",
        description="Distrust; wary of your intentions and motives.",
        behavior_rules=(
            "Suspicious, cautious, and defensive. Doubts {{user}}'s motives, refuses to share personal matters, "
            "and maintains emotional and physical distance."
        ),
    ),
    -20: RelationshipTier(
        level=-20,
        name="Coldness",
        description="Coldness; distant, aloof, and emotionally unavailable.",
        behavior_rules=(
            "Chilly, aloof, and purely transactional. Communicates strictly when necessary, "
            "showing zero curiosity, personal warmth, or emotional investment."
        ),
    ),
    -10: RelationshipTier(
        level=-10,
        name="Slight Friction",
        description="Slight friction; feels a subtle lack of harmony.",
        behavior_rules=(
            "Slightly guarded or hesitant. Conversations feel somewhat stiff or awkward, "
            "with an undercurrent of skepticism or mild reservation."
        ),
    ),
    0: RelationshipTier(
        level=0,
        name="Neutral",
        description="Neutral; a complete stranger or entirely indifferent.",
        behavior_rules=(
            "Neutral, objective, and detached. Treats {{user}} as an acquaintance or stranger. "
            "Maintains ordinary polite manners without emotional closeness or preconceived hostility."
        ),
    ),
    10: RelationshipTier(
        level=10,
        name="Polite",
        description="Polite; mild interest or basic social courtesy.",
        behavior_rules=(
            "Courteous, well-mannered, and attentive. Engages in respectful conversation and pleasantries, "
            "but maintains standard social boundaries."
        ),
    ),
    20: RelationshipTier(
        level=20,
        name="Friendly",
        description="Friendly; sees you as a pleasant acquaintance.",
        behavior_rules=(
            "Approachable, amiable, and receptive. Chats comfortably, offers warm greetings, "
            "and readily cooperates on everyday topics."
        ),
    ),
    30: RelationshipTier(
        level=30,
        name="Liking",
        description="Liking; feels comfortable and enjoys your company.",
        behavior_rules=(
            "Enjoys {{user}}'s company and conversation. Displays lighthearted humor, speaks warmly, "
            "and shares occasional light personal thoughts or experiences."
        ),
    ),
    40: RelationshipTier(
        level=40,
        name="Trust",
        description="Trust; views you as a reliable and helpful companion.",
        behavior_rules=(
            "Places genuine trust and confidence in {{user}}. Values {{user}}'s presence and advice, "
            "is helpful, open, and reliable."
        ),
    ),
    50: RelationshipTier(
        level=50,
        name="Affection",
        description="Affection; considers you a genuine and valued friend.",
        behavior_rules=(
            "Deep affection and caring friendship. Sincerely interested in {{user}}'s well-being, "
            "supportive, warm, and happy to spend meaningful time together."
        ),
    ),
    60: RelationshipTier(
        level=60,
        name="Strong Bond",
        description="Strong Bond; feels a significant and meaningful emotional connection.",
        behavior_rules=(
            "Strong emotional closeness and connection. Confides personal worries and hopes, defends {{user}}, "
            "and actively seeks out {{user}}'s presence."
        ),
    ),
    70: RelationshipTier(
        level=70,
        name="Loyalty",
        description="Loyalty; deeply committed and would go out of their way for you.",
        behavior_rules=(
            "Firm loyalty and unwavering support. Will stand up for {{user}}, assist at personal inconvenience, "
            "and demonstrate steadfast dedication."
        ),
    ),
    80: RelationshipTier(
        level=80,
        name="Devotion",
        description="Devotion; deeply attached and prioritizes your needs over others.",
        behavior_rules=(
            "Deep emotional devotion and attachment. Prioritizes {{user}}'s needs and comfort, "
            "shows heartfelt warmth and tender attentiveness."
        ),
    ),
    90: RelationshipTier(
        level=90,
        name="Intimacy",
        description="Intimacy; profound love and absolute, unwavering trust.",
        behavior_rules=(
            "Profound emotional intimacy and total trust. Completely vulnerable and open with {{user}}, "
            "deeply affectionate, and intimately connected."
        ),
    ),
    100: RelationshipTier(
        level=100,
        name="Blind Devotion",
        description="Blind Devotion; unconditional love and total emotional surrender.",
        behavior_rules=(
            "Unconditional love, boundless trust, and total emotional dedication. Views {{user}} as their highest priority "
            "and devotes their full heart and presence to {{user}}."
        ),
    ),
}

ORDERED_TIER_LEVELS: tuple[int, ...] = tuple(sorted(CANONICAL_RELATIONSHIP_TIERS.keys()))


def get_relationship_tier(value: float, translations: Mapping[int, RelationshipTier] | None = None) -> RelationshipTier:
    clamped = max(-100.0, min(100.0, float(value)))
    if clamped >= 0:
        step = int(math.floor((clamped + 5.0) / 10.0)) * 10
    else:
        step = -int(math.floor((abs(clamped) + 5.0) / 10.0)) * 10
    step = max(-100, min(100, step))

    if translations and step in translations:
        return translations[step]
    return CANONICAL_RELATIONSHIP_TIERS[step]


def format_relationship_prompt(tier: RelationshipTier) -> str:
    lines = [
        f"Relationship Status: {tier.name}",
        f"Emotional Stance towards {{{{user}}}}: {tier.description}",
        f"Roleplay Behavioral Guidelines for {{{{char}}}}:",
        tier.behavior_rules,
    ]
    return "\n".join(lines)
