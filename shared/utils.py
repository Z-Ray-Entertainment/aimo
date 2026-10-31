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
