import logging
import time

from django.conf import settings
from django.db import connection, models

from horilla_rag.models import EmbeddingDocument, RAGQueryLog
from horilla_rag.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

# Document types visible to all authenticated users in the same company
PUBLIC_DOCUMENT_TYPES = {
    "policy",
    "faq",
    "holiday",
    "company_leave",
    "leave_type",
    "announcement",
    "mail_template",
}


def get_accessible_employee_ids(user):
    """
    Get the set of employee IDs this user can access, mirroring Horilla's
    filtersubordinates() logic from base/methods.py.

    Returns:
        set of int: Employee PKs the user can access
        None: if user has full view permission (HR admin / superuser)
    """
    from employee.models import Employee

    if user.is_superuser:
        return None  # No filtering needed

    try:
        employee = user.employee_get
    except Exception:
        return set()

    # If user has broad view permission, they can see all in their company
    if user.has_perm("employee.view_employee"):
        work_info = getattr(employee, "employee_work_info", None)
        if work_info and work_info.company_id:
            return None  # No filtering — they can see everyone in company
        return None

    # Otherwise: own data + subordinates
    accessible = {employee.pk}

    nested = getattr(settings, "NESTED_SUBORDINATE_VISIBILITY", False)

    if nested:
        # Recursive: all levels of subordinates
        def _collect_subordinates(emp_pk, visited):
            subs = Employee.objects.filter(
                employee_work_info__reporting_manager_id=emp_pk,
                is_active=True,
            ).values_list("pk", flat=True)
            for sub_pk in subs:
                if sub_pk not in visited:
                    visited.add(sub_pk)
                    _collect_subordinates(sub_pk, visited)

        _collect_subordinates(employee.pk, accessible)
    else:
        # Direct subordinates only
        direct = Employee.objects.filter(
            employee_work_info__reporting_manager_id=employee.pk,
            is_active=True,
        ).values_list("pk", flat=True)
        accessible.update(direct)

    return accessible


class RetrievalService:
    """Performs vector similarity search with access control filtering."""

    def __init__(self):
        self.embedding_service = EmbeddingService()

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
        Semantic search over embeddings with company and permission filtering.

        Access control is applied BEFORE vector search (pre-filtered retrieval).
        """
        start_time = time.time()

        is_postgres = connection.vendor == "postgresql"

        # Generate query embedding
        query_embedding = self.embedding_service.embed_text(query)

        # Build filtered queryset
        qs = EmbeddingDocument.objects.all()

        # Company filter
        if company_id is not None:
            company_pk = company_id.pk if hasattr(company_id, "pk") else company_id
            qs = qs.filter(
                models.Q(company_id=company_pk) | models.Q(company_id__isnull=True)
            )

        # Document type filter
        if document_types:
            qs = qs.filter(document_type__in=document_types)

        # Access control: pre-filter by accessible employee IDs
        # Public docs are always visible; employee-specific docs need permission
        if employee_ids is not None:
            qs = qs.filter(
                models.Q(document_type__in=PUBLIC_DOCUMENT_TYPES)
                | models.Q(employee_id__in=employee_ids)
            )

        # Vector similarity search
        if is_postgres:
            try:
                from pgvector.django import CosineDistance

                qs = qs.annotate(
                    distance=CosineDistance("embedding", query_embedding)
                ).order_by("distance")[:top_k]

                results = [
                    {
                        "id": doc.pk,
                        "source_model": doc.source_model,
                        "source_id": doc.source_id,
                        "content_text": doc.content_text,
                        "score": round(1.0 - doc.distance, 4),
                        "document_type": doc.document_type,
                        "metadata": doc.metadata,
                        "chunk_index": doc.chunk_index,
                    }
                    for doc in qs
                ]
            except Exception:
                logger.exception("pgvector search failed, falling back to keyword")
                results = self._keyword_fallback(qs, query, top_k)
        else:
            # SQLite fallback: keyword search (no vector support)
            results = self._keyword_fallback(qs, query, top_k)

        latency_ms = int((time.time() - start_time) * 1000)

        # Audit log
        if user and user.is_authenticated:
            try:
                company_fk = company_id if hasattr(company_id, "pk") else None
                RAGQueryLog.objects.create(
                    user=user,
                    query_text=query,
                    results_count=len(results),
                    query_type="semantic" if is_postgres else "hybrid",
                    latency_ms=latency_ms,
                    company_id=company_fk,
                )
            except Exception:
                logger.exception("Failed to log RAG query")

        logger.info(
            f"RAG search: '{query[:50]}' -> {len(results)} results in {latency_ms}ms"
        )
        return results

    def search_for_user(self, query, user, document_types=None, top_k=5):
        """
        Convenience method: search with automatic permission filtering.
        Resolves company and accessible employees from the user object.
        """
        company_id = None
        employee_ids = None

        try:
            employee = user.employee_get
            work_info = getattr(employee, "employee_work_info", None)
            if work_info:
                company_id = work_info.company_id
        except Exception:
            pass

        # Get accessible employee IDs based on user's role
        accessible = get_accessible_employee_ids(user)
        if accessible is not None:
            employee_ids = list(accessible)

        return self.search(
            query=query,
            user=user,
            company_id=company_id,
            document_types=document_types,
            employee_ids=employee_ids,
            top_k=top_k,
        )

    def _keyword_fallback(self, qs, query, top_k):
        """Simple keyword search when pgvector is not available (SQLite dev)."""
        words = query.lower().split()
        if not words:
            return []

        q_filter = models.Q()
        for word in words[:5]:  # Limit to 5 words to avoid huge queries
            q_filter |= models.Q(content_text__icontains=word)

        qs = qs.filter(q_filter).order_by("-created_at")[:top_k]

        return [
            {
                "id": doc.pk,
                "source_model": doc.source_model,
                "source_id": doc.source_id,
                "content_text": doc.content_text,
                "score": 0.5,  # No real score for keyword search
                "document_type": doc.document_type,
                "metadata": doc.metadata,
                "chunk_index": doc.chunk_index,
            }
            for doc in qs
        ]
