#!/usr/bin/env python3
"""Zero-dependency gettext .pot/.po/.mo manager for AIMO (Core + Flask)."""
from __future__ import annotations

import argparse
import ast
import re
import struct
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_LOCALES_DIR = PROJECT_ROOT / "core" / "locales"
FLASK_LOCALES_DIR = PROJECT_ROOT / "flask" / "locales"

SUPPORTED_LANGUAGES = (
    "en", "zh", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur",
    "id", "de", "ja", "tr", "ko", "vi", "it", "pl", "nl", "th",
)

TEMPLATE_GETTEXT_RE = re.compile(
    r"""\b(?:_|gettext)\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')\s*[,)]"""
)


_UNESCAPE_MAP = {"\\n": "\n", "\\t": "\t", "\\r": "\r", '\\"': '"', "\\'": "'", "\\\\": "\\"}
_UNESCAPE_RE = re.compile(r'\\([\\ntr"\'])')


def _unescape_py(raw: str) -> str:
    return _UNESCAPE_RE.sub(lambda m: _UNESCAPE_MAP[m.group(0)], raw)


def _escape_po(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\t", "\\t")
        .replace("\n", "\\n")
    )


def _format_po_entry(keyword: str, text: str) -> str:
    if "\n" not in text:
        return f'{keyword} "{_escape_po(text)}"\n'
    lines = text.split("\n")
    out = f'{keyword} ""\n'
    for idx, line in enumerate(lines):
        suffix = "\\n" if idx < len(lines) - 1 else ""
        out += f'"{_escape_po(line)}{suffix}"\n'
    return out


