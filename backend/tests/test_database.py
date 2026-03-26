"""Unit tests for database module."""
import os
import pytest
from pathlib import Path

# Point at the actual DB
os.environ.setdefault("DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "o2c.db"))

from database import get_schema, get_table_info, execute_readonly_query


class TestGetSchema:
    def test_returns_create_statements(self):
        schema = get_schema()
        assert "CREATE TABLE" in schema
        assert "sales_order_headers" in schema

    def test_contains_all_tables(self):
        schema = get_schema()
        expected = [
            "sales_order_headers", "sales_order_items", "billing_document_headers",
            "outbound_delivery_headers", "business_partners", "products", "plants",
        ]
        for table in expected:
            assert table in schema, f"Missing table: {table}"


class TestGetTableInfo:
    def test_returns_all_tables(self):
        info = get_table_info()
        assert len(info) >= 19
        assert "sales_order_headers" in info

    def test_column_info_structure(self):
        info = get_table_info()
        cols = info["sales_order_headers"]
        assert len(cols) > 0
        assert "name" in cols[0]
        assert "type" in cols[0]


class TestExecuteReadonlyQuery:
    def test_simple_select(self):
        cols, rows = execute_readonly_query("SELECT COUNT(*) as cnt FROM sales_order_headers")
        assert cols == ["cnt"]
        assert len(rows) == 1
        assert rows[0][0] > 0

    def test_select_with_where(self):
        cols, rows = execute_readonly_query(
            "SELECT salesOrder FROM sales_order_headers LIMIT 1"
        )
        assert "salesOrder" in cols
        assert len(rows) == 1

    def test_rejects_drop(self):
        with pytest.raises(ValueError, match="Forbidden"):
            execute_readonly_query("DROP TABLE sales_order_headers")

    def test_rejects_insert(self):
        with pytest.raises(ValueError, match="Forbidden"):
            execute_readonly_query("INSERT INTO sales_order_headers VALUES ('x')")

    def test_invalid_sql_raises(self):
        with pytest.raises(Exception):
            execute_readonly_query("SELECT * FROM nonexistent_table_xyz")

    def test_row_limit(self):
        """Ensure we don't return more than MAX_ROWS."""
        from database import MAX_ROWS
        cols, rows = execute_readonly_query("SELECT * FROM product_storage_locations")
        assert len(rows) <= MAX_ROWS

    def test_join_query(self):
        cols, rows = execute_readonly_query(
            "SELECT h.salesOrder, i.material "
            "FROM sales_order_headers h "
            "JOIN sales_order_items i ON h.salesOrder = i.salesOrder "
            "LIMIT 5"
        )
        assert "salesOrder" in cols
        assert "material" in cols
