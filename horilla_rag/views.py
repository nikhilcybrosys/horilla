import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from horilla.decorators import login_required
from horilla_rag.models import EmbeddingDocument


@login_required
@require_http_methods(["POST"])
def rag_search(request):
    """
    Semantic search endpoint with permission-filtered retrieval.

    POST /rag/search/
    Body: {"query": "...", "top_k": 5, "document_types": ["policy", "faq"]}
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    query = body.get("query", "").strip()
    if not query:
        return JsonResponse({"error": "query is required"}, status=400)

    top_k = body.get("top_k", 5)
    document_types = body.get("document_types", None)

    from horilla_rag.services.retrieval_service import RetrievalService

    retriever = RetrievalService()

    if document_types:
        # Direct search with specific types (still permission-filtered)
        from horilla_rag.services.retrieval_service import get_accessible_employee_ids

        company_id = None
        employee_ids = None
        try:
            employee = request.user.employee_get
            work_info = getattr(employee, "employee_work_info", None)
            if work_info:
                company_id = work_info.company_id
        except Exception:
            pass

        accessible = get_accessible_employee_ids(request.user)
        if accessible is not None:
            employee_ids = list(accessible)

        results = retriever.search(
            query=query,
            user=request.user,
            company_id=company_id,
            document_types=document_types,
            employee_ids=employee_ids,
            top_k=top_k,
        )
    else:
        # Auto permission-filtered search
        results = retriever.search_for_user(
            query=query,
            user=request.user,
            top_k=top_k,
        )

    return JsonResponse({"query": query, "results": results, "count": len(results)})


@login_required
@require_http_methods(["POST"])
def rag_query(request):
    """
    Orchestrated query endpoint — classifies, routes, and combines results.

    POST /rag/query/
    Body: {"query": "...", "top_k": 5}
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    query = body.get("query", "").strip()
    if not query:
        return JsonResponse({"error": "query is required"}, status=400)

    top_k = body.get("top_k", 5)

    from horilla_rag.services.orchestrator import RAGOrchestrator

    orchestrator = RAGOrchestrator()
    result = orchestrator.process_query(
        query=query,
        user=request.user,
        top_k=top_k,
    )

    return JsonResponse(result)


@login_required
@require_http_methods(["GET"])
def rag_status(request):
    """
    RAG index status endpoint.

    GET /rag/status/
    """
    from django.db.models import Count, Max

    stats = (
        EmbeddingDocument.objects.values("document_type")
        .annotate(count=Count("id"), last_updated=Max("updated_at"))
        .order_by("document_type")
    )

    total = EmbeddingDocument.objects.count()

    return JsonResponse(
        {
            "total_embeddings": total,
            "by_type": list(stats),
        }
    )


def _generate_llm_response(query, context):
    """
    Use Claude (Anthropic) or OpenAI to synthesize a natural language answer.
    Prefers Anthropic if ANTHROPIC_API_KEY is set, falls back to OpenAI.
    Returns None if no API key is configured or the call fails.
    """
    from django.conf import settings

    if not context.strip():
        return None

    system_prompt = (
        "You are Horilla HR Assistant. Answer the user's HR question "
        "based ONLY on the provided context. Be concise, helpful, and "
        "accurate. If the context doesn't contain enough information, "
        "say so. Never make up data like leave balances or dates."
    )

    # Try Anthropic (Claude) first
    anthropic_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if anthropic_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=anthropic_key)
            response = client.messages.create(
                model="claude-sonnet-4-5-20250514",
                max_tokens=500,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Context:\n{context[:3000]}\n\nQuestion: {query}",
                    },
                ],
            )
            return response.content[0].text
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning("Anthropic response failed: %s", str(e))

    # Fall back to OpenAI
    openai_key = getattr(settings, "OPENAI_API_KEY", "")
    if openai_key and openai_key not in ("", "this_is_my_open_api_key"):
        try:
            from openai import OpenAI

            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Context:\n{context[:3000]}\n\nQuestion: {query}",
                    },
                ],
                max_tokens=500,
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception:
            import logging

            logging.getLogger(__name__).debug("OpenAI response failed", exc_info=True)

    return None


