"""MCP tools for leave management queries."""

import json

from horilla_mcp.server import mcp


@mcp.tool()
def get_leave_balance(employee_id: int) -> str:
    """
    Get the current leave balance for an employee.
    Returns available days, carryforward days, and total for each leave type.
    Always queries live database for accuracy.
    """
    from leave.models import AvailableLeave

    balances = AvailableLeave.objects.filter(employee_id=employee_id).select_related(
        "leave_type_id", "employee_id"
    )

    if not balances.exists():
        return json.dumps(
            {"error": f"No leave records found for employee {employee_id}"}
        )

    emp = balances.first().employee_id
    results = []

    for bal in balances:
        results.append(
            {
                "leave_type": bal.leave_type_id.name,
                "payment": bal.leave_type_id.payment,
                "available_days": float(bal.available_days),
                "carryforward_days": float(bal.carryforward_days),
                "total_days": float(bal.total_leave_days),
                "reset_date": str(bal.reset_date) if bal.reset_date else None,
            }
        )

    return json.dumps(
        {
            "employee": f"{emp.employee_first_name} {emp.employee_last_name}",
            "employee_id": emp.pk,
            "balances": results,
        },
        indent=2,
    )


@mcp.tool()
def search_policies(query: str, limit: int = 5) -> str:
    """
    Search company policies using semantic search (RAG).
    Returns relevant policy excerpts matching the query.
    Falls back to keyword search if RAG is not available.
    """
    try:
        from horilla_rag.services.retrieval_service import RetrievalService

        retriever = RetrievalService()
        results = retriever.search(
            query=query,
            document_types=["policy", "faq"],
            top_k=limit,
        )

        if results:
            return json.dumps(
                {
                    "query": query,
                    "results": [
                        {
                            "content": r["content_text"],
                            "score": r["score"],
                            "type": r["document_type"],
                        }
                        for r in results
                    ],
                },
                indent=2,
            )
    except Exception:
        pass

    # Fallback: keyword search
    from employee.models import Policy

    policies = Policy.objects.filter(title__icontains=query, is_active=True)[:limit]

    results = []
    for p in policies:
        import re

        clean_body = re.sub(r"<[^>]+>", "", p.body or "")
        clean_body = re.sub(r"\s+", " ", clean_body).strip()
        results.append(
            {
                "title": p.title,
                "content": clean_body[:500],
                "type": "policy",
            }
        )

    return json.dumps(
        {"query": query, "results": results, "source": "keyword_search"},
        indent=2,
    )
