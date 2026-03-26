"""Unit tests for LLM response parsing."""
import pytest
from llm import _parse_llm_response, _format_results, _extract_entity_refs


class TestParseLLMResponse:
    def test_json_response(self):
        text = '{"is_relevant": true, "sql_query": "SELECT 1", "explanation": "test", "referenced_entities": []}'
        result = _parse_llm_response(text)
        assert result["is_relevant"] is True
        assert result["sql_query"] == "SELECT 1"

    def test_json_in_markdown_fence(self):
        text = '```json\n{"is_relevant": true, "sql_query": "SELECT 1", "explanation": "test"}\n```'
        result = _parse_llm_response(text)
        assert result["is_relevant"] is True
        assert result["sql_query"] == "SELECT 1"

    def test_off_topic_marker(self):
        result = _parse_llm_response("OFF_TOPIC")
        assert result["is_relevant"] is False

    def test_raw_sql_extraction(self):
        text = "Here is the query:\nSELECT * FROM sales_order_headers;"
        result = _parse_llm_response(text)
        assert result["is_relevant"] is True
        assert "SELECT" in result.get("sql_query", "")

    def test_plain_text_answer(self):
        text = "There are 150 sales orders in the database."
        result = _parse_llm_response(text)
        assert result["is_relevant"] is True
        assert result.get("sql_query") is None
        assert text in result.get("explanation", "")


class TestFormatResults:
    def test_empty_rows(self):
        result = _format_results(["col1"], [])
        assert "No results" in result

    def test_markdown_table(self):
        result = _format_results(["name", "value"], [["Alice", "100"], ["Bob", "200"]])
        assert "| name | value |" in result
        assert "| Alice | 100 |" in result
        assert "| Bob | 200 |" in result

    def test_none_values(self):
        result = _format_results(["a"], [[None]])
        assert "| |" in result or "|  |" in result


class TestExtractEntityRefs:
    def test_extracts_sales_orders(self):
        refs = _extract_entity_refs(["salesOrder"], [["740506"], ["740507"]])
        assert "SO:740506" in refs
        assert "SO:740507" in refs

    def test_extracts_customers(self):
        refs = _extract_entity_refs(["customer"], [["310000108"]])
        assert "CUST:310000108" in refs

    def test_extracts_products(self):
        refs = _extract_entity_refs(["material"], [["3001456"]])
        assert "PROD:3001456" in refs

    def test_ignores_unknown_cols(self):
        refs = _extract_entity_refs(["unknownCol"], [["val"]])
        assert len(refs) == 0

    def test_skips_none_values(self):
        refs = _extract_entity_refs(["salesOrder"], [[None]])
        assert len(refs) == 0
