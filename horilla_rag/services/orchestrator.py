"""
RAG Orchestrator: routes queries through classification → retrieval/tools → response.
"""

import json
import logging

from horilla_rag.services.query_classifier import classify_query
from horilla_rag.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


class RAGOrchestrator:
    """
    Routes user queries to the appropriate handler based on classification.

    - factual → MCP tool calls (direct DB queries)
    - knowledge → RAG semantic search
    - hybrid → both, then combine results
    """

    def __init__(self):
        self.retriever = RetrievalService()

    def process_query(self, query, user, top_k=5):
        """
        Process a user query end-to-end.

        Returns:
            dict with: query, classification, rag_results, tool_results, combined_context
        """
        classification = classify_query(query)

        result = {
            "query": query,
            "classification": classification,
            "rag_results": [],
            "tool_results": [],
            "combined_context": "",
        }

        if classification in ("knowledge", "hybrid"):
            rag_results = self.retriever.search_for_user(
                query=query,
                user=user,
                top_k=top_k,
            )
            result["rag_results"] = rag_results

        if classification in ("factual", "hybrid"):
            tool_results = self._route_to_tools(query, user)
            result["tool_results"] = tool_results

        # Combine context from both sources
        context_parts = []

        if result["rag_results"]:
            context_parts.append("=== Retrieved Documents ===")
            for r in result["rag_results"]:
                context_parts.append(f"[{r['document_type']}] {r['content_text']}")

        if result["tool_results"]:
            context_parts.append("=== Live Data ===")
            for t in result["tool_results"]:
                context_parts.append(f"[{t['tool']}] {t['result']}")

        result["combined_context"] = "\n\n".join(context_parts)

        return result

    def _route_to_tools(self, query, user):
        """
        Route factual queries to appropriate MCP tools.
        Uses keyword matching to determine which tool to call.
        """
        results = []
        query_lower = query.lower()

        try:
            employee = user.employee_get
            employee_id = employee.pk
        except Exception:
            return results

        # Leave balance queries
        if any(
            kw in query_lower
            for kw in [
                "leave balance",
                "leave days",
                "days left",
                "days remaining",
                "how many leave",
                "leaves do i have",
                "leaves left",
                "my leave",
                "available leave",
                "remaining leave",
                "leave available",
                "leave remaining",
                "leave quota",
            ]
        ):
            try:
                from horilla_mcp.tools.leave_tools import get_leave_balance

                result = get_leave_balance(employee_id=employee_id)
                results.append({"tool": "get_leave_balance", "result": result})
            except Exception:
                logger.exception("Failed to call get_leave_balance")

        # Leave request queries
        if any(
            kw in query_lower
            for kw in [
                "leave request",
                "leave status",
                "my leave request",
                "applied leave",
                "pending leave",
                "approved leave",
                "leave history",
                "leave application",
            ]
        ):
            try:
                from horilla_mcp.tools.leave_management_tools import get_leave_requests

                result = get_leave_requests(employee_id=employee_id)
                results.append({"tool": "get_leave_requests", "result": result})
            except Exception:
                logger.exception("Failed to call get_leave_requests")

        # Holiday queries
        if any(
            kw in query_lower
            for kw in [
                "holiday",
                "holidays",
                "upcoming holiday",
                "next holiday",
                "public holiday",
                "when is the holiday",
            ]
        ):
            try:
                from horilla_mcp.tools.calendar_tools import get_holidays

                result = get_holidays()
                results.append({"tool": "get_holidays", "result": result})
            except Exception:
                logger.exception("Failed to call get_holidays")

        # Attendance queries
        if any(
            kw in query_lower
            for kw in [
                "attendance today",
                "who is present",
                "who is absent",
                "checked in",
                "my attendance",
                "attendance summary",
                "present today",
                "absent today",
            ]
        ):
            try:
                from horilla_mcp.tools.attendance_tools import get_attendance_today

                result = get_attendance_today()
                results.append({"tool": "get_attendance_today", "result": result})
            except Exception:
                logger.exception("Failed to call get_attendance_today")

        # Team queries
        if any(
            kw in query_lower
            for kw in [
                "my team",
                "team calendar",
                "team attendance",
                "team leave",
                "department summary",
                "team members",
            ]
        ):
            try:
                from horilla_mcp.tools.org_tools import get_department_summary

                result = get_department_summary()
                results.append({"tool": "get_department_summary", "result": result})
            except Exception:
                logger.exception("Failed to call get_department_summary")

        # Policy queries
        if any(
            kw in query_lower
            for kw in [
                "policy",
                "policies",
                "company policy",
                "leave policy",
                "what is the rule",
                "what is the policy",
            ]
        ):
            try:
                from horilla_mcp.tools.leave_tools import search_policies

                result = search_policies(query=query)
                results.append({"tool": "search_policies", "result": result})
            except Exception:
                logger.exception("Failed to call search_policies")

        return results
