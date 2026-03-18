"""
Classifies user queries to route them to the correct handler:
- factual: Direct DB query via MCP tools (leave balance, attendance today)
- knowledge: Semantic search via RAG (policy questions, FAQ)
- hybrid: Both MCP + RAG (eligibility checks, rule-based questions about specific data)
"""

import re

# Patterns that indicate factual/data queries (route to MCP tools)
FACTUAL_PATTERNS = [
    r"\bhow many\b",
    r"\bleave balance\b",
    r"\bleave days?\b.*\b(left|remaining|available)\b",
    r"\battendance today\b",
    r"\bwho is (on leave|absent|present)\b",
    r"\bwho('s| is) (in|checked in|clocked in)\b",
    r"\bpayslip\b",
    r"\bsalary\b",
    r"\bovertime\b.*\b(hours|pending|approved)\b",
    r"\bteam (calendar|schedule|availability)\b",
    r"\borg(anization)? chart\b",
    r"\bdepartment (count|headcount|size)\b",
    r"\bholiday(s)?\b.*\b(list|upcoming|next)\b",
    r"\bcontract\b.*\b(details|status|end)\b",
    r"\binterview(s)?\b.*\b(schedule|upcoming)\b",
    r"\bopen position(s)?\b",
    r"\bcandidate(s)?\b.*\b(pipeline|status|stage)\b",
]

# Patterns that indicate knowledge/policy queries (route to RAG)
KNOWLEDGE_PATTERNS = [
    r"\bpolicy\b",
    r"\bprocedure\b",
    r"\bhow (do|does|can|to)\b",
    r"\bwhat (is|are) the rule(s)?\b",
    r"\bexplain\b",
    r"\bwhat happens (if|when)\b",
    r"\b(maternity|paternity|sick|casual|annual) leave\b.*\b(policy|rule|entitle|eligible)\b",
    r"\bcarry\s?forward\b",
    r"\breimbursement\b.*\b(process|procedure|how)\b",
    r"\bnotice period\b",
    r"\bprobation\b.*\b(period|rule|policy)\b",
    r"\bwork from home\b.*\b(policy|rule|allow)\b",
    r"\bdress code\b",
    r"\bcode of conduct\b",
    r"\bgrievance\b",
]

_factual_compiled = [re.compile(p, re.IGNORECASE) for p in FACTUAL_PATTERNS]
_knowledge_compiled = [re.compile(p, re.IGNORECASE) for p in KNOWLEDGE_PATTERNS]


def classify_query(query):
    """
    Classify a query as 'factual', 'knowledge', or 'hybrid'.

    Returns:
        str: 'factual', 'knowledge', or 'hybrid'
    """
    query_lower = query.lower().strip()

    factual_score = sum(1 for p in _factual_compiled if p.search(query_lower))
    knowledge_score = sum(1 for p in _knowledge_compiled if p.search(query_lower))

    if factual_score > 0 and knowledge_score > 0:
        return "hybrid"
    if factual_score > 0:
        return "factual"
    if knowledge_score > 0:
        return "knowledge"

    # Default: if query contains a person's name or specific data reference, treat as factual
    # Otherwise treat as knowledge (safer default — RAG can handle both)
    return "knowledge"
