"""Unit tests for graph module."""
import os
import pytest
from pathlib import Path

os.environ.setdefault("DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "o2c.db"))

from graph import build_graph, graph_to_json, get_node_with_neighbors, get_summary_graph, search_nodes


@pytest.fixture(scope="module")
def graph():
    """Build graph once for all tests in this module."""
    return build_graph()


class TestBuildGraph:
    def test_has_nodes(self, graph):
        assert graph.number_of_nodes() > 100

    def test_has_edges(self, graph):
        assert graph.number_of_edges() > 100

    def test_expected_node_types(self, graph):
        types = {d.get("type") for _, d in graph.nodes(data=True)}
        for t in ["SalesOrder", "Customer", "Product", "Delivery", "BillingDocument"]:
            assert t in types, f"Missing node type: {t}"

    def test_nodes_have_labels(self, graph):
        for node_id, data in list(graph.nodes(data=True))[:50]:
            assert "label" in data, f"Node {node_id} missing label"


class TestGraphToJson:
    def test_returns_nodes_and_edges(self, graph):
        result = graph_to_json(graph)
        assert "nodes" in result
        assert "edges" in result
        assert len(result["nodes"]) > 0
        assert len(result["edges"]) > 0

    def test_node_structure(self, graph):
        result = graph_to_json(graph)
        node = result["nodes"][0]
        assert "id" in node
        assert "type" in node

    def test_edge_structure(self, graph):
        result = graph_to_json(graph)
        edge = result["edges"][0]
        assert "source" in edge
        assert "target" in edge
        assert "relationship" in edge

    def test_subgraph_for_specific_node(self, graph):
        # Get a known sales order node
        so_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "SalesOrder"]
        assert len(so_nodes) > 0
        result = graph_to_json(graph, [so_nodes[0]])
        assert len(result["nodes"]) >= 1


class TestGetNodeWithNeighbors:
    def test_existing_node(self, graph):
        so_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "SalesOrder"]
        result = get_node_with_neighbors(graph, so_nodes[0])
        assert result is not None
        assert "node" in result
        assert "neighbors" in result
        assert result["node"]["id"] == so_nodes[0]

    def test_nonexistent_node(self, graph):
        result = get_node_with_neighbors(graph, "NONEXISTENT:999")
        assert result is None


class TestGetSummaryGraph:
    def test_excludes_items(self, graph):
        result = get_summary_graph(graph)
        types = {n.get("type") for n in result["nodes"]}
        assert "SalesOrderItem" not in types
        assert "DeliveryItem" not in types
        assert "BillingDocumentItem" not in types

    def test_includes_top_level(self, graph):
        result = get_summary_graph(graph)
        types = {n.get("type") for n in result["nodes"]}
        assert "SalesOrder" in types
        assert "Customer" in types


class TestSearchNodes:
    def test_search_by_id(self, graph):
        # Use a known node type prefix
        results = search_nodes(graph, "SO:")
        assert len(results) > 0
        assert all("SO:" in r["id"] for r in results)

    def test_search_by_name(self, graph):
        # Search for a partial customer name
        results = search_nodes(graph, "CUST:")
        assert len(results) > 0

    def test_search_no_results(self, graph):
        results = search_nodes(graph, "zzzzzznonexistent123")
        assert len(results) == 0

    def test_search_respects_limit(self, graph):
        results = search_nodes(graph, "SO:", limit=3)
        assert len(results) <= 3