def _format_tool_results(tool_results, query):
    """Format tool results into human-readable text (fallback when LLM is unavailable)."""
    import json as _json

    parts = []
    for t in tool_results:
        tool_name = t.get("tool", "")
        raw = t.get("result", "")

        try:
            data = _json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            parts.append(str(raw)[:500])
            continue

        if tool_name == "get_leave_balance" and isinstance(data, dict):
            name = data.get("employee", "You")
            balances = data.get("balances", [])
            lines = [f"Leave balance for {name}:"]
            for b in balances:
                lines.append(
                    f"  • {b['leave_type']}: {b['available_days']} days available "
                    f"({b.get('carryforward_days', 0)} carryforward, {b['total_days']} total)"
                )
            parts.append("\n".join(lines))

        elif tool_name == "get_leave_requests" and isinstance(data, dict):
            requests = data.get("requests", [])
            if requests:
                lines = [f"Leave requests ({data.get('count', len(requests))}):"]
                for r in requests[:10]:
                    lines.append(
                        f"  • {r.get('leave_type', 'Leave')}: {r.get('start_date')} to {r.get('end_date')} "
                        f"({r.get('requested_days', '?')} days) — {r.get('status', 'unknown')}"
                    )
                parts.append("\n".join(lines))
            else:
                parts.append("No leave requests found.")

        elif tool_name == "get_holidays" and isinstance(data, dict):
            holidays = data.get("holidays", [])
            lines = [
                f"Holidays for {data.get('year', 'this year')} ({data.get('count', len(holidays))}):"
            ]
            for h in holidays[:15]:
                line = f"  • {h['name']}: {h['start_date']}"
                if h.get("end_date") and h["end_date"] != h["start_date"]:
                    line += f" to {h['end_date']}"
                if h.get("recurring"):
                    line += " (recurring)"
                lines.append(line)
            parts.append("\n".join(lines))

        elif tool_name == "get_attendance_today" and isinstance(data, dict):
            parts.append(
                f"Attendance for {data.get('date', 'today')}:\n"
                f"  • Total employees: {data.get('total_employees', '?')}\n"
                f"  • Present: {data.get('present', '?')}\n"
                f"  • Absent: {data.get('absent', '?')}\n"
                f"  • On leave: {data.get('on_leave_count', '?')}"
            )

        elif tool_name == "get_department_summary" and isinstance(data, dict):
            depts = data.get("departments", [])
            lines = [f"Departments ({data.get('total_departments', len(depts))}):"]
            for d in depts[:15]:
                lines.append(f"  • {d['department']}: {d['headcount']} employees")
            parts.append("\n".join(lines))

        else:
            parts.append(str(raw)[:500])

    return "\n\n".join(parts) if parts else "No results found."


@login_required
@require_http_methods(["POST"])
def rag_chat(request):
    """
    Chat endpoint for the HTMX chat widget.
    Returns an HTML fragment with user message + bot response.

    POST /rag/chat/
    Form data: query=...
    """
    from django.shortcuts import render

    query = request.POST.get("query", "").strip()
    if not query:
        return render(
            request,
            "horilla_rag/chat_message.html",
            {
                "query": "",
                "error": "Please enter a question.",
            },
        )

    try:
        from horilla_rag.services.orchestrator import RAGOrchestrator

        orchestrator = RAGOrchestrator()
        result = orchestrator.process_query(query=query, user=request.user, top_k=5)

        context = result.get("combined_context", "")

        # Try LLM-synthesized response if API key is configured
        response = _generate_llm_response(query, context)

        if not response:
            if result.get("tool_results"):
                response = _format_tool_results(result["tool_results"], query)
            elif context:
                lines = context.split("\n")
                response = "\n".join(line for line in lines if line.strip())[:1000]
            else:
                response = "I couldn't find relevant information. Try rephrasing your question."

        # Collect source types
        sources = ", ".join(
            set(r["document_type"] for r in result.get("rag_results", []))
        )

        return render(
            request,
            "horilla_rag/chat_message.html",
            {
                "query": query,
                "response": response,
                "sources": sources,
            },
        )

    except Exception as e:
        import logging

        logging.getLogger(__name__).exception("Chat query failed")
        return render(
            request,
            "horilla_rag/chat_message.html",
            {
                "query": query,
                "error": f"Something went wrong: {str(e)[:100]}",
            },
        )
