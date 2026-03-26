"""
Graph construction from SQLite data using NetworkX.
"""

import networkx as nx
from database import get_connection


def build_graph() -> nx.DiGraph:
    """Build a directed graph from the O2C database."""
    G = nx.DiGraph()
    conn = get_connection()

    # --- NODES ---

    # Sales Orders
    for row in conn.execute("SELECT * FROM sales_order_headers").fetchall():
        r = dict(row)
        G.add_node(f"SO:{r['salesOrder']}", type="SalesOrder", label=r["salesOrder"],
                   totalNetAmount=r.get("totalNetAmount"), creationDate=r.get("creationDate"),
                   overallDeliveryStatus=r.get("overallDeliveryStatus"),
                   overallBillingStatus=r.get("overallOrdReltdBillgStatus"),
                   currency=r.get("transactionCurrency"),
                   salesOrganization=r.get("salesOrganization"))

    # Sales Order Items
    for row in conn.execute("SELECT * FROM sales_order_items").fetchall():
        r = dict(row)
        node_id = f"SOI:{r['salesOrder']}-{r['salesOrderItem']}"
        G.add_node(node_id, type="SalesOrderItem", label=f"{r['salesOrder']}/{r['salesOrderItem']}",
                   material=r.get("material"), netAmount=r.get("netAmount"),
                   requestedQuantity=r.get("requestedQuantity"),
                   requestedQuantityUnit=r.get("requestedQuantityUnit"))
        # Edge: SalesOrder -> has item
        G.add_edge(f"SO:{r['salesOrder']}", node_id, relationship="HAS_ITEM")
        # Edge: Item -> Product
        if r.get("material"):
            G.add_edge(node_id, f"PROD:{r['material']}", relationship="CONTAINS_PRODUCT")
        # Edge: Item -> Plant
        if r.get("productionPlant"):
            G.add_edge(node_id, f"PLANT:{r['productionPlant']}", relationship="PRODUCED_AT")

    # Schedule Lines (add as attributes, not separate nodes to keep graph clean)
    # We skip these as separate nodes - they're detail data queryable via SQL

    # Outbound Deliveries
    for row in conn.execute("SELECT * FROM outbound_delivery_headers").fetchall():
        r = dict(row)
        G.add_node(f"DEL:{r['deliveryDocument']}", type="Delivery", label=r["deliveryDocument"],
                   actualGoodsMovementDate=r.get("actualGoodsMovementDate"),
                   overallGoodsMovementStatus=r.get("overallGoodsMovementStatus"),
                   creationDate=r.get("creationDate"))

    # Outbound Delivery Items - create edges to sales orders
    for row in conn.execute("SELECT * FROM outbound_delivery_items").fetchall():
        r = dict(row)
        node_id = f"DELI:{r['deliveryDocument']}-{r['deliveryDocumentItem']}"
        G.add_node(node_id, type="DeliveryItem", label=f"{r['deliveryDocument']}/{r['deliveryDocumentItem']}",
                   actualDeliveryQuantity=r.get("actualDeliveryQuantity"),
                   plant=r.get("plant"))
        # Edge: Delivery -> has item
        G.add_edge(f"DEL:{r['deliveryDocument']}", node_id, relationship="HAS_ITEM")
        # Edge: Delivery fulfills Sales Order
        if r.get("referenceSdDocument"):
            G.add_edge(f"DEL:{r['deliveryDocument']}", f"SO:{r['referenceSdDocument']}", relationship="FULFILLS")
        # Edge: DeliveryItem -> Plant
        if r.get("plant"):
            G.add_edge(node_id, f"PLANT:{r['plant']}", relationship="SHIPS_FROM")

    # Billing Document Headers
    for row in conn.execute("SELECT * FROM billing_document_headers").fetchall():
        r = dict(row)
        G.add_node(f"BILL:{r['billingDocument']}", type="BillingDocument", label=r["billingDocument"],
                   totalNetAmount=r.get("totalNetAmount"), creationDate=r.get("creationDate"),
                   billingDocumentDate=r.get("billingDocumentDate"),
                   isCancelled=r.get("billingDocumentIsCancelled"),
                   currency=r.get("transactionCurrency"))
        # Edge: Billing -> Customer
        if r.get("soldToParty"):
            G.add_edge(f"BILL:{r['billingDocument']}", f"CUST:{r['soldToParty']}", relationship="BILLED_TO")
        # Edge: Billing -> Journal Entry (via accountingDocument)
        if r.get("accountingDocument"):
            G.add_edge(f"BILL:{r['billingDocument']}",
                       f"JE:{r.get('companyCode', '')}-{r.get('fiscalYear', '')}-{r['accountingDocument']}",
                       relationship="GENERATES")

    # Billing Document Items
    for row in conn.execute("SELECT * FROM billing_document_items").fetchall():
        r = dict(row)
        node_id = f"BILLI:{r['billingDocument']}-{r['billingDocumentItem']}"
        G.add_node(node_id, type="BillingDocumentItem", label=f"{r['billingDocument']}/{r['billingDocumentItem']}",
                   material=r.get("material"), netAmount=r.get("netAmount"),
                   billingQuantity=r.get("billingQuantity"))
        G.add_edge(f"BILL:{r['billingDocument']}", node_id, relationship="HAS_ITEM")
        # Edge: BillingItem -> Product
        if r.get("material"):
            G.add_edge(node_id, f"PROD:{r['material']}", relationship="BILLS_PRODUCT")
        # Edge: BillingItem -> SalesOrder (via referenceSdDocument)
        if r.get("referenceSdDocument"):
            G.add_edge(f"BILL:{r['billingDocument']}", f"SO:{r['referenceSdDocument']}", relationship="BILLS")

    # Journal Entry Items (AR) - group by accountingDocument
    je_seen = set()
    for row in conn.execute("SELECT * FROM journal_entry_items_ar").fetchall():
        r = dict(row)
        je_key = f"JE:{r.get('companyCode', '')}-{r.get('fiscalYear', '')}-{r['accountingDocument']}"
        if je_key not in je_seen:
            G.add_node(je_key, type="JournalEntry", label=r["accountingDocument"],
                       companyCode=r.get("companyCode"), fiscalYear=r.get("fiscalYear"),
                       postingDate=r.get("postingDate"),
                       accountingDocumentType=r.get("accountingDocumentType"))
            if r.get("customer"):
                G.add_edge(je_key, f"CUST:{r['customer']}", relationship="CHARGED_TO")
            je_seen.add(je_key)

    # Payments (AR)
    pay_seen = set()
    for row in conn.execute("SELECT * FROM payments_ar").fetchall():
        r = dict(row)
        pay_key = f"PAY:{r.get('companyCode', '')}-{r.get('fiscalYear', '')}-{r['accountingDocument']}"
        if pay_key not in pay_seen:
            G.add_node(pay_key, type="Payment", label=r["accountingDocument"],
                       companyCode=r.get("companyCode"), fiscalYear=r.get("fiscalYear"),
                       postingDate=r.get("postingDate"),
                       amountInTransactionCurrency=r.get("amountInTransactionCurrency"),
                       currency=r.get("transactionCurrency"))
            if r.get("customer"):
                G.add_edge(pay_key, f"CUST:{r['customer']}", relationship="PAID_BY")
            # Link payment to journal entry via clearingAccountingDocument
            if r.get("clearingAccountingDocument"):
                clearing_key = f"JE:{r.get('companyCode', '')}-{r.get('clearingDocFiscalYear', '')}-{r['clearingAccountingDocument']}"
                G.add_edge(pay_key, clearing_key, relationship="CLEARS")
            # Link payment to sales document
            if r.get("salesDocument"):
                G.add_edge(pay_key, f"SO:{r['salesDocument']}", relationship="PAYS_FOR")
            pay_seen.add(pay_key)

    # Customers (from business_partners)
    for row in conn.execute("SELECT * FROM business_partners").fetchall():
        r = dict(row)
        cust_id = r.get("customer") or r.get("businessPartner")
        if cust_id:
            G.add_node(f"CUST:{cust_id}", type="Customer", label=cust_id,
                       name=r.get("businessPartnerFullName") or r.get("businessPartnerName"),
                       industry=r.get("industry"),
                       category=r.get("businessPartnerCategory"))

    # Sales Order -> Customer edges
    for row in conn.execute("SELECT salesOrder, soldToParty FROM sales_order_headers WHERE soldToParty IS NOT NULL AND soldToParty != ''").fetchall():
        G.add_edge(f"SO:{row[0]}", f"CUST:{row[1]}", relationship="SOLD_TO")

    # Products
    for row in conn.execute("SELECT * FROM products").fetchall():
        r = dict(row)
        G.add_node(f"PROD:{r['product']}", type="Product", label=r["product"],
                   productType=r.get("productType"), productGroup=r.get("productGroup"),
                   grossWeight=r.get("grossWeight"), baseUnit=r.get("baseUnit"))

    # Product descriptions (add as attributes to product nodes)
    for row in conn.execute("SELECT product, productDescription FROM product_descriptions WHERE language='EN'").fetchall():
        node_id = f"PROD:{row[0]}"
        if G.has_node(node_id):
            G.nodes[node_id]["description"] = row[1]

    # Plants
    for row in conn.execute("SELECT * FROM plants").fetchall():
        r = dict(row)
        G.add_node(f"PLANT:{r['plant']}", type="Plant", label=r["plant"],
                   plantName=r.get("plantName"))

    # Product -> Plant edges
    for row in conn.execute("SELECT DISTINCT product, plant FROM product_plants").fetchall():
        G.add_edge(f"PROD:{row[0]}", f"PLANT:{row[1]}", relationship="AVAILABLE_AT")

    conn.close()

    # Remove nodes that were referenced but don't exist (dangling edges)
    # This is fine - they'll just be nodes with only a type inferred from prefix
    
    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def graph_to_json(G: nx.DiGraph, node_ids: list[str] | None = None) -> dict:
    """Convert graph (or subgraph) to JSON-serializable format for frontend."""
    if node_ids:
        subgraph_nodes = set(node_ids)
        # Include immediate neighbors
        for nid in node_ids:
            if G.has_node(nid):
                subgraph_nodes.update(G.successors(nid))
                subgraph_nodes.update(G.predecessors(nid))
        sub = G.subgraph(subgraph_nodes)
    else:
        sub = G

    nodes = []
    for node_id, data in sub.nodes(data=True):
        nodes.append({
            "id": node_id,
            **{k: v for k, v in data.items() if v is not None}
        })

    edges = []
    for source, target, data in sub.edges(data=True):
        edges.append({
            "source": source,
            "target": target,
            "relationship": data.get("relationship", "RELATED_TO"),
        })

    return {"nodes": nodes, "edges": edges}


