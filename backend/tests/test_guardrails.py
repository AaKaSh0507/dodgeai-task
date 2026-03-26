"""Unit tests for guardrails module."""
import pytest
from guardrails import check_off_topic, validate_sql


class TestCheckOffTopic:
    def test_dataset_questions_pass(self):
        assert not check_off_topic("How many sales orders are there?")
        assert not check_off_topic("Which customer has the highest billing amount?")
        assert not check_off_topic("Show me the complete O2C flow for order 740506")
        assert not check_off_topic("List all products")

    def test_off_topic_rejected(self):
        assert check_off_topic("Write me a poem about love")
        assert check_off_topic("What is the capital of France?")
        assert check_off_topic("Translate this to Spanish")
        assert check_off_topic("Give me a recipe for pasta")

    def test_very_short_input(self):
        assert check_off_topic("")
        assert check_off_topic("hi")

    def test_boundary_length(self):
        assert not check_off_topic("abc")  # exactly 3 chars


class TestValidateSQL:
    def test_valid_select(self):
        ok, _ = validate_sql("SELECT * FROM sales_order_headers")
        assert ok

    def test_valid_with_cte(self):
        ok, _ = validate_sql("WITH cte AS (SELECT 1) SELECT * FROM cte")
        assert ok

    def test_rejects_empty(self):
        ok, err = validate_sql("")
        assert not ok
        assert "Empty" in err

    def test_rejects_drop(self):
        ok, _ = validate_sql("DROP TABLE sales_order_headers")
        assert not ok

    def test_rejects_delete(self):
        ok, _ = validate_sql("DELETE FROM sales_order_headers")
        assert not ok

    def test_rejects_insert(self):
        ok, _ = validate_sql("INSERT INTO sales_order_headers VALUES (1)")
        assert not ok

    def test_rejects_update(self):
        ok, _ = validate_sql("UPDATE sales_order_headers SET salesOrder='x'")
        assert not ok

    def test_rejects_multiple_statements(self):
        ok, err = validate_sql("SELECT 1; SELECT 2")
        assert not ok
        assert "Multiple" in err

    def test_rejects_pragma(self):
        ok, _ = validate_sql("PRAGMA table_info(sales_order_headers)")
        assert not ok

    def test_trailing_semicolon_allowed(self):
        ok, _ = validate_sql("SELECT 1;")
        assert ok

    def test_select_with_subquery(self):
        ok, _ = validate_sql(
            "SELECT * FROM sales_order_headers WHERE salesOrder IN (SELECT salesOrder FROM sales_order_items)"
        )
        assert ok

    def test_rejects_injection_in_select(self):
        ok, _ = validate_sql("SELECT * FROM t; DROP TABLE t")
        assert not ok
