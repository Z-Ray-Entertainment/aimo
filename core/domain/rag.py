from __future__ import annotations

from typing import Callable, Iterable, TypeVar

from shared.utils import count_tags_overlap

T = TypeVar("T")


def score_and_rank_tagged_items(
    items: Iterable[T],
    *,
    get_tags: Callable[[T], list[str]],
    get_text_parts: Callable[[T], Iterable[str]],
    get_order_key: Callable[[T], int | float],
    active_tags: list[str],
    latest_user_tags: list[str] | None = None,
    focus_keywords: set[str] | None = None,
    extra_bonus_fn: Callable[[T], float] | None = None,
    max_results: int = 5,
) -> list[T]:
    if not active_tags and not focus_keywords:
        return []

    latest_set = {t.strip().lower() for t in (latest_user_tags or []) if t.strip()}
    focus_set = {k.strip().lower() for k in (focus_keywords or set()) if k.strip()}
    scored: list[tuple[float, int | float, T]] = []

    for item in items:
        item_tags = get_tags(item)
        overlap = count_tags_overlap(active_tags, item_tags)
        freshness = count_tags_overlap(list(latest_set), item_tags) if latest_set else 0

        focus_hit = 0
        if focus_set:
            text_blob = " ".join(part.lower() for part in get_text_parts(item) if part)
            focus_hit = sum(1 for kw in focus_set if kw in text_blob)

        if overlap > 0 or focus_hit > 0:
            bonus = extra_bonus_fn(item) if extra_bonus_fn is not None else 0.0
            score = (overlap * 10.0) + (freshness * 20.0) + (focus_hit * 8.0) + bonus
            scored.append((score, get_order_key(item), item))

    scored.sort(key=lambda pair: (pair[0], pair[1]), reverse=True)
    return [pair[2] for pair in scored[:max_results]]
