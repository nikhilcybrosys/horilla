"""
Hybrid search: combines pgvector semantic search with PostgreSQL full-text search.

Scoring: final_score = alpha * semantic_score + (1 - alpha) * fts_score
Default alpha = 0.7 (semantic-heavy).
"""

import logging
import time

from django.db import connection, models

from horilla_rag.models import EmbeddingDocument, RAGQueryLog
from horilla_rag.services.embedding_service import EmbeddingService
from horilla_rag.services.retrieval_service import PUBLIC_DOCUMENT_TYPES

logger = logging.getLogger(__name__)


class HybridSearchService:
    """Combines vector similarity with keyword matching for best results."""

    def __init__(self, alpha=0.7):
        self.embedding_service = EmbeddingService()
        self.alpha = alpha  # Weight for semantic score (1-alpha for FTS)

    def search(
        self,
        query,
        user=None,
        company_id=None,
        document_types=None,
        employee_ids=None,
        top_k=5,
    ):
        """
        Hybrid search: semantic + keyword, then rank-fuse the results.
        Falls back to keyword-only on SQLite.
        """
        start_time = time.time()
        is_postgres = connection.vendor == "postgresql"

        # Base queryset with access filters
        base_qs = self._build_filtered_qs(company_id, document_types, employee_ids)

        if is_postgres:
            results = self._postgres_hybrid(base_qs, query, top_k)
        else:
            results = self._keyword_search(base_qs, query, top_k)

        latency_ms = int((time.time() - start_time) * 1000)

        if user and user.is_authenticated:
            try:
                company_fk = company_id if hasattr(company_id, "pk") else None
                RAGQueryLog.objects.create(
                    user=user,
                    query_text=query,
                    results_count=len(results),
                    query_type="hybrid",
                    latency_ms=latency_ms,
                    company_id=company_fk,
                )
            except Exception:
                logger.exception("Failed to log hybrid query")

        return results

    def _build_filtered_qs(self, company_id, document_types, employee_ids):
        """Build access-controlled base queryset."""
        qs = EmbeddingDocument.objects.all()

        if company_id is not None:
            company_pk = company_id.pk if hasattr(company_id, "pk") else company_id
            qs = qs.filter(
                models.Q(company_id=company_pk) | models.Q(company_id__isnull=True)
            )

        if document_types:
            qs = qs.filter(document_type__in=document_types)

        if employee_ids is not None:
            qs = qs.filter(
                models.Q(document_type__in=PUBLIC_DOCUMENT_TYPES)
                | models.Q(employee_id__in=employee_ids)
            )

        return qs

    def _postgres_hybrid(self, base_qs, query, top_k):
        """PostgreSQL: combine pgvector + FTS ranking."""
        from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

        query_embedding = self.embedding_service.embed_text(query)

        try:
            from pgvector.django import CosineDistance

            # Semantic search
            semantic_qs = base_qs.annotate(
                distance=CosineDistance("embedding", query_embedding)
            ).order_by("distance")[: top_k * 2]

            semantic_results = {
                doc.pk: {
                    "doc": doc,
                    "semantic_score": max(0, 1.0 - doc.distance),
                }
                for doc in semantic_qs
            }

            # Full-text search
            search_vector = SearchVector("content_text")
            search_query = SearchQuery(query, search_type="websearch")

            fts_qs = (
                base_qs.annotate(rank=SearchRank(search_vector, search_query))
                .filter(rank__gt=0)
                .order_by("-rank")[: top_k * 2]
            )

            fts_results = {}
            for doc in fts_qs:
                fts_results[doc.pk] = {
                    "doc": doc,
                    "fts_score": float(doc.rank),
                }

            # Merge and rank-fuse
            all_ids = set(semantic_results.keys()) | set(fts_results.keys())
            combined = []

            # Normalize FTS scores to 0-1 range
            max_fts = max((r["fts_score"] for r in fts_results.values()), default=1.0)
            if max_fts == 0:
                max_fts = 1.0

            for pk in all_ids:
                sem = semantic_results.get(pk, {})
                fts = fts_results.get(pk, {})

                semantic_score = sem.get("semantic_score", 0)
                fts_score = fts.get("fts_score", 0) / max_fts

                final_score = self.alpha * semantic_score + (1 - self.alpha) * fts_score

                doc = sem.get("doc") or fts.get("doc")
                combined.append(
                    {
                        "id": doc.pk,
                        "source_model": doc.source_model,
                        "source_id": doc.source_id,
                        "content_text": doc.content_text,
                        "score": round(final_score, 4),
                        "document_type": doc.document_type,
                        "metadata": doc.metadata,
                        "chunk_index": doc.chunk_index,
                        "semantic_score": round(semantic_score, 4),
                        "fts_score": round(fts_score, 4),
                    }
                )

            combined.sort(key=lambda x: x["score"], reverse=True)
            return combined[:top_k]

        except Exception:
            logger.exception("Hybrid search failed, falling back to keyword")
            return self._keyword_search(base_qs, query, top_k)

    def _keyword_search(self, base_qs, query, top_k):
        """SQLite fallback: keyword search."""
        words = query.lower().split()[:5]
        if not words:
            return []

        q_filter = models.Q()
        for word in words:
            q_filter |= models.Q(content_text__icontains=word)

        qs = base_qs.filter(q_filter).order_by("-created_at")[:top_k]

        return [
            {
                "id": doc.pk,
                "source_model": doc.source_model,
                "source_id": doc.source_id,
                "content_text": doc.content_text,
                "score": 0.5,
                "document_type": doc.document_type,
                "metadata": doc.metadata,
                "chunk_index": doc.chunk_index,
            }
            for doc in qs
        ]
