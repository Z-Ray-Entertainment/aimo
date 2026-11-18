import math
import re
import unicodedata

import bcrypt

_UMLAUT_MAP: dict[str, str] = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "Ä": "Ae",
    "Ö": "Oe",
    "Ü": "Ue",
    "ß": "ss",
}


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


STOPWORDS: frozenset[str] = frozenset({
    # German stopwords
    "aber", "alle", "allem", "allen", "aller", "alles", "als", "also", "am", "an",
    "andere", "anderem", "anderen", "anderer", "anderes", "anderm", "andern", "anderr", "anders",
    "auch", "auf", "aus", "bei", "bin", "bis", "bist", "da", "damit", "dann", "das", "dass", "daß",
    "dasselbe", "dazu", "dein", "deine", "deinem", "deinen", "deiner", "deines", "dem", "demselben",
    "den", "denn", "denselben", "der", "derer", "derselbe", "derselben", "des", "desselben", "dessen",
    "dich", "die", "dies", "diese", "dieselbe", "dieselben", "diesem", "diesen", "dieser", "dieses",
    "dir", "doch", "dort", "du", "durch", "ein", "eine", "einem", "einen", "einer", "eines", "einig",
    "einige", "einigem", "einigen", "einiger", "einiges", "einmal", "er", "es", "etwas", "euch",
    "euer", "eure", "eurem", "euren", "eurer", "eures", "für", "gegen", "gewesen", "hab", "habe",
    "haben", "hat", "hatte", "hatten", "hier", "hin", "hinter", "ich", "ihm", "ihn", "ihnen", "ihr",
    "ihre", "ihrem", "ihren", "ihrer", "ihres", "im", "immer", "in", "indem", "ins", "ist", "jede",
    "jedem", "jeden", "jeder", "jedes", "jene", "jenem", "jenen", "jener", "jenes", "jetzt", "kann",
    "kannst", "können", "könnte", "machen", "man", "manche", "manchem", "manchen", "mancher", "manches",
    "mein", "meine", "meinem", "meinen", "meiner", "meines", "mich", "mir", "mit", "muss", "musst",
    "müssen", "nach", "nachdem", "nein", "nicht", "nichts", "noch", "nun", "nur", "ob", "oder", "ohne",
    "sehr", "sein", "seine", "seinem", "seinen", "seiner", "seines", "selbst", "sich", "sie", "sind",
    "so", "solche", "solchem", "solchen", "solcher", "solches", "soll", "sollte", "sonst", "über",
    "um", "und", "uns", "unser", "unsere", "unserem", "unseren", "unserer", "unseres", "unter", "vom",
    "von", "vor", "während", "war", "waren", "warst", "warum", "was", "weg", "weil", "weiter", "weitere",
    "welchem", "welchen", "welcher", "welches", "wenn", "wer", "werde", "werden", "werdet", "wie",
    "wieder", "will", "wir", "wird", "wirst", "wo", "wollen", "wollte", "würde", "würden", "zu",
    "zum", "zur", "zwar", "zwischen",
    # English stopwords
    "about", "above", "after", "again", "against", "all", "and", "any", "are", "aren", "because",
    "been", "before", "being", "below", "between", "both", "but", "can", "cannot", "could", "did",
    "didn", "does", "doesn", "doing", "don", "down", "during", "each", "few", "for", "from", "further",
    "had", "hadn", "has", "hasn", "have", "haven", "having", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "into", "its", "itself", "just", "more", "most", "myself", "nor",
    "not", "now", "off", "once", "only", "other", "our", "ours", "ourselves", "out", "over", "own",
    "same", "she", "should", "shouldn", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "themselves", "then", "there", "these", "they", "this", "those", "through", "too", "under",
    "until", "very", "was", "wasn", "were", "weren", "what", "when", "where", "which", "while",
    "who", "whom", "why", "will", "with", "won", "would", "wouldn", "you", "your", "yours",
    "yourself", "yourselves",
})


