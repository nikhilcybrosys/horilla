import hashlib

from django.db import models

from horilla.models import HorillaModel

DOCUMENT_TYPE_CHOICES = [
    ("policy", "Policy"),
    ("faq", "FAQ"),
    ("employee", "Employee Profile"),
    ("leave_type", "Leave Type"),
    ("leave_balance", "Leave Balance"),
    ("leave_request", "Leave Request"),
    ("attendance", "Attendance Summary"),
    ("holiday", "Holiday"),
    ("company_leave", "Company Leave"),
    ("announcement", "Announcement"),
    ("mail_template", "Mail Template"),
]

QUERY_TYPE_CHOICES = [
    ("semantic", "Semantic"),
    ("hybrid", "Hybrid"),
    ("mcp_routed", "MCP Routed"),
]


class EmbeddingDocument(HorillaModel):
    """Stores vector embeddings for RAG retrieval."""

    # Source tracking
    source_model = models.CharField(max_length=100, db_index=True)
    source_id = models.PositiveIntegerField()
    source_field = models.CharField(max_length=100, blank=True, default="")

    # Content
    content_text = models.TextField()
    content_hash = models.CharField(max_length=64, db_index=True)
    # On PostgreSQL: vector(1536) via migration. On SQLite: stored as TEXT (JSON array).
    embedding = models.TextField(default="[]")

    # Classification
    document_type = models.CharField(
        max_length=30, choices=DOCUMENT_TYPE_CHOICES, db_index=True
    )
    chunk_index = models.IntegerField(default=0)
    token_count = models.IntegerField(default=0)

    # Access control
    metadata = models.JSONField(default=dict, blank=True)
    employee_id = models.IntegerField(null=True, blank=True, db_index=True)
    company_id = models.ForeignKey(
        "base.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="rag_documents",
    )

    # HorillaModel provides created_at but not updated_at
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_model", "source_id", "source_field", "chunk_index"],
                name="unique_embedding_source",
            ),
        ]
        # HNSW index on embedding is created via migration RunPython (PostgreSQL only)
        indexes = [
            models.Index(
                fields=["document_type", "company_id"],
                name="rag_doc_type_company_idx",
            ),
            models.Index(
                fields=["employee_id", "document_type"],
                name="rag_employee_doc_type_idx",
            ),
        ]

    def __str__(self):
        return f"{self.document_type}:{self.source_model}#{self.source_id}"

    @staticmethod
    def compute_hash(text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RAGQueryLog(HorillaModel):
    """Audit trail for RAG queries."""

    user = models.ForeignKey(
        "horilla_auth.HorillaUser",
        on_delete=models.SET_NULL,
        null=True,
        related_name="rag_queries",
    )
    query_text = models.TextField()
    results_count = models.IntegerField(default=0)
    response_text = models.TextField(blank=True, default="")
    query_type = models.CharField(
        max_length=20, choices=QUERY_TYPE_CHOICES, default="semantic"
    )
    latency_ms = models.IntegerField(default=0)
    company_id = models.ForeignKey(
        "base.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"RAGQuery by {self.user} at {self.created_at}"


ALERT_TYPE_CHOICES = [
    ("attendance", "Attendance"),
    ("leave_balance", "Leave Balance"),
    ("contract_expiry", "Contract Expiry"),
    ("birthday", "Birthday"),
    ("capacity", "Capacity"),
    ("probation", "Probation Ending"),
]

SEVERITY_CHOICES = [
    ("info", "Info"),
    ("warning", "Warning"),
    ("critical", "Critical"),
]


class InsightAlert(HorillaModel):
    """Proactive HR insight alerts generated daily."""

    company_id = models.ForeignKey(
        "base.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="insight_alerts",
    )
    alert_type = models.CharField(
        max_length=30, choices=ALERT_TYPE_CHOICES, db_index=True
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="info")
    related_employees = models.ManyToManyField(
        "employee.Employee", blank=True, related_name="insight_alerts"
    )
    is_read = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-severity"]

    def __str__(self):
        return f"[{self.severity}] {self.alert_type}: {self.title}"
