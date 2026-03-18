"""MCP prompt: /leave-request — guide through leave request review."""

from horilla_mcp.server import mcp


@mcp.prompt()
def process_leave_request(employee_name: str) -> str:
    """Step-by-step leave request review: check balance, team calendar, policy, approve/reject."""
    return f"""You are reviewing a leave request for {employee_name}. Follow these steps:

**Step 1: Identify the Employee**
- Use `search_employees` to find {employee_name}
- Note their employee_id, department, and manager

**Step 2: Check Leave Balance**
- Use `get_leave_balance` with the employee_id
- Verify sufficient balance for the requested leave type

**Step 3: Check Team Calendar**
- Use `get_team_calendar` to check if others in the team are on leave during the same period
- Flag potential staffing issues

**Step 4: Review Leave Policy**
- Use `search_policies` to find relevant leave policy rules
- Check: approval requirements, attachment requirements, restricted dates

**Step 5: Check for Conflicts**
- Use `get_leave_requests` filtered by the employee to check for overlapping requests

**Step 6: Decision**
Based on the above analysis:
- If everything looks good → use `approve_leave_request` (preview first, then confirm)
- If there are issues → use `reject_leave_request` with a clear reason
- If more information is needed → list what's missing

Provide a summary of your analysis before making the decision."""