def filter_stopwords(tags: list[str]) -> list[str]:
    return [t for t in tags if t.lower() not in STOPWORDS]


def parse_tags(raw: str | list[str]) -> list[str]:
    chunks = [raw] if isinstance(raw, str) else raw
    seen: set[str] = set()
    normalized_tags: list[str] = []

    for chunk in chunks:
        for part in re.split(r"[,;]+", chunk):
            cleaned = re.sub(r"\s+", "", part.strip().lower())
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                normalized_tags.append(cleaned)

    return normalized_tags


def tags_overlap(tags_a: list[str], tags_b: list[str]) -> bool:
    return count_tags_overlap(tags_a, tags_b) >= 1


def count_tags_overlap(tags_a: list[str], tags_b: list[str]) -> int:
    set_a = {tag.strip().lower() for tag in tags_a if tag and tag.strip()}
    set_b = {tag.strip().lower() for tag in tags_b if tag and tag.strip()}
    return len(set_a & set_b)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    char_based = math.ceil(len(text) / 3.2)
    word_based = math.ceil(len(text.split()) * 1.35)
    return max(char_based, word_based)


def extract_first_sentence(text: str, max_chars: int = 180) -> str:
    if not text or not text.strip():
        return ""
    cleaned = re.sub(r"\s+", " ", text.strip())
    match = re.match(r"^(.+?[.!?])(?:\s|$)", cleaned)
    first_sent = match.group(1).strip() if match else cleaned
    if len(first_sent) <= max_chars:
        return first_sent
    truncated = first_sent[:max_chars].rsplit(" ", 1)[0].rstrip(",;:-")
    return f"{truncated}..."


_SPEECH_QUOTE_RE = re.compile(r'(?:["“”„‟«»].+?["“”„‟«»])', re.DOTALL)
_ACTION_BLOCK_RE = re.compile(r"\*([^*]+)\*", re.DOTALL)


def _condense_action_block(match: re.Match, max_len: int = 100) -> str:
    inner = re.sub(r"\s+", " ", match.group(1).strip())
    if not inner:
        return ""
    if len(inner) <= max_len:
        return f"*{inner}*"
    short_sent = extract_first_sentence(inner, max_chars=max_len)
    return f"*{short_sent}*"


def distill_message_dialogue(text: str, max_chars: int = 380) -> str:
    if not text or not text.strip():
        return ""
    raw = text.strip()
    if len(raw) <= max_chars:
        return raw

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n", raw) if p.strip()]
    distilled_parts: list[str] = []

    for idx, para in enumerate(paragraphs):
        has_speech = bool(_SPEECH_QUOTE_RE.search(para))
        if has_speech:
            condensed = _ACTION_BLOCK_RE.sub(
                lambda m: _condense_action_block(m, max_len=75),
                para,
            )
            distilled_parts.append(re.sub(r"\s+", " ", condensed).strip())
        elif idx == 0 and not distilled_parts:
            first_action = _ACTION_BLOCK_RE.search(para)
            if first_action:
                distilled_parts.append(_condense_action_block(first_action, max_len=75))

    combined = " ".join(distilled_parts) if distilled_parts else re.sub(r"\s+", " ", raw)
    if len(combined) <= max_chars:
        return combined

    half = (max_chars - 5) // 2
    head = combined[:half].rsplit(" ", 1)[0].rstrip(",;:-")
    tail = combined[-half:].split(" ", 1)[-1].lstrip(",;:-")
    return f"{head} [...] {tail}"


def sanitize_filename(filename: str) -> str:
    replaced = "".join(_UMLAUT_MAP.get(ch, ch) for ch in filename.strip())
    normalized = (
        unicodedata.normalize("NFKD", replaced)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized).strip("._-")
    return sanitized or "unnamed_file"


