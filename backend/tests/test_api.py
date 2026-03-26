"""Integration tests for the FastAPI API endpoints."""
import os
import pytest
from pathlib import Path

os.environ.setdefault("DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "o2c.db"))

from fastapi.testclient import TestClient
from main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["nodes"] > 0
        assert data["edges"] > 0


class TestGraphEndpoints:
    def test_graph_summary(self, client):
        res = client.get("/api/graph?summary=true")
        assert res.status_code == 200
        data = res.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0

    def test_graph_full(self, client):
        res = client.get("/api/graph?summary=false")
        assert res.status_code == 200
        data = res.json()
        assert len(data["nodes"]) > len(client.get("/api/graph?summary=true").json()["nodes"])

    def test_node_detail(self, client):
        # Get a node ID from the graph
        graph = client.get("/api/graph?summary=true").json()
        node_id = graph["nodes"][0]["id"]
        res = client.get(f"/api/graph/node/{node_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["node"]["id"] == node_id
        assert "neighbors" in data

    def test_node_not_found(self, client):
        res = client.get("/api/graph/node/NONEXISTENT:999")
        assert res.status_code == 404

    def test_expand_node(self, client):
        graph = client.get("/api/graph?summary=true").json()
        node_id = graph["nodes"][0]["id"]
        res = client.get(f"/api/graph/expand/{node_id}")
        assert res.status_code == 200
        data = res.json()
        assert "nodes" in data
        assert len(data["nodes"]) >= 1

    def test_expand_nonexistent(self, client):
        res = client.get("/api/graph/expand/NONEXISTENT:999")
        assert res.status_code == 404

    def test_search(self, client):
        res = client.get("/api/graph/search?q=SO:")
        assert res.status_code == 200
        data = res.json()
        assert "results" in data
        assert len(data["results"]) > 0

    def test_search_empty_query(self, client):
        res = client.get("/api/graph/search?q=")
        assert res.status_code == 422  # validation error

    def test_search_limit(self, client):
        res = client.get("/api/graph/search?q=SO:&limit=2")
        assert res.status_code == 200
        assert len(res.json()["results"]) <= 2


class TestSchemaEndpoint:
    def test_schema(self, client):
        res = client.get("/api/schema")
        assert res.status_code == 200
        data = res.json()
        assert "schema" in data
        assert "tables" in data
        assert "sales_order_headers" in data["tables"]


class TestChatEndpoint:
    def test_empty_message(self, client):
        res = client.post("/api/chat", json={"message": ""})
        assert res.status_code == 422  # Pydantic validation

    def test_whitespace_message(self, client):
        res = client.post("/api/chat", json={"message": "   "})
        assert res.status_code == 422

    def test_off_topic_regex(self, client):
        res = client.post("/api/chat", json={"message": "Write me a poem about love"})
        assert res.status_code == 200
        data = res.json()
        assert data["is_off_topic"] is True

    def test_chat_basic(self, client):
        """Test a basic data question (requires LLM API key)."""
        res = client.post("/api/chat", json={"message": "How many sales orders are there?"})
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        # If API key is set, we should get an actual answer
        if os.getenv("GEMINI_API_KEY"):
            assert data["answer"]
            assert not data["is_off_topic"]


class TestChatStreamEndpoint:
    def test_stream_empty_message(self, client):
        res = client.post("/api/chat/stream", json={"message": ""})
        assert res.status_code == 422

    def test_stream_off_topic(self, client):
        res = client.post("/api/chat/stream", json={"message": "Tell me a joke about sports"})
        assert res.status_code == 200


class TestChatInputValidation:
    def test_message_truncated(self, client):
        """Very long messages should be truncated, not crash."""
        long_msg = "How many sales orders? " * 200  # ~4600 chars
        res = client.post("/api/chat", json={"message": long_msg})
        # Should not crash — either 200 or the off-topic check handles it
        assert res.status_code in (200, 422)

    def test_special_characters(self, client):
        res = client.post("/api/chat", json={"message": "Sales orders with amount > 1000 & < 5000"})
        assert res.status_code == 200

    def test_sql_injection_attempt(self, client):
        res = client.post(
            "/api/chat",
            json={"message": "'; DROP TABLE sales_order_headers; --"}
        )
        assert res.status_code == 200
        # Should not crash, table should still exist
        schema_res = client.get("/api/schema")
        assert "sales_order_headers" in schema_res.json()["tables"]
