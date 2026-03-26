"""
LLM integration using Google Gemini for NL-to-SQL translation and response generation.
"""

import json
import os
import re
import google.generativeai as genai
from database import get_schema, execute_readonly_query
from guardrails import check_off_topic, validate_sql, REJECTION_MESSAGE

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))

model = genai.GenerativeModel("gemini-2.0-flash")

SYSTEM_PROMPT = """You are a data analyst assistant for an SAP Order-to-Cash (O2C) system. 
You help users query and understand business data about sales orders, deliveries, billing documents, 
payments, customers, and products.

IMPORTANT RULES:
1. You ONLY answer questions about the provided dataset. If a question is unrelated to the O2C dataset, 
   respond with: "OFF_TOPIC"
2. When you need to query data, generate a SQLite SQL query.
3. ONLY generate SELECT queries. Never generate INSERT, UPDATE, DELETE, DROP, or any DDL.
4. Always use the exact table and column names from the schema.
5. Return your response in the following JSON format:
   {
     "is_relevant": true/false,
     "sql_query": "SELECT ... (or null if not needed)",
     "explanation": "Brief explanation of what the query does",
     "referenced_entities": ["SO:123", "CUST:456"] (list of entity IDs referenced)
   }

DATABASE SCHEMA:
{schema}

KEY RELATIONSHIPS:
- sales_order_headers.soldToParty = business_partners.customer (customer who placed the order)
- sales_order_items.salesOrder = sales_order_headers.salesOrder (items in an order)
- sales_order_items.material = products.product (product ordered)
- sales_order_items.productionPlant = plants.plant (plant for production)
- outbound_delivery_items.referenceSdDocument = sales_order_headers.salesOrder (delivery fulfills order)
- outbound_delivery_items.deliveryDocument = outbound_delivery_headers.deliveryDocument
- billing_document_items.referenceSdDocument = sales_order_headers.salesOrder (invoice for order)
- billing_document_items.billingDocument = billing_document_headers.billingDocument
- billing_document_items.material = products.product (product billed)
- billing_document_headers.soldToParty = business_partners.customer (customer billed)
- billing_document_headers.accountingDocument = journal_entry_items_ar.accountingDocument (accounting entry)
- journal_entry_items_ar.customer = business_partners.customer
- payments_ar.customer = business_partners.customer
- payments_ar.salesDocument = sales_order_headers.salesOrder
- product_plants.product = products.product AND product_plants.plant = plants.plant
- product_descriptions.product = products.product (use language='EN' for English descriptions)
- business_partner_addresses.businessPartner = business_partners.businessPartner

O2C FLOW: Sales Order → Delivery → Billing Document → Journal Entry → Payment

IMPORTANT NOTES:
- All monetary amounts are in INR (Indian Rupees)
- Company code is 'ABCD' for all records
- Use billing_document_cancellations for cancelled invoices
- overallDeliveryStatus 'C' = Complete, overallOrdReltdBillgStatus for billing status
- To trace a full flow: start from sales_order_headers, join to outbound_delivery_items (via referenceSdDocument),
  then billing_document_items (via referenceSdDocument), then billing_document_headers (for accountingDocument),
  then journal_entry_items_ar (via accountingDocument)
"""


def get_system_prompt() -> str:
    """Build the system prompt with current schema."""
    schema = get_schema()
    return SYSTEM_PROMPT.replace("{schema}", schema)


