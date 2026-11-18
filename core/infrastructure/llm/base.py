import json
import re

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
        )
        raw_output = self.generate(
            prompt=prompt, model=model, params=classification_params, think=False
        )
        return self._match_candidate(raw_output, cleaned_candidates)

    def classify_turn(
        self,
        text: str,
        emotion_candidates: list[str] | None,
        location_candidates: list[str] | None,
        model: str,
    ) -> tuple[str, str | None]:
        clean_emotions = [e.strip() for e in (emotion_candidates or []) if e.strip()]
        clean_locs = [l.strip() for l in (location_candidates or []) if l.strip()]

        if not clean_emotions and not clean_locs:
            return "neutral", None

        if clean_emotions and not clean_locs:
            detected_emotion = self.classify(text=text, candidates=clean_emotions, model=model)
            return detected_emotion, None

        if clean_locs and not clean_emotions:
            raw_loc = self.classify(text=text, candidates=clean_locs, model=model)
            loc_matched = self._match_candidate(raw_loc, clean_locs)
            matched_loc = None if loc_matched.lower() == "stay_here" else loc_matched
            return "neutral", matched_loc

        emotions_str = ", ".join(clean_emotions)
        locs_str = ", ".join(clean_locs)
        prompt = (
            "Analyze the narrative response and classify two attributes strictly in JSON format:\n"
            f"1. 'emotion': strictly choose one emotion label from: [{emotions_str}]\n"
            f"2. 'location': strictly choose one location label from: [{locs_str}] (choose 'stay_here' if no explicit relocation or journey was decided or proposed)\n\n"
            f"Passage:\n{text}\n\n"
            'Respond ONLY with a valid JSON object of the exact shape: {"emotion": "...", "location": "..."}'
        )
        classification_params = ModelParameters(
            num_ctx=2048,
            temperature=0.0,
            top_p=0.9,
            repeat_penalty=1.0,
        )
        raw_emotion = "neutral"
        raw_loc = "stay_here"
        try:
            raw_output = self.generate(
                prompt=prompt,
                model=model,
                params=classification_params,
                format="json",
                think=False,
            )
            data = json.loads(raw_output)
            raw_emotion = str(data.get("emotion", "")).strip()
            raw_loc = str(data.get("location", "")).strip()
        except Exception:
            try:
                raw_output = self.generate(
                    prompt=prompt,
                    model=model,
                    params=classification_params,
                    think=False,
                )
                start = raw_output.find("{")
                end = raw_output.rfind("}")
                if start != -1 and end != -1:
                    data = json.loads(raw_output[start : end + 1])
                    raw_emotion = str(data.get("emotion", "")).strip()
                    raw_loc = str(data.get("location", "")).strip()
            except Exception:
                raw_emotion = "neutral"
                raw_loc = "stay_here"

        detected_emotion = self._match_candidate(raw_emotion, clean_emotions)
        detected_loc = self._match_candidate(raw_loc, clean_locs)
        return detected_emotion, (detected_loc if detected_loc != "stay_here" else None)

    @staticmethod
    def _ensure_ok(response: requests.Response, context: str) -> None:
        if response.status_code >= 400:
            detail = response.text.strip()
            raise InfrastructureError(
                f"{context} failed with HTTP {response.status_code}: {detail}"
            )

    @staticmethod
    def _match_candidate(raw_output: str, candidates: list[str]) -> str:
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

        return candidates[0]
