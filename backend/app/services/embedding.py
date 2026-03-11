"""
Multi-provider embedding service.

Supports OpenAI (text-embedding-3-small) and Google (text-embedding-004).
The active provider is determined by settings.EMBEDDING_PROVIDER.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self._provider = settings.EMBEDDING_PROVIDER.lower()
        if self._provider == "openai":
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_EMBEDDING_MODEL
            self.dimensions = settings.OPENAI_EMBEDDING_DIMENSIONS
        elif self._provider == "google":
            from google import genai
            self._genai = genai
            self._client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            self.model = settings.GOOGLE_EMBEDDING_MODEL
            self.dimensions = settings.GOOGLE_EMBEDDING_DIMENSIONS
        else:
            raise ValueError(
                f"Unknown EMBEDDING_PROVIDER={self._provider!r}. "
                "Choose from: openai, google"
            )
        logger.info(
            "Embedding provider: %s  model: %s  dim: %d",
            self._provider, self.model, self.dimensions,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch embed multiple texts."""
        if not texts:
            return []

        if self._provider == "openai":
            return self._embed_openai(texts)
        else:
            return self._embed_google(texts)

    def embed_single(self, text: str) -> list[float]:
        """Embed a single text."""
        return self.embed_texts([text])[0]

    # ── OpenAI ──────────────────────────────────────────────────

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        all_embeddings = []
        for i in range(0, len(texts), 2048):
            batch = texts[i : i + 2048]
            response = self._client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=self.dimensions,
            )
            all_embeddings.extend(
                [item.embedding for item in response.data]
            )
        logger.info("Generated %d OpenAI embeddings", len(all_embeddings))
        return all_embeddings

    # ── Google ──────────────────────────────────────────────────

    def _embed_google(self, texts: list[str]) -> list[list[float]]:
        all_embeddings = []
        # Google embed_content supports batching via list of strings
        for i in range(0, len(texts), 100):  # Google batch limit ~100
            batch = texts[i : i + 100]
            config = {"output_dimensionality": self.dimensions}
            result = self._client.models.embed_content(
                model=self.model,
                contents=batch,
                config=config,
            )
            all_embeddings.extend(
                [emb.values for emb in result.embeddings]
            )
        logger.info("Generated %d Google embeddings", len(all_embeddings))
        return all_embeddings


embedding_service = EmbeddingService()