_CHAR_PLACEHOLDER_RE = re.compile(r"\{\{\s*char\s*\}\}|\{\s*char\s*\}", re.IGNORECASE)
_USER_PLACEHOLDER_RE = re.compile(r"\{\{\s*user\s*\}\}|\{\s*user\s*\}", re.IGNORECASE)

_CHAR_GENDER_RE = re.compile(r"\{\{\s*char_gender\s*\}\}|\{\s*char_gender\s*\}", re.IGNORECASE)
_USER_GENDER_RE = re.compile(r"\{\{\s*user_gender\s*\}\}|\{\s*user_gender\s*\}", re.IGNORECASE)

_CHAR_PRONOUNS_RE = re.compile(r"\{\{\s*char_pronouns\s*\}\}|\{\s*char_pronouns\s*\}", re.IGNORECASE)
_USER_PRONOUNS_RE = re.compile(r"\{\{\s*user_pronouns\s*\}\}|\{\s*user_pronouns\s*\}", re.IGNORECASE)

_CHAR_SUBJECT_RE = re.compile(r"\{\{\s*char_subject\s*\}\}|\{\s*char_subject\s*\}", re.IGNORECASE)
_USER_SUBJECT_RE = re.compile(r"\{\{\s*user_subject\s*\}\}|\{\s*user_subject\s*\}", re.IGNORECASE)

_CHAR_OBJECT_RE = re.compile(r"\{\{\s*char_object\s*\}\}|\{\s*char_object\s*\}", re.IGNORECASE)
_USER_OBJECT_RE = re.compile(r"\{\{\s*user_object\s*\}\}|\{\s*user_object\s*\}", re.IGNORECASE)

_CHAR_POSSESSIVE_RE = re.compile(r"\{\{\s*char_possessive\s*\}\}|\{\s*char_possessive\s*\}", re.IGNORECASE)
_USER_POSSESSIVE_RE = re.compile(r"\{\{\s*user_possessive\s*\}\}|\{\s*user_possessive\s*\}", re.IGNORECASE)


def get_gender_forms(gender: str | None) -> dict[str, str]:
    raw = (gender or "").strip().lower()
    if raw == "female":
        return {
            "gender": "female",
            "pronouns": "she/her",
            "subject": "she",
            "object": "her",
            "possessive": "her",
        }
    elif raw == "male":
        return {
            "gender": "male",
            "pronouns": "he/him",
            "subject": "he",
            "object": "him",
            "possessive": "his",
        }
    else:
        return {
            "gender": raw or "non-binary",
            "pronouns": "they/them",
            "subject": "they",
            "object": "them",
            "possessive": "their",
        }


def replace_roleplay_placeholders(
    text: str,
    character_name: str,
    persona_name: str,
    character_gender: str | None = None,
    persona_gender: str | None = None,
) -> str:
    if not text:
        return ""
    result = _CHAR_PLACEHOLDER_RE.sub(character_name, text)
    result = _USER_PLACEHOLDER_RE.sub(persona_name, result)

    if character_gender is not None:
        c_forms = get_gender_forms(character_gender)
        result = _CHAR_GENDER_RE.sub(c_forms["gender"], result)
        result = _CHAR_PRONOUNS_RE.sub(c_forms["pronouns"], result)
        result = _CHAR_SUBJECT_RE.sub(c_forms["subject"], result)
        result = _CHAR_OBJECT_RE.sub(c_forms["object"], result)
        result = _CHAR_POSSESSIVE_RE.sub(c_forms["possessive"], result)

    if persona_gender is not None:
        u_forms = get_gender_forms(persona_gender)
        result = _USER_GENDER_RE.sub(u_forms["gender"], result)
        result = _USER_PRONOUNS_RE.sub(u_forms["pronouns"], result)
        result = _USER_SUBJECT_RE.sub(u_forms["subject"], result)
        result = _USER_OBJECT_RE.sub(u_forms["object"], result)
        result = _USER_POSSESSIVE_RE.sub(u_forms["possessive"], result)

    return result
