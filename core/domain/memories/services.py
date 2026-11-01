from datetime import datetime, timezone
import json
import re
from typing import Any, Protocol

from domain.memories.exceptions import InvalidMemoryDataError
from domain.memories.models import Memory
from domain.settings.models import ModelParameters
from shared.utils import parse_tags, tags_overlap


class MemoryLLMProvider(Protocol):
    def generate(
        self,
        prompt: str,
        model: str,
        params: ModelParameters,
        stop: list[str] | None = None,
        format: str | None = None,
    ) -> str:
        ...


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
        if isinstance(chat_session_id, bool) or not isinstance(chat_session_id, int) or chat_session_id <= 0:
            raise InvalidMemoryDataError("A valid positive chat_session_id is required.")
        if isinstance(message_idx, bool) or not isinstance(message_idx, int) or message_idx < 0:
            raise InvalidMemoryDataError("message_idx must be a non-negative integer.")

        cleaned_title = title.strip() if isinstance(title, str) else ""
        if not cleaned_title:
            raise InvalidMemoryDataError("Memory title must not be empty.")

        normalized_tags = parse_tags(tags)
        cleaned_summary = summary.strip() if isinstance(summary, str) else ""
        if not cleaned_summary:
            raise InvalidMemoryDataError("Memory summary must not be empty.")

        now = datetime.now(timezone.utc)
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
        cleaned_title = title.strip() if isinstance(title, str) else ""
        if not cleaned_title:
            raise InvalidMemoryDataError("Memory title must not be empty.")

        cleaned_summary = summary.strip() if isinstance(summary, str) else ""
        if not cleaned_summary:
            raise InvalidMemoryDataError("Memory summary must not be empty.")

        memory.title = cleaned_title
        memory.tags = parse_tags(tags)
        memory.summary = cleaned_summary
        memory.updated_at = datetime.now(timezone.utc)
        return memory

    def extract_memory_and_title(
        self,
        last_10_messages: list[dict],
        memory_prompt: str,
        llm_provider: MemoryLLMProvider,
        model: str,
    ) -> tuple[str, list[str], str, str]:
        formatted_messages = "\n".join(
            f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}"
            for msg in last_10_messages
        )
        prompt = (
            f"{memory_prompt.strip()}\n\n"
            "Return the result strictly as a JSON object with keys: "
            '"title", "tags" (comma-separated string or array), "summary" (300-500 chars), '
            'and "chat_title".\n\n'
            f"Messages:\n{formatted_messages}"
        )
        params = ModelParameters(
            num_ctx=4096,
            temperature=0.3,
            top_p=0.9,
            repeat_penalty=1.05,
        )
        try:
            raw_output = llm_provider.generate(
                prompt=prompt, model=model, params=params, format="json"
            ).strip()
        except TypeError:
            raw_output = llm_provider.generate(
                prompt=prompt, model=model, params=params
            ).strip()

        # Discard reasoning/thinking blocks (e.g. from DeepSeek-R1, QwQ)
        cleaned_output = re.sub(r"<think>.*?</think>", "", raw_output, flags=re.DOTALL).strip()
        if not cleaned_output and raw_output:
            cleaned_output = re.sub(r"<think>.*", "", raw_output, flags=re.DOTALL).strip() or raw_output

        # Clean markdown code fences if wrapped in ```json ... ```
        cleaned_output = re.sub(r"^```(?:json)?\s*", "", cleaned_output, flags=re.MULTILINE)
        cleaned_output = re.sub(r"\s*```$", "", cleaned_output, flags=re.MULTILINE).strip()

        title = "Roleplay Episode"
        tags: list[str] = ["roleplay", "memory"]
        summary = ""
        chat_title = "Roleplay Session"

        json_match = re.search(r"\{.*\}", cleaned_output, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed.get("title"), str) and parsed["title"].strip():
                    title = parsed["title"].strip()
                raw_tags = parsed.get("tags", [])
                if isinstance(raw_tags, (str, list)):
                    extracted_tags = parse_tags(raw_tags)
                    if extracted_tags:
                        tags = extracted_tags
                if isinstance(parsed.get("summary"), str) and parsed["summary"].strip():
                    summary = parsed["summary"].strip()
                if isinstance(parsed.get("chat_title"), str) and parsed["chat_title"].strip():
                    chat_title = parsed["chat_title"].strip()
            except (json.JSONDecodeError, TypeError):
                pass

        if not summary:
            summary = cleaned_output[:500] if cleaned_output else "Summary of recent events."

        return title, tags, summary, chat_title

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
    ) -> list[Memory]:
        normalized_active = parse_tags(active_tags)
        if not normalized_active:
            return []
        return [
            mem
            for mem in memories
            if tags_overlap(mem.tags, normalized_active)
        ]

    def cascade_delete_memories(
        self,
        memories: list[Memory],
        deleted_message_idx: int,
    ) -> list[Memory]:
        return [
            mem
            for mem in memories
            if mem.message_idx <= deleted_message_idx
        ]

    def filter_memories_for_fork(
        self,
        memories: list[Memory],
        fork_point_idx: int,
    ) -> list[Memory]:
        return [
            mem
            for mem in memories
            if mem.message_idx <= fork_point_idx
        ]
