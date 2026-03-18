"""
Initial migration for horilla_rag.

Database-aware: creates pgvector extension and HNSW index only on PostgreSQL.
On SQLite (dev), the embedding column is stored as TEXT.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import connection, migrations, models


def create_pgvector_extension(apps, schema_editor):
    """Create pgvector extension on PostgreSQL only."""
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def alter_embedding_to_vector(apps, schema_editor):
    """Convert embedding column to pgvector vector type on PostgreSQL only."""
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "ALTER TABLE horilla_rag_embeddingdocument "
            "ALTER COLUMN embedding TYPE vector(1536) "
            "USING embedding::vector(1536);"
        )


def create_hnsw_index(apps, schema_editor):
    """Create HNSW index on PostgreSQL only."""
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "CREATE INDEX IF NOT EXISTS rag_embedding_hnsw_idx "
            "ON horilla_rag_embeddingdocument "
            "USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64);"
        )


def reverse_all(apps, schema_editor):
    """Reverse: drop index, revert column, drop extension."""
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP INDEX IF EXISTS rag_embedding_hnsw_idx;")
        schema_editor.execute(
            "ALTER TABLE horilla_rag_embeddingdocument "
            "ALTER COLUMN embedding TYPE text;"
        )
        schema_editor.execute("DROP EXTENSION IF EXISTS vector;")


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("base", "0003_alter_dynamicemailconfiguration_company_id_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Step 1: pgvector extension (no-op on SQLite)
        migrations.RunPython(create_pgvector_extension, migrations.RunPython.noop),
        # Step 2: RAGQueryLog (no pgvector dependency)
        migrations.CreateModel(
            name="RAGQueryLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("query_text", models.TextField()),
                ("results_count", models.IntegerField(default=0)),
                ("response_text", models.TextField(blank=True, default="")),
                ("query_type", models.CharField(choices=[("semantic", "Semantic"), ("hybrid", "Hybrid"), ("mcp_routed", "MCP Routed")], default="semantic", max_length=20)),
                ("latency_ms", models.IntegerField(default=0)),
                ("company_id", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="base.company")),
                ("created_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("modified_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_modified_by", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="rag_queries", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        # Step 3: EmbeddingDocument with TEXT embedding column (works on both SQLite and PostgreSQL)
        migrations.CreateModel(
            name="EmbeddingDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("source_model", models.CharField(db_index=True, max_length=100)),
                ("source_id", models.PositiveIntegerField()),
                ("source_field", models.CharField(blank=True, default="", max_length=100)),
                ("content_text", models.TextField()),
                ("content_hash", models.CharField(db_index=True, max_length=64)),
                ("embedding", models.TextField(default="[]")),
                ("document_type", models.CharField(choices=[("policy", "Policy"), ("faq", "FAQ"), ("employee", "Employee Profile"), ("leave_type", "Leave Type"), ("leave_balance", "Leave Balance"), ("leave_request", "Leave Request"), ("attendance", "Attendance Summary"), ("holiday", "Holiday"), ("company_leave", "Company Leave"), ("announcement", "Announcement"), ("mail_template", "Mail Template")], db_index=True, max_length=30)),
                ("chunk_index", models.IntegerField(default=0)),
                ("token_count", models.IntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("employee_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company_id", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="rag_documents", to="base.company")),
                ("created_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("modified_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_modified_by", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["document_type", "company_id"], name="rag_doc_type_company_idx"),
                    models.Index(fields=["employee_id", "document_type"], name="rag_employee_doc_type_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("source_model", "source_id", "source_field", "chunk_index"), name="unique_embedding_source"),
                ],
            },
        ),
        # Step 4: Convert embedding TEXT → vector(1536) on PostgreSQL only (no-op on SQLite)
        migrations.RunPython(alter_embedding_to_vector, reverse_all),
        # Step 5: HNSW index on PostgreSQL only (no-op on SQLite)
        migrations.RunPython(create_hnsw_index, migrations.RunPython.noop),
    ]
