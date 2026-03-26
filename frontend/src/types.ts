export interface GraphNode {
  id: string;
  type?: string;
  label?: string;
  name?: string;
  description?: string;
  [key: string]: unknown;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface NodeDetail {
  node: GraphNode;
  neighbors: (GraphNode & { direction: string; relationship: string })[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sql_query?: string | null;
  referenced_nodes?: string[];
  is_off_topic?: boolean;
}

export interface ChatResponse {
  answer: string;
  sql_query: string | null;
  referenced_nodes: string[];
  is_off_topic: boolean;
}

export interface SearchResult {
  results: GraphNode[];
}

// Color mapping for node types
export const NODE_COLORS: Record<string, string> = {
  SalesOrder: "#3b82f6",      // blue
  SalesOrderItem: "#60a5fa",  // light blue
  Delivery: "#22c55e",        // green
  DeliveryItem: "#4ade80",    // light green
  BillingDocument: "#f97316",  // orange
  BillingDocumentItem: "#fb923c", // light orange
  JournalEntry: "#eab308",    // yellow
  Payment: "#a855f7",         // purple
  Customer: "#ec4899",        // pink
  Product: "#ef4444",         // red
  Plant: "#6b7280",           // gray
};

export const NODE_TYPE_LABELS: Record<string, string> = {
  SalesOrder: "Sales Order",
  SalesOrderItem: "SO Item",
  Delivery: "Delivery",
  DeliveryItem: "Delivery Item",
  BillingDocument: "Billing Doc",
  BillingDocumentItem: "Billing Item",
  JournalEntry: "Journal Entry",
  Payment: "Payment",
  Customer: "Customer",
  Product: "Product",
  Plant: "Plant",
};
