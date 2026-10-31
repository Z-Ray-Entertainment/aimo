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
    set_a = {tag.strip().lower() for tag in tags_a if tag.strip()}
    set_b = {tag.strip().lower() for tag in tags_b if tag.strip()}
    return len(set_a & set_b) >= 1


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
