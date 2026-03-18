"""
Horilla HR MCP Server

Exposes Horilla HRMS data as MCP tools, resources, and prompts.
Run standalone: python horilla_mcp/server.py
"""

import os
import sys

# Bootstrap Django before importing any models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import django

django.setup()

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "horilla-hr",
    instructions=(
        "Horilla HRMS data access tools. Use these tools to query employee data, "
        "leave balances, attendance records, holidays, and company policies. "
        "All data is filtered by company context."
    ),
)

from horilla_mcp.prompts import (  # noqa: F401, E402
    leave_request_prompt,
    monthly_report_prompt,
    onboard_prompt,
    performance_review_prompt,
)

# Import and register all tool + prompt modules (Phase 1–4)
from horilla_mcp.tools import (  # noqa: F401, E402
    action_tools,
    attendance_tools,
    calendar_tools,
    capacity_tools,
    employee_tools,
    insights_tools,
    leave_management_tools,
    leave_tools,
    org_tools,
    payroll_tools,
    pms_tools,
    recruitment_tools,
)


def main():
    """Entry point for MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
