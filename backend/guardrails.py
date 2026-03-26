"""
Guardrails for validating user queries and LLM-generated SQL.
"""

import re

# Patterns that suggest off-topic queries
OFF_TOPIC_PATTERNS = [
    r"\b(write|compose|create)\b.*(poem|story|essay|song|joke|letter)",
    r"\b(what is|who is|tell me about)\b.*(capital|president|weather|news|history)",
    r"\b(translate|convert)\b.*\b(language|french|spanish|german)\b",
    r"\b(code|program|script)\b.*(python|java|javascript|html)",
    r"\b(recipe|cook|food|restaurant)\b",
    r"\b(movie|film|music|game|sport)\b",
    r"\b(health|medical|doctor|symptom)\b",
    r"\b(travel|flight|hotel|vacation)\b",
]

REJECTION_MESSAGE = (
    "This system is designed to answer questions related to the SAP Order-to-Cash dataset only. "
    "I can help you explore sales orders, deliveries, billing documents, payments, customers, "
    "products, and their relationships. Please ask a question about the dataset."
)

# SQL statements that should never be generated
FORBIDDEN_SQL_PATTERNS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bPRAGMA\b",
    r"\bVACUUM\b",
    r"\bREINDEX\b",
]


def check_off_topic(query: str) -> bool:
    """Return True if the query appears to be off-topic (not dataset-related)."""
    query_lower = query.lower().strip()

    # Very short queries might be greetings or nonsense
    if len(query_lower) < 3:
        return True

    # Check against off-topic patterns
    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return True

    return False


def validate_sql(sql: str) -> tuple[bool, str]:
    """Validate that generated SQL is safe to execute.
    
    Returns (is_valid, error_message).
    """
    if not sql or not sql.strip():
        return False, "Empty SQL query"

    sql_upper = sql.upper().strip()

    # Must start with SELECT or WITH (for CTEs)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False, "Only SELECT queries are allowed"

    # Check for forbidden patterns
    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, sql_upper):
            return False, f"Forbidden SQL operation detected"

    # Check for multiple statements (basic semicolon check)
    # Remove semicolons at the end
    stripped = sql.strip().rstrip(";").strip()
    if ";" in stripped:
        return False, "Multiple SQL statements are not allowed"

    return True, ""
