from urllib.parse import urlparse
from flask import request
from markupsafe import Markup, escape


def get_safe_back_url(fallback: str) -> str:
    """Return a safe relative URL to navigate back to, or the provided fallback."""
    candidate = request.args.get("return_to") or request.form.get("return_to")

    # If no candidate, try the Referer header
    if not candidate and request.referrer:
        try:
            ref_parsed = urlparse(request.referrer)
            req_parsed = urlparse(request.url)
            # Verify same host / domain
            if (not ref_parsed.netloc or ref_parsed.netloc == req_parsed.netloc) and ref_parsed.path != req_parsed.path:
                candidate = ref_parsed.path
                if ref_parsed.query:
                    candidate += f"?{ref_parsed.query}"
        except Exception:
            candidate = None

    if candidate:
        candidate = candidate.strip()
        # Ensure it is a safe relative local path (prevents open redirects)
        if candidate.startswith("/") and not candidate.startswith("//"):
            return candidate

    return fallback


def mask_secret(raw: str | None) -> str:
    """Return a masked hint for an API key or secret without exposing it."""
    cleaned = (raw or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) <= 8:
        return "••••••••"
    return f"••••{cleaned[-4:]}"


def render_new_button(
    text: str,
    href: str | None = None,
    modal: str | None = None,
    onclick: str | None = None,
    min_height: str | None = None,
    extra_class: str = "",
    id: str | None = None,
    title: str | None = None,
) -> Markup:
    style_attr = f' style="min-height: {escape(min_height)};"' if min_height else ""
    id_attr = f' id="{escape(id)}"' if id else ""
    title_attr = f' title="{escape(title)}"' if title else ""
    class_attr = f"aimo-add-card-tile {escape(extra_class)}".strip()

    if href:
        return Markup(
            f'<a href="{escape(href)}" class="{class_attr}"{id_attr}{title_attr}{style_attr}>\n'
            f'  <div class="plus-symbol">+</div>\n'
            f'  <div class="tile-label">{escape(text)}</div>\n'
            f'</a>'
        )
    modal_attr = f' data-modal-open="{escape(modal)}"' if modal else ""
    onclick_attr = f' onclick="{escape(onclick)}"' if onclick else ""
    return Markup(
        f'<button type="button" class="{class_attr}"{id_attr}{title_attr}{modal_attr}{onclick_attr}{style_attr}>\n'
        f'  <div class="plus-symbol">+</div>\n'
        f'  <div class="tile-label">{escape(text)}</div>\n'
        f'</button>'
    )
