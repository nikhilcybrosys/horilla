import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_local_model = None


class EmbeddingService:
    """Generates vector embeddings using local sentence-transformers model.

    Uses all-MiniLM-L6-v2 (384 dimensions, free, no API key needed).
    Falls back to OpenAI if OPENAI_API_KEY is configured.
    """

    def __init__(self):
        self._openai_client = None

    def _use_local(self):
        key = getattr(settings, "OPENAI_API_KEY", "")
        return not key or key in ("", "this_is_my_open_api_key", "sk-...")

    def _get_local_model(self):
        global _local_model
        if _local_model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading local embedding model (first time only)...")
            _local_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Model loaded (384-dim vectors).")
        return _local_model

    @property
    def dimensions(self):
        if self._use_local():
            return 384
        return getattr(settings, "RAG_EMBEDDING_DIMENSIONS", 1536)

    def embed_text(self, text):
        """Embed a single text string. Returns a list of floats."""
        if self._use_local():
            model = self._get_local_model()
            return model.encode(text).tolist()

        return self._embed_openai([text])[0]

    def embed_batch(self, texts):
        """Embed multiple texts. Returns list of embedding vectors."""
        if not texts:
            return []

        if self._use_local():
            model = self._get_local_model()
            embeddings = model.encode(
                texts, show_progress_bar=len(texts) > 50, batch_size=64
            )
            return [e.tolist() for e in embeddings]

        return self._embed_openai(texts)

    def _embed_openai(self, texts):
        """Fallback: embed via OpenAI API."""
        if self._openai_client is None:
            from openai import OpenAI

            self._openai_client = OpenAI(
                api_key=getattr(settings, "OPENAI_API_KEY", "")
            )

        import time

        all_embeddings = []
        batch_size = 2048
        model = getattr(settings, "RAG_EMBEDDING_MODEL", "text-embedding-3-large")
        dims = getattr(settings, "RAG_EMBEDDING_DIMENSIONS", 1536)

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self._openai_client.embeddings.create(
                input=batch,
                model=model,
                dimensions=dims,
            )
            all_embeddings.extend([item.embedding for item in response.data])
            if i + batch_size < len(texts):
                time.sleep(0.5)

        return all_embeddings

    def count_tokens(self, text):
        """Count tokens in text (approximate for local model)."""
        return len(text.split())

    def chunk_text(self, text, max_tokens=None, overlap=None):
        """Split text into overlapping chunks based on word count."""
        if max_tokens is None:
            max_tokens = getattr(settings, "RAG_CHUNK_MAX_TOKENS", 512)
        if overlap is None:
            overlap = getattr(settings, "RAG_CHUNK_OVERLAP", 50)

        words = text.split()

        if len(words) <= max_tokens:
            return [text]

        chunks = []
        start = 0

        while start < len(words):
            end = min(start + max_tokens, len(words))
            chunk_words = words[start:end]
            chunks.append(" ".join(chunk_words))

            if end >= len(words):
                break

            start = end - overlap

        return chunks
