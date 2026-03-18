"""MCP prompt: /performance-review — prepare comprehensive performance review."""

from horilla_mcp.server import mcp


@mcp.prompt()
def performance_review(employee_name: str) -> str:
    """Gather OKR progress, feedback, attendance, and bonus data to draft a performance review."""
    return f"""Prepare a comprehensive performance review for {employee_name}.

**Step 1: Identify Employee**
- Use `search_employees` to find {employee_name} and get their employee_id

**Step 2: Gather OKR Data**
- Use `get_employee_objectives` to get all objectives and key results
- Note: overall progress %, completed vs at-risk objectives

**Step 3: Gather 360 Feedback**
- Use `get_employee_feedback` to get feedback cycles
- Note: response rates, open vs closed cycles

**Step 4: Get Performance Summary**
- Use `get_performance_summary` for the aggregated view
- This includes: OKR average, feedback status, bonus points, attendance rate

**Step 5: Check Attendance**
- Use `get_employee_attendance` for monthly attendance detail
- Note: late arrivals, overtime hours

**Step 6: Compile Review**

Format the review as:

```
# Performance Review — {employee_name}
## Period: [current quarter/year]

### OKR Progress
- [objective]: [progress]% — [status]
  - KR1: [current]/[target]
  - KR2: [current]/[target]

### 360 Feedback Summary
- Cycles completed: X
- Open feedback: X
- Key themes: [summarize]

### Attendance & Reliability
- Attendance rate: X%
- Late arrivals: X
- Overtime: X hours

### Bonus Points
- Current balance: X points

### Strengths
- [based on data]

### Areas for Development
- [based on data]

### Recommendation
- [based on overall assessment]
```

Be objective and data-driven. Reference specific numbers from the tools."""