async def chat(message: str, history: list[dict] | None = None) -> dict:
    """Process a user message and return a response with data.
    
    Returns: {answer, sql_query, referenced_nodes, is_off_topic}
    """
    # Quick off-topic check
    if check_off_topic(message):
        # Still let the LLM make the final call, but flag it
        pass

    system_prompt = get_system_prompt()

    # Build conversation for the LLM
    contents = [{"role": "user", "parts": [{"text": f"System instructions:\n{system_prompt}"}]},
                {"role": "model", "parts": [{"text": "I understand. I will only answer questions about the SAP O2C dataset and return responses in the specified JSON format."}]}]

    # Add conversation history
    if history:
        for msg in history[-10:]:  # Last 10 messages for context
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    # Add current message
    contents.append({"role": "user", "parts": [{"text": message}]})

    try:
        # Pass 1: Generate SQL
        response = model.generate_content(contents)
        llm_text = response.text.strip()

        # Parse LLM response
        parsed = _parse_llm_response(llm_text)

        if not parsed["is_relevant"]:
            return {
                "answer": REJECTION_MESSAGE,
                "sql_query": None,
                "referenced_nodes": [],
                "is_off_topic": True,
            }

        sql_query = parsed.get("sql_query")
        explanation = parsed.get("explanation", "")
        referenced = parsed.get("referenced_entities", [])

        if not sql_query:
            return {
                "answer": explanation or "I couldn't generate a query for that question. Could you rephrase it?",
                "sql_query": None,
                "referenced_nodes": referenced,
                "is_off_topic": False,
            }

        # Validate SQL
        is_valid, error = validate_sql(sql_query)
        if not is_valid:
            return {
                "answer": f"I generated a query but it didn't pass safety checks: {error}. Please try rephrasing your question.",
                "sql_query": sql_query,
                "referenced_nodes": [],
                "is_off_topic": False,
            }

        # Execute SQL
        try:
            columns, rows = execute_readonly_query(sql_query)
        except Exception as e:
            # If query fails, try to get LLM to fix it
            return {
                "answer": f"The query encountered an error: {str(e)}. Let me know if you'd like to try a different approach.",
                "sql_query": sql_query,
                "referenced_nodes": [],
                "is_off_topic": False,
            }

        # Pass 2: Summarize results
        if not rows:
            answer = f"{explanation}\n\nThe query returned no results."
        elif len(rows) <= 50:
            result_text = _format_results(columns, rows)
            summary_prompt = (
                f"The user asked: '{message}'\n"
                f"Query explanation: {explanation}\n"
                f"SQL: {sql_query}\n"
                f"Results:\n{result_text}\n\n"
                f"Please provide a clear, concise natural language answer based on these results. "
                f"Include specific numbers and values from the data. Format nicely with markdown if helpful."
            )
            summary_response = model.generate_content(summary_prompt)
            answer = summary_response.text.strip()
        else:
            # Too many rows, summarize first few
            result_text = _format_results(columns, rows[:20])
            answer = (
                f"{explanation}\n\n"
                f"The query returned {len(rows)} rows. Here are the first 20:\n\n{result_text}"
            )

        # Extract entity IDs from results
        referenced_nodes = _extract_entity_refs(columns, rows)
        referenced_nodes.extend(referenced)

        return {
            "answer": answer,
            "sql_query": sql_query,
            "referenced_nodes": list(set(referenced_nodes)),
            "is_off_topic": False,
        }

    except Exception as e:
        return {
            "answer": f"An error occurred while processing your question: {str(e)}",
            "sql_query": None,
            "referenced_nodes": [],
            "is_off_topic": False,
        }


def _parse_llm_response(text: str) -> dict:
    """Parse the LLM's JSON response, handling various formats."""
    # Check for explicit off-topic
    if "OFF_TOPIC" in text:
        return {"is_relevant": False}

    # Try to extract JSON
    # Look for JSON block in markdown code fence
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try parsing the whole text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find any JSON object in the text
    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # If we can't parse JSON, check if it looks like a direct answer
    # This happens when the LLM ignores the JSON format instruction
    if any(keyword in text.upper() for keyword in ["SELECT", "FROM", "WHERE"]):
        # Extract SQL from the text
        sql_match = re.search(r"(SELECT\s+.*?)(?:;|\Z)", text, re.DOTALL | re.IGNORECASE)
        if sql_match:
            return {
                "is_relevant": True,
                "sql_query": sql_match.group(1).strip(),
                "explanation": "Query generated from your question",
                "referenced_entities": [],
            }

    return {"is_relevant": True, "sql_query": None, "explanation": text, "referenced_entities": []}


def _format_results(columns: list[str], rows: list[list]) -> str:
    """Format query results as a readable table."""
    if not rows:
        return "No results"

    # Markdown table
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body_lines = []
    for row in rows:
        body_lines.append("| " + " | ".join(str(v) if v is not None else "" for v in row) + " |")

    return "\n".join([header, separator] + body_lines)


def _extract_entity_refs(columns: list[str], rows: list[list]) -> list[str]:
    """Extract entity references from query results for graph highlighting."""
    refs = []
    col_mapping = {
        "salesOrder": "SO",
        "deliveryDocument": "DEL",
        "billingDocument": "BILL",
        "accountingDocument": "JE",
        "customer": "CUST",
        "product": "PROD",
        "material": "PROD",
        "plant": "PLANT",
        "businessPartner": "CUST",
    }

    for col_idx, col_name in enumerate(columns):
        prefix = col_mapping.get(col_name)
        if prefix:
            for row in rows[:50]:  # Limit to avoid huge lists
                val = row[col_idx]
                if val:
                    refs.append(f"{prefix}:{val}")

    return refs
