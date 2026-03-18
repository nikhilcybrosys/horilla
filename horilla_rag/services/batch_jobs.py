"""Batch re-indexing jobs for data that changes frequently."""

import logging
from datetime import date

logger = logging.getLogger(__name__)


def reindex_attendance_summaries():
    """
    Re-index attendance summaries for the current month.
    Called nightly via APScheduler.
    """
    try:
        from attendance.models import AttendanceOverTime
        from horilla_rag.models import EmbeddingDocument
        from horilla_rag.services.embedding_service import EmbeddingService
        from horilla_rag.services.serializers import serialize_attendance_summary

        today = date.today()
        month_names = [
            "",
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]
        month_name = month_names[today.month]

        ot_records = AttendanceOverTime.objects.filter(
            month=month_name,
            year=str(today.year),
        ).select_related("employee_id")

        embedding_service = EmbeddingService()
        count = 0

        for ot in ot_records:
            emp = ot.employee_id
            if not emp or not emp.is_active:
                continue

            data = {
                "present_days": (
                    ot.hour_account_second // 3600 // 8 if ot.hour_account_second else 0
                ),
                "worked_hours": ot.worked_hours or "00:00",
                "pending_hours": ot.pending_hours or "00:00",
                "overtime": ot.overtime or "00:00",
            }

            text = serialize_attendance_summary(emp, month_name, str(today.year), data)
            content_hash = EmbeddingDocument.compute_hash(text)

            existing = EmbeddingDocument.objects.filter(
                source_model="attendance.AttendanceOverTime",
                source_id=ot.pk,
                chunk_index=0,
            ).first()

            if existing and existing.content_hash == content_hash:
                continue

            try:
                embedding = embedding_service.embed_text(text)
                company = None
                work_info = getattr(emp, "employee_work_info", None)
                if work_info:
                    company = work_info.company_id

                EmbeddingDocument.objects.update_or_create(
                    source_model="attendance.AttendanceOverTime",
                    source_id=ot.pk,
                    source_field="",
                    chunk_index=0,
                    defaults={
                        "content_text": text,
                        "content_hash": content_hash,
                        "embedding": embedding,
                        "document_type": "attendance",
                        "token_count": embedding_service.count_tokens(text),
                        "employee_id": emp.pk,
                        "company_id": company,
                        "metadata": {
                            "model": "attendance.AttendanceOverTime",
                            "pk": ot.pk,
                            "month": month_name,
                            "year": today.year,
                        },
                    },
                )
                count += 1
            except Exception:
                logger.exception(f"Failed to embed attendance for {emp}")

        logger.info(
            f"Re-indexed {count} attendance summaries for {month_name} {today.year}"
        )

    except ImportError:
        logger.info("Attendance app not installed, skipping attendance re-indexing")
    except Exception:
        logger.exception("Attendance re-indexing failed")