def extract_msgids(scope: str = "all") -> dict[str, list[str]]:
    entries: dict[str, list[str]] = {}

    def _add(msgid: str, ref: str) -> None:
        if not msgid:
            return
        entries.setdefault(msgid, [])
        if ref not in entries[msgid]:
            entries[msgid].append(ref)

    py_roots = []
    if scope in ("core", "all"):
        py_roots.append(PROJECT_ROOT / "core")
    if scope in ("flask", "all"):
        py_roots.append(PROJECT_ROOT / "flask")

    for py_root in py_roots:
        for py_file in sorted(py_root.rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue
            src = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(src, filename=str(py_file))
            except SyntaxError:
                continue
            rel = py_file.relative_to(PROJECT_ROOT).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    if func_name in ("_", "gettext", "gettext_noop") and node.args:
                        arg0 = node.args[0]
                        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                            _add(arg0.value, f"{rel}:{node.lineno}")

    if scope in ("flask", "all"):
        tpl_root = PROJECT_ROOT / "flask" / "templates"
        for html_file in sorted(tpl_root.rglob("*.html")):
            src = html_file.read_text(encoding="utf-8")
            rel = html_file.relative_to(PROJECT_ROOT).as_posix()
            for lineno, line in enumerate(src.splitlines(), start=1):
                for match in TEMPLATE_GETTEXT_RE.finditer(line):
                    raw = match.group(1) if match.group(1) is not None else match.group(2)
                    try:
                        _add(_unescape_py(raw), f"{rel}:{lineno}")
                    except Exception:
                        _add(raw, f"{rel}:{lineno}")

    return entries


def write_pot(entries: dict[str, list[str]], locales_dir: Path) -> None:
    locales_dir.mkdir(parents=True, exist_ok=True)
    pot_path = locales_dir / "messages.pot"
    header = (
        'msgid ""\n'
        'msgstr ""\n'
        '"Project-Id-Version: AIMO 1.0\\n"\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Content-Transfer-Encoding: 8bit\\n"\n\n'
    )
    chunks = [header]
    for msgid, refs in entries.items():
        ref_line = "#: " + " ".join(refs[:5]) + "\n"
        chunks.append(ref_line + _format_po_entry("msgid", msgid) + 'msgstr ""\n\n')
    pot_path.write_text("".join(chunks), encoding="utf-8")
    print(f"Extracted {len(entries)} messages to {pot_path}")


def parse_po(po_path: Path) -> dict[str, str]:
    if not po_path.is_file():
        return {}
    content = po_path.read_text(encoding="utf-8")
    catalog: dict[str, str] = {}
    cur_key: str | None = None
    cur_msgid = ""
    cur_msgstr = ""

    def _flush() -> None:
        if cur_msgid or cur_msgstr:
            catalog[cur_msgid] = cur_msgstr

    for raw_line in content.splitlines():
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


def update_po_files(entries: dict[str, list[str]], locales_dir: Path, seed_from: Path | None = None) -> None:
    for lang in SUPPORTED_LANGUAGES:
        po_dir = locales_dir / lang / "LC_MESSAGES"
        po_dir.mkdir(parents=True, exist_ok=True)
        po_path = po_dir / "messages.po"
        existing = parse_po(po_path)
        if not existing and seed_from is not None:
            existing = parse_po(seed_from / lang / "LC_MESSAGES" / "messages.po")
        header = (
            'msgid ""\n'
            'msgstr ""\n'
            f'"Language: {lang}\\n"\n'
            '"Content-Type: text/plain; charset=UTF-8\\n"\n'
            '"Content-Transfer-Encoding: 8bit\\n"\n\n'
        )
        chunks = [header]
        for msgid, refs in entries.items():
            translated = existing.get(msgid, "")
            if lang == "en" and not translated:
                translated = msgid
            ref_line = "#: " + " ".join(refs[:5]) + "\n"
            chunks.append(
                ref_line
                + _format_po_entry("msgid", msgid)
                + _format_po_entry("msgstr", translated)
                + "\n"
            )
        po_path.write_text("".join(chunks), encoding="utf-8")
    print(f"Updated .po files in {locales_dir} for {len(SUPPORTED_LANGUAGES)} languages.")


def compile_mo(po_path: Path, mo_path: Path) -> None:
    catalog = parse_po(po_path)
    items = sorted(
        (k.encode("utf-8"), v.encode("utf-8"))
        for k, v in catalog.items()
        if v
    )
    # Include header if present
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

    header = struct.pack(
        "Iiiiiii",
        0x950412DE,
        0,
        n,
        7 * 4,
        7 * 4 + 8 * n,
        0,
        0,
    )
    otable = bytearray()
    for length, offset in koffsets:
        otable.extend(struct.pack("ii", length, offset))
    ttable = bytearray()
    for length, offset in voffsets:
        ttable.extend(struct.pack("ii", length, offset))

    mo_path.write_bytes(header + otable + ttable + kbytes + vbytes)


def compile_all(locales_dir: Path) -> None:
    count = 0
    for lang in SUPPORTED_LANGUAGES:
        po_path = locales_dir / lang / "LC_MESSAGES" / "messages.po"
        if po_path.is_file():
            mo_path = po_path.with_suffix(".mo")
            compile_mo(po_path, mo_path)
            count += 1
    print(f"Compiled {count} .mo catalogs in {locales_dir}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="AIMO gettext i18n tool")
    parser.add_argument("command", choices=["extract", "update", "compile", "all"])
    parser.add_argument("--seed-from", default="", help="Optional legacy locales dir to seed existing translations")
    args = parser.parse_args()
    seed_dir = Path(args.seed_from) if args.seed_from else None

    for scope, locales_dir in (("core", CORE_LOCALES_DIR), ("flask", FLASK_LOCALES_DIR)):
        if args.command in ("extract", "all"):
            entries = extract_msgids(scope)
            write_pot(entries, locales_dir)
        if args.command in ("update", "all"):
            entries = extract_msgids(scope)
            update_po_files(entries, locales_dir, seed_from=seed_dir)
        if args.command in ("compile", "all"):
            compile_all(locales_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
