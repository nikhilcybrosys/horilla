from django.apps import apps
from django.core.management.base import BaseCommand

from horilla_rag.services.indexing_service import IndexingService
from horilla_rag.services.serializers import SERIALIZER_REGISTRY


class Command(BaseCommand):
    help = "Index all registered models into RAG embeddings"

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            help="Index a specific model (e.g., 'employee.Policy')",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-embed even if content hash is unchanged",
        )

    def handle(self, *args, **options):
        indexer = IndexingService()
        target_model = options.get("model")
        force = options.get("force", False)

        if target_model:
            if target_model not in SERIALIZER_REGISTRY:
                self.stderr.write(
                    self.style.ERROR(
                        f"No serializer registered for '{target_model}'. "
                        f"Available: {', '.join(SERIALIZER_REGISTRY.keys())}"
                    )
                )
                return

            app_label, model_name = target_model.split(".")
            model_class = apps.get_model(app_label, model_name)
            self.stdout.write(f"Indexing {target_model}...")
            count = indexer.bulk_index_model(model_class, force=force)
            self.stdout.write(
                self.style.SUCCESS(f"Indexed {count} {target_model} records")
            )
        else:
            total = 0
            for model_path in SERIALIZER_REGISTRY:
                app_label, model_name = model_path.split(".")
                try:
                    model_class = apps.get_model(app_label, model_name)
                except LookupError:
                    self.stdout.write(
                        self.style.WARNING(f"Skipping {model_path} (app not installed)")
                    )
                    continue

                self.stdout.write(f"Indexing {model_path}...")
                count = indexer.bulk_index_model(model_class, force=force)
                self.stdout.write(f"  -> {count} records indexed")
                total += count

            self.stdout.write(
                self.style.SUCCESS(f"Total: {total} records indexed across all models")
            )
