import json
import re
from typing import Any

import requests

from domain.settings.models import ModelParameters
from infrastructure.llm.interface import LLMProvider
from shared.exceptions import InfrastructureError


class BaseLLMProvider(LLMProvider):
    """Shared classification and HTTP validation behavior across LLM providers."""

    def classify(self, text: str, candidates: list[str], model: str) -> str:
        cleaned_candidates = [c.strip() for c in candidates if c.strip()]
        if not cleaned_candidates:
            raise InfrastructureError(
                "Classification requires at least one non-empty candidate label."
            )

        candidates_str = ", ".join(cleaned_candidates)
        prompt = (
            "Classify the following narrative passage by choosing strictly one label "
            f"from the valid candidates: [{candidates_str}].\n"
            "Respond with ONLY the exact candidate label and nothing else.\n\n"
            f"Passage:\n{text}\n\n"
            "Selected label:"
        )
        classification_params = ModelParameters(
            num_ctx=2048,
            temperature=0.0,
            top_p=0.9,
            repeat_penalty=1.0,
            max_tokens=24,
        )
        raw_output = self.generate(
            prompt=prompt, model=model, params=classification_params, think=False
        )
        return self._match_candidate(raw_output, cleaned_candidates)

    _RELATIONSHIP_IMPACT_CANDIDATES: tuple[str, ...] = (
        "neutral",
        "positive",
        "negative",
        "very_positive",
        "very_negative",
    )

    def _generate_json_dict(
        self,
        prompt: str,
        model: str,
        params: ModelParameters,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        format_attempts: list[str | dict[str, Any] | None] = (
            [schema, "json", None] if schema is not None else ["json", None]
        )
        for fmt in format_attempts:
            try:
                raw_output = self.generate(
                    prompt=prompt,
                    model=model,
                    params=params,
                    format=fmt,
                    think=False,
                )
                if fmt is not None:
                    data = json.loads(raw_output)
                else:
                    start = raw_output.find("{")
                    end = raw_output.rfind("}")
                    if start == -1 or end == -1:
                        continue
                    data = json.loads(raw_output[start : end + 1])
                if isinstance(data, dict):
                    return {str(k): str(v).strip() for k, v in data.items() if v is not None}
            except Exception:
                continue

        return {}

    def classify_turn(
        self,
        text: str,
        emotion_candidates: list[str] | None,
        location_candidates: list[str] | None,
        model: str,
        user_text: str | None = None,
        character_name: str | None = None,
        relationship_tier: str | None = None,
        evaluate_relationship: bool = False,
        num_ctx: int = 2048,
    ) -> tuple[str, str | None, str]:
        clean_emotions = [e.strip() for e in (emotion_candidates or []) if e.strip()]
        clean_locs = [l.strip() for l in (location_candidates or []) if l.strip()]

        # Compact keys ('e', 'l', 'r') minimize output tokens while keeping semantic enum values.
        fields: list[tuple[str, str, str, list[str], str]] = []
        if clean_emotions:
            emotions_str = ", ".join(clean_emotions)
            fields.append(
                (
                    "e",
                    "emotion",
                    f"choose one from [{emotions_str}]",
                    clean_emotions,
                    "neutral",
                )
            )
        if clean_locs:
            locs_str = ", ".join(clean_locs)
            fields.append(
                (
                    "l",
                    "location",
                    (
                        f"DEFAULT 'stay_here'. Choose from [{locs_str}]: "
                        "ONLY pick another location if characters explicitly move to, enter, or propose going there RIGHT NOW in this turn "
                        "(ignore mentions, memories, metaphors, distant plans; if unsure, ALWAYS 'stay_here')"
                    ),
                    clean_locs,
                    "stay_here",
                )
            )
        if evaluate_relationship:
            impact_list = ", ".join(self._RELATIONSHIP_IMPACT_CANDIDATES)
            fields.append(
                (
                    "r",
                    "relationship_impact",
                    (
                        f"judge ONLY if character grew closer to or more distant from player this turn; choose from [{impact_list}]. "
                        "IMPORTANT: Sadness, fear, pain, or vulnerability confided IN player shows trust/intimacy (positive/very_positive), NOT negative. "
                        "Default 'neutral' if unsure. "
                        "(neutral=normal/factual or playful/spicy without hostility toward player; "
                        "positive=warmth, affection, flirting, humor, appreciation, trusting openness; "
                        "negative=mild annoyance, coldness, irritation AT player; "
                        "very_positive=deep vulnerability, confession, devotion, loyalty, heartfelt connection; "
                        "very_negative=clearly rejects, despises, or is furious AT player)"
                    ),
                    list(self._RELATIONSHIP_IMPACT_CANDIDATES),
                    "neutral",
                )
            )

        if not fields:
            return "neutral", None, "neutral"

        if len(fields) == 1 and fields[0][0] != "r":
            key, _, _, candidates, _ = fields[0]
            matched = self.classify(text=text, candidates=candidates, model=model)
            if key == "e":
                return matched, None, "neutral"
            return "neutral", (None if matched.lower() == "stay_here" else matched), "neutral"

        instructions = "\n".join(
            f"{idx}. '{key}' ({label}): {instruction}"
            for idx, (key, label, instruction, _, _) in enumerate(fields, start=1)
        )
        json_shape = ", ".join(f'"{key}":"..."' for key, _, _, _, _ in fields)
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                key: {"type": "string", "enum": candidates}
                for key, _, _, candidates, _ in fields
            },
            "required": [key for key, _, _, _, _ in fields],
            "additionalProperties": False,
        }

        context_lines: list[str] = []
        if evaluate_relationship:
            char_label = character_name.strip() if character_name and character_name.strip() else "Character"
            context_lines.append(f"Character: {char_label}")
            if user_text and user_text.strip():
                context_lines.append(f"Player message:\n{user_text.strip()}")
            context_lines.append(f"Character reply:\n{text}")
        else:
            context_lines.append(f"Passage:\n{text}")

        prompt = (
            "Analyze the narrative turn and output ONLY valid JSON:\n"
            f"{instructions}\n"
            f"JSON shape: {{{json_shape}}}\n\n"
            + "\n\n".join(context_lines)
        )
        classification_params = ModelParameters(
            num_ctx=num_ctx,
            temperature=0.0,
            top_p=0.9,
            repeat_penalty=1.0,
            max_tokens=96,
        )
        data = self._generate_json_dict(
            prompt=prompt,
            model=model,
            params=classification_params,
            schema=schema,
        )

        results: dict[str, str] = {}
        for key, _, _, candidates, default_val in fields:
            raw_val = data.get(key, default_val)
            if key == "r":
                raw_val = raw_val.strip().lower().replace("-", "_").replace(" ", "_")
            results[key] = self._match_candidate(raw_val, candidates, default=default_val)

        detected_emotion = results.get("e", "neutral")
        raw_loc_val = data.get("l", "stay_here").strip().lower().replace(" ", "_")
        if raw_loc_val in ("", "none", "null", "n/a", "stay_here", "current", "current_location"):
            matched_loc = None
        else:
            detected_loc = results.get("l")
            matched_loc = None if not detected_loc or detected_loc.lower() == "stay_here" else detected_loc
        detected_impact = results.get("r", "neutral")
        return detected_emotion, matched_loc, detected_impact

    @staticmethod
    def _ensure_ok(response: requests.Response, context: str) -> None:
        if response.status_code >= 400:
            detail = response.text.strip()
            raise InfrastructureError(
                f"{context} failed with HTTP {response.status_code}: {detail}"
            )

    @staticmethod
    def _match_candidate(
        raw_output: str, candidates: list[str], default: str | None = None
    ) -> str:
        normalized_output = raw_output.strip().strip("`'\".,:;!?()[]{}").lower()
        lower_map = {candidate.lower(): candidate for candidate in candidates}

        if normalized_output in lower_map:
            return lower_map[normalized_output]

        for candidate in candidates:
            pattern = rf"\b{re.escape(candidate.lower())}\b"
            if re.search(pattern, normalized_output):
                return candidate

        for candidate in candidates:
            if candidate.lower() in normalized_output:
                return candidate

        return default if default is not None else candidates[0]
