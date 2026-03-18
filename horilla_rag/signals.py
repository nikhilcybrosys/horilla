import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from base.models import Holidays
from employee.models import Employee, EmployeeWorkInformation, Policy

logger = logging.getLogger(__name__)


# ============================================================
# Phase 1: Policies, Holidays, LeaveType
# ============================================================


@receiver(post_save, sender=Policy)
def index_policy_on_save(sender, instance, **kwargs):
    from horilla_rag.services.indexing_service import index_object_async

    index_object_async(instance)


@receiver(post_delete, sender=Policy)
def delete_policy_embedding(sender, instance, **kwargs):
    from horilla_rag.services.indexing_service import IndexingService

    IndexingService().delete_embeddings("employee.Policy", instance.pk)


@receiver(post_save, sender=Holidays)
def index_holiday_on_save(sender, instance, **kwargs):
    from horilla_rag.services.indexing_service import index_object_async

    index_object_async(instance)


@receiver(post_delete, sender=Holidays)
def delete_holiday_embedding(sender, instance, **kwargs):
    from horilla_rag.services.indexing_service import IndexingService

    IndexingService().delete_embeddings("base.Holidays", instance.pk)


# ============================================================
# Phase 2: Employee, EmployeeWorkInformation, Leave
# ============================================================


@receiver(post_save, sender=Employee)
def index_employee_on_save(sender, instance, **kwargs):
    from horilla_rag.services.indexing_service import index_object_async

    index_object_async(instance)


@receiver(post_delete, sender=Employee)
def delete_employee_embedding(sender, instance, **kwargs):
    from horilla_rag.services.indexing_service import IndexingService

    IndexingService().delete_embeddings("employee.Employee", instance.pk)


@receiver(post_save, sender=EmployeeWorkInformation)
def index_employee_on_workinfo_save(sender, instance, **kwargs):
    """Re-index the employee when their work info changes (dept, position, manager)."""
    from horilla_rag.services.indexing_service import index_object_async

    if instance.employee_id:
        index_object_async(instance.employee_id)


# Conditional imports for leave module
try:
    from leave.models import AvailableLeave, LeaveRequest, LeaveType

    @receiver(post_save, sender=LeaveType)
    def index_leave_type_on_save(sender, instance, **kwargs):
        from horilla_rag.services.indexing_service import index_object_async

        index_object_async(instance)

    @receiver(post_delete, sender=LeaveType)
    def delete_leave_type_embedding(sender, instance, **kwargs):
        from horilla_rag.services.indexing_service import IndexingService

        IndexingService().delete_embeddings("leave.LeaveType", instance.pk)

    @receiver(post_save, sender=AvailableLeave)
    def index_available_leave_on_save(sender, instance, **kwargs):
        from horilla_rag.services.indexing_service import index_object_async

        index_object_async(instance)

    @receiver(post_delete, sender=AvailableLeave)
    def delete_available_leave_embedding(sender, instance, **kwargs):
        from horilla_rag.services.indexing_service import IndexingService

        IndexingService().delete_embeddings("leave.AvailableLeave", instance.pk)

    @receiver(post_save, sender=LeaveRequest)
    def index_leave_request_on_save(sender, instance, **kwargs):
        from horilla_rag.services.indexing_service import index_object_async

        index_object_async(instance)

    @receiver(post_delete, sender=LeaveRequest)
    def delete_leave_request_embedding(sender, instance, **kwargs):
        from horilla_rag.services.indexing_service import IndexingService

        IndexingService().delete_embeddings("leave.LeaveRequest", instance.pk)

except ImportError:
    pass

# Conditional import for helpdesk FAQ
try:
    from helpdesk.models import FAQ

    @receiver(post_save, sender=FAQ)
    def index_faq_on_save(sender, instance, **kwargs):
        from horilla_rag.services.indexing_service import index_object_async

        index_object_async(instance)

    @receiver(post_delete, sender=FAQ)
    def delete_faq_embedding(sender, instance, **kwargs):
        from horilla_rag.services.indexing_service import IndexingService

        IndexingService().delete_embeddings("helpdesk.FAQ", instance.pk)

except ImportError:
    pass
