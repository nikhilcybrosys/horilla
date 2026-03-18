"""MCP prompt: /onboard — guide through employee onboarding."""

from horilla_mcp.server import mcp


@mcp.prompt()
def onboard_employee(
    name: str,
    position: str,
    department: str,
    start_date: str,
) -> str:
    """Guide through a complete employee onboarding checklist."""
    return f"""You are onboarding a new employee. Gather and verify the following:

**New Employee Details:**
- Name: {name}
- Position: {position}
- Department: {department}
- Start Date: {start_date}

**Onboarding Checklist:**

1. **Employee Record Creation**
   - Use `search_employees` to check if employee already exists
   - Verify the department exists using `get_department_summary`

2. **Team Introduction**
   - Use `get_org_chart` for {department} to show the team structure
   - Identify the reporting manager

3. **Leave Setup**
   - Check available leave types using `search_policies` for "leave policy"
   - Verify leave allocation is configured

4. **Attendance Setup**
   - Check shift assignments using `get_employee` after creation
   - Verify holidays for the year using `get_holidays`

5. **Payroll Setup**
   - Verify contract will be created
   - Check company payroll policies

6. **Welcome Materials**
   - Search for onboarding policies using `search_policies` for "onboarding"
   - Compile welcome information

Complete each step and report status. Ask for any missing information."""
