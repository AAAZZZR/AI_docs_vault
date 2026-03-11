"""
Multi-provider LLM service.

Supports Anthropic (Claude), Google (Gemini), and OpenAI (GPT).
The active provider is determined by settings.LLM_PROVIDER.
Each provider exposes the same interface through a BaseLLMProvider ABC.
"""

import abc
import json
import logging
import re
from collections.abc import Iterator

from app.core.config import settings
from app.services.prompts.pdf_parse import (
    build_condensed_note_prompt,
    build_page_parse_prompt,
    build_tag_prompt,
)
from app.services.prompts.chat_prompts import (
    CHAT_SYSTEM_PROMPT,
    build_chat_messages,
    build_intent_prompt,
)

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────

def _extract_json(text: str) -> dict | list:
    """Extract JSON from LLM response, handling markdown code fences."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.strip()
    return json.loads(cleaned)


# ── Abstract Base ───────────────────────────────────────────────

class BaseLLMProvider(abc.ABC):
    """Interface every LLM provider must implement."""

    @abc.abstractmethod
    def complete(
        self,
        messages: list[dict],
        *,
        model: str,
        max_tokens: int = 4096,
        system: str | None = None,
    ) -> str:
        """Single-turn completion → full text response."""

    @abc.abstractmethod
    def complete_with_image(
        self,
        image_base64: str,
        text_prompt: str,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> str:
        """Vision completion with a single base64 image."""

    @abc.abstractmethod
    def stream(
        self,
        messages: list[dict],
        *,
        model: str,
        max_tokens: int = 4096,
        system: str | None = None,
    ) -> Iterator[str]:
        """Streaming completion → yields text chunks."""


# ── Anthropic ───────────────────────────────────────────────────

class AnthropicProvider(BaseLLMProvider):
    def __init__(self):
        from anthropic import Anthropic
        self._client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def complete(self, messages, *, model, max_tokens=4096, system=None):
        kwargs = dict(model=model, max_tokens=max_tokens, messages=messages)
        if system:
            kwargs["system"] = system
        resp = self._client.messages.create(**kwargs)
        return resp.content[0].text

    def complete_with_image(self, image_base64, text_prompt, *, model, max_tokens=4096):
        resp = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}},
                    {"type": "text", "text": text_prompt},
                ],
            }],
        )
        return resp.content[0].text

    def stream(self, messages, *, model, max_tokens=4096, system=None):
        kwargs = dict(model=model, max_tokens=max_tokens, messages=messages)
        if system:
            kwargs["system"] = system
        with self._client.messages.stream(**kwargs) as s:
            for text in s.text_stream:
                yield text


# ── Google Gemini ───────────────────────────────────────────────

class GoogleProvider(BaseLLMProvider):
    def __init__(self):
        from google import genai
        self._genai = genai
        self._client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    def complete(self, messages, *, model, max_tokens=4096, system=None):
        config = self._genai.types.GenerateContentConfig(
            max_output_tokens=max_tokens,
        )
        if system:
            config.system_instruction = system

        contents = self._messages_to_contents(messages)
        resp = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        return resp.text

    def complete_with_image(self, image_base64, text_prompt, *, model, max_tokens=4096):
        import base64
        image_bytes = base64.b64decode(image_base64)

        contents = [
            self._genai.types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            text_prompt,
        ]
        config = self._genai.types.GenerateContentConfig(max_output_tokens=max_tokens)
        resp = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        return resp.text

    def stream(self, messages, *, model, max_tokens=4096, system=None):
        config = self._genai.types.GenerateContentConfig(
            max_output_tokens=max_tokens,
        )
        if system:
            config.system_instruction = system

        contents = self._messages_to_contents(messages)
        for chunk in self._client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                yield chunk.text

    def _messages_to_contents(self, messages: list[dict]) -> list:
        """Convert OpenAI-style messages to Gemini contents."""
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                self._genai.types.Content(
                    role=role,
                    parts=[self._genai.types.Part.from_text(text=msg["content"])],
                )
            )
        return contents


# ── OpenAI ──────────────────────────────────────────────────────

class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        from openai import OpenAI
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def complete(self, messages, *, model, max_tokens=4096, system=None):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)
        resp = self._client.chat.completions.create(
            model=model, max_tokens=max_tokens, messages=msgs,
        )
        return resp.choices[0].message.content

    def complete_with_image(self, image_base64, text_prompt, *, model, max_tokens=4096):
        resp = self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                    {"type": "text", "text": text_prompt},
                ],
            }],
        )
        return resp.choices[0].message.content

    def stream(self, messages, *, model, max_tokens=4096, system=None):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)
        stream = self._client.chat.completions.create(
            model=model, max_tokens=max_tokens, messages=msgs, stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content


# ── Provider Factory ────────────────────────────────────────────

_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "openai": OpenAIProvider,
}


def _make_provider() -> BaseLLMProvider:
    key = settings.LLM_PROVIDER.lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER={key!r}. Choose from: {list(_PROVIDERS)}"
        )
    logger.info("LLM provider: %s", key)
    return cls()


def _get_models() -> tuple[str, str]:
    """Return (primary_model, fast_model) for the active provider."""
    key = settings.LLM_PROVIDER.lower()
    if key == "anthropic":
        return settings.ANTHROPIC_PRIMARY_MODEL, settings.ANTHROPIC_FAST_MODEL
    elif key == "google":
        return settings.GOOGLE_PRIMARY_MODEL, settings.GOOGLE_FAST_MODEL
    elif key == "openai":
        return settings.OPENAI_PRIMARY_MODEL, settings.OPENAI_FAST_MODEL
    raise ValueError(f"Unknown LLM_PROVIDER={key!r}")


# ── High-level Service ──────────────────────────────────────────

class LLMService:
    def __init__(self):
        self._provider = _make_provider()
        self._primary_model, self._fast_model = _get_models()

    @property
    def provider_name(self) -> str:
        return settings.LLM_PROVIDER.lower()

    def parse_pdf_page(
        self,
        image_base64: str,
        page_num: int,
        total_pages: int,
        context: str = "",
    ) -> dict:
        """Send a single page image for structured extraction (primary model)."""
        prompt = build_page_parse_prompt(page_num, total_pages, context)
        text = self._provider.complete_with_image(
            image_base64, prompt, model=self._primary_model, max_tokens=4096,
        )
        try:
            return _extract_json(text)
        except (json.JSONDecodeError, IndexError):
            logger.error("Failed to parse JSON from page %d: %s", page_num, text[:200])
            return {
                "page": page_num,
                "summary": text[:500],
                "key_entities": [],
                "tables": [],
                "images": [],
            }

    def generate_condensed_note(
        self, page_extractions: list[dict], filename: str
    ) -> dict:
        """Synthesize all page extractions into a condensed note (primary model)."""
        prompt = build_condensed_note_prompt(page_extractions, filename)
        text = self._provider.complete(
            [{"role": "user", "content": prompt}],
            model=self._primary_model,
            max_tokens=8192,
        )
        try:
            return _extract_json(text)
        except (json.JSONDecodeError, IndexError):
            logger.error("Failed to parse condensed note JSON")
            return {
                "version": 1,
                "title": filename,
                "summary": text[:1000],
                "document_type": "unknown",
                "sections": [],
                "key_findings": [],
                "entities": {},
                "auto_tags": [],
            }

    def generate_tags(
        self, condensed_note: dict, existing_tags: list[dict]
    ) -> list[dict]:
        """Generate context-aware tags from condensed note (fast model).

        existing_tags: list of {"name": str, "description": str}
        Returns list of {"name": str, "description": str, "confidence": float}
        """
        prompt = build_tag_prompt(condensed_note, existing_tags)
        text = self._provider.complete(
            [{"role": "user", "content": prompt}],
            model=self._fast_model,
            max_tokens=2048,
        )
        try:
            result = _extract_json(text)
            if isinstance(result, dict):
                return result.get("tags", [])
            return result
        except (json.JSONDecodeError, IndexError):
            logger.error("Failed to parse tags JSON")
            return [
                {"name": t, "confidence": 0.7}
                for t in condensed_note.get("auto_tags", [])
            ]

    def parse_chat_intent(
        self, query: str, conversation_history: list[dict]
    ) -> dict:
        """Classify intent and extract search params (fast model)."""
        prompt = build_intent_prompt(query, conversation_history)
        text = self._provider.complete(
            [{"role": "user", "content": prompt}],
            model=self._fast_model,
            max_tokens=512,
        )
        try:
            return _extract_json(text)
        except (json.JSONDecodeError, IndexError):
            return {"intent": "search", "search_query": query, "tag_filter": []}

    def generate_chat_response(
        self,
        query: str,
        context_chunks: list[dict],
        condensed_notes: list[dict],
        conversation_history: list[dict],
    ) -> Iterator[str]:
        """Stream a chat response with RAG context (primary model)."""
        messages = build_chat_messages(
            query, context_chunks, condensed_notes, conversation_history
        )
        yield from self._provider.stream(
            messages,
            model=self._primary_model,
            max_tokens=4096,
            system=CHAT_SYSTEM_PROMPT,
        )


llm_service = LLMService()
