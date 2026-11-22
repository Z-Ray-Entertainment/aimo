from pathlib import Path

from rcssmin import cssmin
from rjsmin import jsmin


def ensure_minified_assets(static_dir: Path) -> None:
    """Ensure minified CSS and JS assets exist in static_dir/.min and stay up to date."""
    min_root = static_dir / ".min"
    targets = [
        (static_dir / "css", "*.css", cssmin),
        (static_dir / "js", "*.js", jsmin),
    ]

    for src_dir, pattern, minifier in targets:
        if not src_dir.is_dir():
            continue
        for src_file in src_dir.rglob(pattern):
            rel_path = src_file.relative_to(static_dir)
            out_file = min_root / rel_path
            if out_file.exists() and out_file.stat().st_mtime >= src_file.stat().st_mtime:
                continue
            out_file.parent.mkdir(parents=True, exist_ok=True)
            content = src_file.read_text(encoding="utf-8")
            out_file.write_text(minifier(content), encoding="utf-8")
