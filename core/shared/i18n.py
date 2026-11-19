from __future__ import annotations

import ast
import gettext
import struct
from pathlib import Path
from threading import Lock

LOCALES_DIR = Path(__file__).resolve().parents[2] / "core" / "locales"
_TRANSLATOR_CACHE: dict[str, tuple[float, gettext.NullTranslations]] = {}
_CACHE_LOCK = Lock()


def normalize_language(raw: str | None, default: str = "en") -> str:
    if not isinstance(raw, str):
        return default
    cleaned = raw.strip().lower()[:2]
    return cleaned if cleaned else default


def get_translator(language: str | None = "en") -> gettext.NullTranslations:
    lang = normalize_language(language, default="en")
    mo_path = LOCALES_DIR / lang / "LC_MESSAGES" / "messages.mo"
    mtime = mo_path.stat().st_mtime if mo_path.is_file() else 0.0
    with _CACHE_LOCK:
        cached = _TRANSLATOR_CACHE.get(lang)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        translator = gettext.translation(
            "messages",
            localedir=str(LOCALES_DIR),
            languages=[lang],
            fallback=True,
        )
        _TRANSLATOR_CACHE[lang] = (mtime, translator)
        return translator


def clear_translator_cache() -> None:
    with _CACHE_LOCK:
        _TRANSLATOR_CACHE.clear()


def _parse_po(po_path: Path) -> dict[str, str]:
    catalog: dict[str, str] = {}
    cur_key: str | None = None
    cur_msgid = ""
    cur_msgstr = ""

    def _flush() -> None:
        if cur_msgid or cur_msgstr:
            catalog[cur_msgid] = cur_msgstr

    for raw_line in po_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("msgid "):
            _flush()
            cur_key = "msgid"
            cur_msgid = ast.literal_eval(line[6:].strip())
            cur_msgstr = ""
        elif line.startswith("msgstr "):
            cur_key = "msgstr"
            cur_msgstr = ast.literal_eval(line[7:].strip())
        elif line.startswith('"') and line.endswith('"'):
            part = ast.literal_eval(line)
            if cur_key == "msgid":
                cur_msgid += part
            elif cur_key == "msgstr":
                cur_msgstr += part
    _flush()
    return catalog


def _compile_mo(po_path: Path, mo_path: Path) -> None:
    catalog = _parse_po(po_path)
    items = sorted(
        (k.encode("utf-8"), v.encode("utf-8"))
        for k, v in catalog.items()
        if v
    )
    if "" in catalog:
        header_bytes = catalog[""].encode("utf-8")
        items = [(b"", header_bytes)] + [(k, v) for k, v in items if k != b""]
    n = len(items)
    keystart = 7 * 4 + 16 * n
    valuestart = keystart + sum(len(k) + 1 for k, _ in items)
    koffsets: list[tuple[int, int]] = []
    voffsets: list[tuple[int, int]] = []
    kbytes = bytearray()
    vbytes = bytearray()
    for k, v in items:
        koffsets.append((len(k), keystart + len(kbytes)))
        kbytes.extend(k + b"\x00")
        voffsets.append((len(v), valuestart + len(vbytes)))
        vbytes.extend(v + b"\x00")
    header = struct.pack("Iiiiiii", 0x950412DE, 0, n, 7 * 4, 7 * 4 + 8 * n, 0, 0)
    otable = bytearray()
    for length, offset in koffsets:
        otable.extend(struct.pack("ii", length, offset))
    ttable = bytearray()
    for length, offset in voffsets:
        ttable.extend(struct.pack("ii", length, offset))
    mo_path.write_bytes(header + otable + ttable + kbytes + vbytes)


def ensure_compiled_locales(locales_dir: Path | None = None) -> int:
    base = locales_dir or LOCALES_DIR
    if not base.is_dir():
        return 0
    compiled = 0
    for po_path in base.glob("*/LC_MESSAGES/messages.po"):
        mo_path = po_path.with_suffix(".mo")
        if not mo_path.is_file() or po_path.stat().st_mtime > mo_path.stat().st_mtime:
            _compile_mo(po_path, mo_path)
            compiled += 1
    if compiled:
        clear_translator_cache()
    return compiled


def t(msgid: str, language: str | None = "en") -> str:
    if not msgid:
        return msgid
    lang = normalize_language(language, default="en")
    if lang == "en":
        return msgid
    return get_translator(lang).gettext(msgid)


def tn(singular: str, plural: str, n: int, language: str | None = "en") -> str:
    lang = normalize_language(language, default="en")
    if lang == "en":
        return singular if n == 1 else plural
    return get_translator(lang).ngettext(singular, plural, n)


def gettext_noop(msgid: str) -> str:
    return msgid
