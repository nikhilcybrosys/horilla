from django.conf import settings


def rag_chat_enabled(request):
    """Inject chat widget availability into template context."""
    anthropic_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    openai_key = getattr(settings, "OPENAI_API_KEY", "")
    enabled = bool(anthropic_key) or (
        bool(openai_key) and openai_key != "this_is_my_open_api_key"
    )
    return {"rag_chat_enabled": enabled}
