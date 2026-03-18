import logging
import threading

from django.db import transaction

from horilla_rag.models import EmbeddingDocument
from horilla_rag.services.embedding_service import EmbeddingService
from horilla_rag.services.serializers import MODEL_TO_DOCUMENT_TYPE, SERIALIZER_REGISTRY

logger = logging.getLogger(__name__)


class IndexingService:
    """Manages creating, updating, and deleting embeddings."""

    def __init__(self):
        self.embedding_service = EmbeddingService()

    def _get_model_path(self, instance):
        meta = instance._meta
        return f"{meta.app_label}.{meta.object_name}"

    def _get_company_id(self, instance):
        """Extract company from instance using common Horilla patterns."""
        # Direct company_id FK
        if hasattr(instance, "company_id") and instance.company_id:
            company = instance.company_id
            if hasattr(company, "pk"):
                return company
            return None

        # M2M company_id (Policy, LeaveType)
        if hasattr(instance, "company_id") and hasattr(instance.company_id, "first"):
            return instance.company_id.first()

        # Via employee_id → work_info → company
        if hasattr(instance, "employee_id"):
            emp = instance.employee_id
            if hasattr(emp, "employee_work_info"):
                work_info = getattr(emp, "employee_work_info", None)
                if work_info and work_info.company_id:
                    return work_info.company_id
        return None

    def _get_employee_id(self, instance):
        """Extract employee PK from instance."""
        model_path = self._get_model_path(instance)

        # The instance itself is an Employee
        if model_path == "employee.Employee":
            return instance.pk

        # Has employee_id FK
        if hasattr(instance, "employee_id") and instance.employee_id:
            emp = instance.employee_id
            return emp.pk if hasattr(emp, "pk") else emp

        return None

    def index_object(self, instance, force=False):
        """
        Serialize and embed a model instance.
        Skips re-embedding if content hash is unchanged (unless force=True).
        """
        model_path = self._get_model_path(instance)
        serializer = SERIALIZER_REGISTRY.get(model_path)

        if serializer is None:
            logger.warning(f"No serializer registered for {model_path}")
            return

        document_type = MODEL_TO_DOCUMENT_TYPE.get(model_path, "employee")

        try:
            content_text = serializer(instance)
        except Exception:
            logger.exception(f"Failed to serialize {model_path}#{instance.pk}")
            return

        if not content_text or not content_text.strip():
            return

        content_hash = EmbeddingDocument.compute_hash(content_text)
        company = self._get_company_id(instance)
        employee_id = self._get_employee_id(instance)

        # Check for existing embedding with same hash
        existing = EmbeddingDocument.objects.filter(
            source_model=model_path,
            source_id=instance.pk,
            source_field="",
            chunk_index=0,
        ).first()

        if existing and existing.content_hash == content_hash and not force:
            return  # Content unchanged

        # Check if chunking is needed
        token_count = self.embedding_service.count_tokens(content_text)
        max_tokens = 512

        if token_count <= max_tokens:
            # Single document, no chunking
            embedding = self.embedding_service.embed_text(content_text)

            with transaction.atomic():
                EmbeddingDocument.objects.update_or_create(
                    source_model=model_path,
                    source_id=instance.pk,
                    source_field="",
                    chunk_index=0,
                    defaults={
                        "content_text": content_text,
                        "content_hash": content_hash,
                        "embedding": embedding,
                        "document_type": document_type,
                        "token_count": token_count,
                        "employee_id": employee_id,
                        "company_id": company,
                        "metadata": {
                            "model": model_path,
                            "pk": instance.pk,
                        },
                    },
                )
                # Remove stale chunks if content was previously chunked
                EmbeddingDocument.objects.filter(
                    source_model=model_path,
                    source_id=instance.pk,
                    chunk_index__gt=0,
                ).delete()
        else:
            # Chunk and embed
            chunks = self.embedding_service.chunk_text(content_text)
            embeddings = self.embedding_service.embed_batch(chunks)

            with transaction.atomic():
                # Remove old embeddings for this source
                EmbeddingDocument.objects.filter(
                    source_model=model_path,
                    source_id=instance.pk,
                ).delete()

                for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                    chunk_hash = EmbeddingDocument.compute_hash(chunk)
                    chunk_tokens = self.embedding_service.count_tokens(chunk)

                    EmbeddingDocument.objects.create(
                        source_model=model_path,
                        source_id=instance.pk,
                        source_field="",
                        chunk_index=i,
                        content_text=chunk,
                        content_hash=chunk_hash,
                        embedding=emb,
                        document_type=document_type,
                        token_count=chunk_tokens,
                        employee_id=employee_id,
                        company_id=company,
                        metadata={
                            "model": model_path,
                            "pk": instance.pk,
                            "chunk": i,
                            "total_chunks": len(chunks),
                        },
                    )

        logger.info(f"Indexed {model_path}#{instance.pk} ({token_count} tokens)")

    def bulk_index_model(self, model_class, queryset=None, force=False):
        """Index all instances of a model."""
        if queryset is None:
            queryset = model_class.objects.all()

        count = 0
        for instance in queryset.iterator():
            try:
                self.index_object(instance, force=force)
                count += 1
            except Exception:
                logger.exception(
                    f"Failed to index {model_class.__name__}#{instance.pk}"
                )
        return count

    def delete_embeddings(self, source_model, source_id):
        """Remove all embeddings for a source object."""
        deleted, _ = EmbeddingDocument.objects.filter(
            source_model=source_model,
            source_id=source_id,
        ).delete()
        if deleted:
            logger.info(f"Deleted {deleted} embeddings for {source_model}#{source_id}")
        return deleted


def index_object_async(instance, force=False):
    """Index an object in a background thread."""

    def _run():
        try:
            IndexingService().index_object(instance, force=force)
        except Exception:
            logger.exception(f"Async indexing failed for {instance}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
