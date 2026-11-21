import json
import re
from typing import Any

from domain.base import TextGenerationProvider, utc_now
from domain.memories.exceptions import InvalidMemoryDataError
from domain.memories.models import Memory
from domain.rag import score_and_rank_tagged_items
from domain.settings.models import ModelParameters
from domain.validation import DomainValidator
from shared.utils import parse_tags

MemoryLLMProvider = TextGenerationProvider


class MemoryService:
    def should_generate_memory(self, unsummarized_message_count: int) -> bool:
        return unsummarized_message_count >= 10

    def create_memory(
        self,
        chat_session_id: int,
        message_idx: int,
        title: str,
        tags: list[str] | str,
        summary: str,
    ) -> Memory:
        DomainValidator.validate_positive_id(chat_session_id, "chat_session_id", InvalidMemoryDataError)
        if isinstance(message_idx, bool) or not isinstance(message_idx, int) or message_idx < 0:
            raise InvalidMemoryDataError("message_idx must be a non-negative integer.")

        cleaned_title = DomainValidator.validate_required_string(title, "Memory title", InvalidMemoryDataError)
        normalized_tags = parse_tags(tags)
        cleaned_summary = DomainValidator.validate_required_string(summary, "Memory summary", InvalidMemoryDataError)

        now = utc_now()
        return Memory(
            id=None,
            chat_session_id=chat_session_id,
            message_idx=message_idx,
            title=cleaned_title,
            tags=normalized_tags,
            summary=cleaned_summary,
            created_at=now,
            updated_at=now,
        )

    def update_memory(
        self,
        memory: Memory,
        title: str,
        tags: list[str] | str,
        summary: str,
    ) -> Memory:
        memory.title = DomainValidator.validate_required_string(title, "Memory title", InvalidMemoryDataError)
        memory.tags = parse_tags(tags)
        memory.summary = DomainValidator.validate_required_string(summary, "Memory summary", InvalidMemoryDataError)
        memory.updated_at = utc_now()
        return memory

    def extract_memory_and_title(
        self,
        last_10_messages: list[dict],
        memory_prompt: str,
        llm_provider: MemoryLLMProvider,
        model: str,
        params: ModelParameters | None = None,
    ) -> tuple[str, list[str], str, str]:
        formatted_messages = "\n".join(
            f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}"
            for msg in last_10_messages
        )
        prompt = (
            f"{memory_prompt.strip()}\n\n"
            "Return the result strictly as a JSON object with keys: "
            '"title", "tags" (comma-separated string or array), "summary" (300-500 chars), '
            'and "chat_title". Do NOT include chain-of-thought or "thought" fields.\n\n'
            f"Messages:\n{formatted_messages}"
        )
        target_num_ctx = params.num_ctx if params is not None and getattr(params, "num_ctx", None) else 8192
        extraction_params = ModelParameters(
            num_ctx=target_num_ctx,
            temperature=0.3,
            top_p=params.top_p if params is not None else 0.9,
            repeat_penalty=params.repeat_penalty if params is not None else 1.05,
        )
        try:
            raw_output = llm_provider.generate(
                prompt=prompt,
                model=model,
                params=extraction_params,
                format="json",
                think=False,
            ).strip()
        except TypeError:
            try:
                raw_output = llm_provider.generate(
                    prompt=prompt,
                    model=model,
                    params=extraction_params,
                    format="json",
                ).strip()
            except TypeError:
                raw_output = llm_provider.generate(
                    prompt=prompt,
                    model=model,
                    params=extraction_params,
                ).strip()

        # Discard reasoning/thinking blocks (e.g. from DeepSeek-R1, QwQ, Gemma, Claude-like)
        cleaned_output = re.sub(
            r"<(?:think|thought|reasoning|scratchpad)>.*?</(?:think|thought|reasoning|scratchpad)>",
            "",
            raw_output,
            flags=re.DOTALL | re.IGNORECASE,
        ).strip()
        if not cleaned_output and raw_output:
            cleaned_output = re.sub(
                r"<(?:think|thought|reasoning|scratchpad)>.*",
                "",
                raw_output,
                flags=re.DOTALL | re.IGNORECASE,
            ).strip() or raw_output

        # Clean markdown code fences if wrapped in ```json ... ```
        cleaned_output = re.sub(r"^```(?:json)?\s*", "", cleaned_output, flags=re.MULTILINE)
        cleaned_output = re.sub(r"\s*```$", "", cleaned_output, flags=re.MULTILINE).strip()

        title = "Roleplay Episode"
        tags: list[str] = ["roleplay", "memory"]
        summary = ""
        chat_title = "Roleplay Session"

        # Robust JSON extraction: parse all JSON objects in output (handles separated thought + memory objects)
        parsed_objects: list[dict] = []
        decoder = json.JSONDecoder()
        idx = 0
        while idx < len(cleaned_output):
            pos = cleaned_output.find("{", idx)
            if pos == -1:
                break
            try:
                obj, end_pos = decoder.raw_decode(cleaned_output, pos)
                if isinstance(obj, dict):
                    parsed_objects.append(obj)
                idx = max(end_pos, pos + 1)
            except json.JSONDecodeError:
                idx = pos + 1

        # Extract memory fields from parsed objects (prefer objects with 'summary' or 'title')
        for obj in reversed(parsed_objects):
            if isinstance(obj.get("title"), str) and obj["title"].strip():
                title = obj["title"].strip()
            raw_tags = obj.get("tags")
            if isinstance(raw_tags, (str, list)):
                extracted_tags = parse_tags(raw_tags)
                if extracted_tags:
                    tags = extracted_tags
            if isinstance(obj.get("summary"), str) and obj["summary"].strip():
                summary = obj["summary"].strip()
            if isinstance(obj.get("chat_title"), str) and obj["chat_title"].strip():
                chat_title = obj["chat_title"].strip()

        # If summary is still empty, check if an object only had 'thought' or 'thinking'
        if not summary:
            for obj in parsed_objects:
                thought_candidate = obj.get("thought") or obj.get("thinking") or obj.get("reasoning")
                if isinstance(thought_candidate, str) and thought_candidate.strip():
                    summary = thought_candidate.strip()
                    break

        # Fallback if no valid summary could be extracted
        if not summary:
            if cleaned_output and not cleaned_output.strip().startswith("{"):
                summary = cleaned_output[:500].strip()
            else:
                summary = "Summary of recent events."

        return title, tags, summary, chat_title

    @staticmethod
    def filter_narrative_messages(messages: list[Any]) -> list[Any]:
        """Extract narrative messages (USER and CHARACTER), filtering out system/metadata messages."""
        return [
            m
            for m in messages
            if getattr(m, "role", None) in ("user", "character")
            or getattr(getattr(m, "role", None), "value", None) in ("user", "character")
        ]

    def extract_messages_for_memory(
        self,
        memories: list[Memory],
        target_memory: Memory,
        all_narrative_messages: list[Any],
        chunk_size: int = 10,
    ) -> list[Any]:
        if not all_narrative_messages:
            return []

        prev_memories = [m for m in memories if m.message_idx < target_memory.message_idx]
        prev_idx = max((m.message_idx for m in prev_memories), default=-1)

        block = [
            m
            for m in all_narrative_messages
            if prev_idx < m.message_idx <= target_memory.message_idx
        ]

        if not block:
            block = [
                m
                for m in all_narrative_messages
                if m.message_idx <= target_memory.message_idx
            ][-chunk_size:]

        return block[-chunk_size:] if len(block) > chunk_size else block

    def search_memories_by_tags(
        self,
        memories: list[Memory],
        active_tags: list[str],
        latest_tags: list[str] | None = None,
        focus_keywords: frozenset[str] | set[str] | list[str] | None = None,
        max_results: int | None = None,
    ) -> list[Memory]:
        normalized_active = parse_tags(active_tags)
        if not normalized_active:
            return []
        normalized_latest = parse_tags(latest_tags) if latest_tags else []
        focus_set = set(focus_keywords) if focus_keywords else set()

        indexed = list(enumerate(memories))
        ranked = score_and_rank_tagged_items(
            indexed,
            get_tags=lambda pair: pair[1].tags,
            get_text_parts=lambda pair: (pair[1].title, pair[1].summary, " ".join(pair[1].tags)),
            get_order_key=lambda pair: pair[0],
            active_tags=normalized_active,
            latest_user_tags=normalized_latest,
            focus_keywords=focus_set,
            extra_bonus_fn=lambda pair: float(pair[1].message_idx) * 0.05,
            max_results=max_results if max_results and max_results > 0 else len(memories) or 1,
        )
        return [pair[1] for pair in ranked]

    @staticmethod
    def _filter_memories_up_to(memories: list[Memory], max_idx: int) -> list[Memory]:
        return [mem for mem in memories if mem.message_idx <= max_idx]

    def cascade_delete_memories(
        self,
        memories: list[Memory],
        deleted_message_idx: int,
    ) -> list[Memory]:
        return self._filter_memories_up_to(memories, deleted_message_idx)

    def filter_memories_for_fork(
        self,
        memories: list[Memory],
        fork_point_idx: int,
    ) -> list[Memory]:
        return self._filter_memories_up_to(memories, fork_point_idx)