def get_node_with_neighbors(G: nx.DiGraph, node_id: str) -> dict | None:
    """Get a node and its immediate neighbors."""
    if not G.has_node(node_id):
        return None

    node_data = dict(G.nodes[node_id])
    neighbors = []

    # Outgoing edges
    for _, target, data in G.out_edges(node_id, data=True):
        target_data = dict(G.nodes[target]) if G.has_node(target) else {}
        neighbors.append({
            "id": target,
            "direction": "outgoing",
            "relationship": data.get("relationship", "RELATED_TO"),
            **{k: v for k, v in target_data.items() if v is not None}
        })

    # Incoming edges
    for source, _, data in G.in_edges(node_id, data=True):
        source_data = dict(G.nodes[source]) if G.has_node(source) else {}
        neighbors.append({
            "id": source,
            "direction": "incoming",
            "relationship": data.get("relationship", "RELATED_TO"),
            **{k: v for k, v in source_data.items() if v is not None}
        })

    return {
        "node": {"id": node_id, **{k: v for k, v in node_data.items() if v is not None}},
        "neighbors": neighbors,
    }


def get_summary_graph(G: nx.DiGraph) -> dict:
    """Return a simplified graph with only top-level entities for initial view."""
    # Include only SalesOrders, Deliveries, BillingDocuments, Customers, and their interconnections
    top_types = {"SalesOrder", "Delivery", "BillingDocument", "Customer", "Product", "Plant", "JournalEntry", "Payment"}
    top_nodes = [n for n, d in G.nodes(data=True) if d.get("type") in top_types]

    nodes = []
    for nid in top_nodes:
        data = dict(G.nodes[nid])
        nodes.append({"id": nid, **{k: v for k, v in data.items() if v is not None}})

    edges = []
    edge_set = set()
    for nid in top_nodes:
        for _, target, data in G.out_edges(nid, data=True):
            if G.has_node(target) and G.nodes[target].get("type") in top_types:
                edge_key = (nid, target)
                if edge_key not in edge_set:
                    edges.append({"source": nid, "target": target, "relationship": data.get("relationship", "RELATED_TO")})
                    edge_set.add(edge_key)

    return {"nodes": nodes, "edges": edges}


def search_nodes(G: nx.DiGraph, query: str, limit: int = 20) -> list[dict]:
    """Search nodes by ID or label (case-insensitive)."""
    query_lower = query.lower()
    results = []
    for node_id, data in G.nodes(data=True):
        label = str(data.get("label", "")).lower()
        name = str(data.get("name", "")).lower()
        desc = str(data.get("description", "")).lower()
        if query_lower in node_id.lower() or query_lower in label or query_lower in name or query_lower in desc:
            results.append({"id": node_id, **{k: v for k, v in data.items() if v is not None}})
            if len(results) >= limit:
                break
    return results
