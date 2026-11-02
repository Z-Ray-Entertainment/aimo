from markupsafe import Markup, escape


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
