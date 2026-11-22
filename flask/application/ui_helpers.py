from urllib.parse import urlparse
from flask import flash, g, request
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


def tr(msgid: str, language: str | None = None, **kwargs: object) -> str:
    from i18n import t

    lang = language or getattr(g, "ui_language", "en")
    text = t(msgid, lang)
    return text % kwargs if kwargs else text


def notify_author_translation_hint(entity_type: str, entity_id: int | None, field_name: str) -> None:
    if not entity_id:
        return
    import requests as http_requests
    from application.core_client import build_core_headers, get_core_base_url
    from i18n import gettext_noop as _, t

    try:
        resp = http_requests.post(
            f"{get_core_base_url()}/api/admin/translations/notify",
            json={"entity_type": entity_type, "entity_id": entity_id, "field_name": field_name},
            headers=build_core_headers(),
            timeout=2,
        )
        if resp.ok:
            data = resp.json()
            if data.get("is_cloud") and data.get("has_missing"):
                lang = getattr(g, "ui_language", "en")
                flash(
                    t(
                        _("Cloud AI mode: automatic background translation is disabled. Use the greyed-out flag pill-badges to translate into other registered user languages."),
                        lang,
                    ),
                    "info",
                )
    except Exception:
        pass
