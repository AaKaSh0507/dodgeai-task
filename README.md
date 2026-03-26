# SAP O2C Graph Explorer

A graph-based data exploration and LLM-powered query system for SAP Order-to-Cash data. Users can visually explore interconnected business entities and ask natural language questions that get translated into SQL queries against the underlying dataset.

![Architecture](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square) ![DB](https://img.shields.io/badge/Database-SQLite-003B57?style=flat-square) ![LLM](https://img.shields.io/badge/LLM-Gemini_Flash-4285F4?style=flat-square) ![Frontend](https://img.shields.io/badge/Frontend-React-61DAFB?style=flat-square)

## Live Demo

> **[https://your-demo-url.vercel.app](https://your-demo-url.vercel.app)** _(update after deployment)_

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐ │
│  │  Force-Directed Graph │  │        Chat Panel               │ │
│  │  - Color-coded nodes  │  │  - NL questions                 │ │
│  │  - Click to expand    │  │  - SQL display                  │ │
│  │  - Hover tooltips     │  │  - Markdown answers             │ │
│  │  - Node highlighting  │  │  - Entity reference links       │ │
│  └──────────┬───────────┘  └──────────┬───────────────────────┘ │
└─────────────┼──────────────────────────┼────────────────────────┘
              │        REST API          │
┌─────────────▼──────────────────────────▼────────────────────────┐
│                      Backend (FastAPI)                           │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │  Graph API   │  │  Chat API    │  │  Guardrails             │ │
│  │  /api/graph  │  │  /api/chat   │  │  - Off-topic rejection  │ │
│  │  /api/expand │  │  NL → SQL    │  │  - SQL validation       │ │
│  │  /api/search │  │  SQL → NL    │  │  - Read-only execution  │ │
│  └──────┬──────┘  └──────┬───────┘  └─────────────────────────┘ │
│         │                │                                       │
│  ┌──────▼──────┐  ┌──────▼──────┐                                │
│  │  NetworkX   │  │  Gemini LLM │                                │
│  │  In-memory  │  │  2-pass:    │                                │
│  │  DiGraph    │  │  1. Gen SQL │                                │
│  │  1385 nodes │  │  2. Summary │                                │
│  │  5339 edges │  │             │                                │
│  └──────┬──────┘  └──────┬──────┘                                │
│         │                │                                       │
│  ┌──────▼────────────────▼──────┐                                │
│  │          SQLite              │                                │
│  │  19 tables · 21K+ rows      │                                │
│  │  Read-only query execution   │                                │
│  └──────────────────────────────┘                                │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User question → Guardrails check → Gemini (NL→SQL) → SQL validation
    → SQLite execution → Gemini (results→NL summary) → Response + referenced entities
```

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Backend** | Python + FastAPI | Async-native, fast to build, excellent LLM ecosystem |
| **Database** | SQLite | Zero-config, embeddable, free to deploy, standard SQL that LLMs generate well |
| **Graph Engine** | NetworkX | In-memory directed graph for traversal + visualization serialization |
| **LLM** | Google Gemini 2.0 Flash | Free tier, fast inference, strong SQL generation |
| **Frontend** | React + Vite + TypeScript | Type safety, fast HMR, modern tooling |
| **Graph Viz** | react-force-graph-2d | Canvas-based, handles 1000+ nodes, built-in interactions |
| **Styling** | Tailwind CSS v4 | Utility-first, rapid UI development |
| **Deployment** | Docker Compose | Single command to run everything |

---

## Database Design

### Why SQLite over Neo4j or PostgreSQL?

1. **LLM compatibility**: LLMs generate standard SQL far more reliably than Cypher. This means fewer errors and more accurate query results.
2. **Zero infrastructure**: No server process, no connection pooling, no credentials. The DB is a single file.
3. **Deployability**: The SQLite file ships inside the Docker image. No external database service needed.
4. **Read performance**: For a read-only analytical workload on ~21K rows, SQLite with WAL mode is more than sufficient.
5. **Dual approach**: We use SQLite for analytical queries (aggregations, joins, filtering) and NetworkX for graph operations (traversal, neighbor expansion, visualization). Best of both worlds.

### Schema (19 tables)

**Core O2C Flow:**
- `sales_order_headers` → `sales_order_items` → `sales_order_schedule_lines`
- `outbound_delivery_headers` → `outbound_delivery_items`
- `billing_document_headers` → `billing_document_items`
- `billing_document_cancellations`
- `journal_entry_items_ar`
- `payments_ar`

**Master Data:**
- `business_partners` → `business_partner_addresses`
- `customer_company_assignments`, `customer_sales_area_assignments`
- `products` → `product_descriptions`, `product_plants`, `product_storage_locations`
- `plants`

### Graph Model (11 node types, 14 edge types)

| Node Type | Count | Key Relationships |
|-----------|-------|------------------|
| SalesOrder | 100 | → SOLD_TO Customer, → HAS_ITEM SalesOrderItem |
| Delivery | 86 | → FULFILLS SalesOrder |
| BillingDocument | 163 | → BILLS SalesOrder, → BILLED_TO Customer, → GENERATES JournalEntry |
| JournalEntry | ~100 | → CHARGED_TO Customer |
| Payment | ~100 | → CLEARS JournalEntry, → PAID_BY Customer |
| Customer | 8 | _target of SOLD_TO, BILLED_TO, PAID_BY_ |
| Product | 69 | → AVAILABLE_AT Plant |
| Plant | 44 | _target of SHIPS_FROM, PRODUCED_AT_ |

---

## LLM Prompting Strategy

### Two-Pass Architecture

**Pass 1 — NL to SQL**: The full SQLite schema (CREATE TABLE statements) + relationship descriptions + few-shot examples are injected into the system prompt. The LLM outputs structured JSON:
```json
{
  "is_relevant": true,
  "sql_query": "SELECT ...",
  "explanation": "This query finds...",
  "referenced_entities": ["SO:123", "CUST:456"]
}
```

**Pass 2 — Results to NL**: The SQL results (as a markdown table) are passed back to the LLM to generate a human-readable summary with specific numbers and values.

### Why Two-Pass?

- **Separation of concerns**: SQL generation is a structured task; summarization is a creative task. Splitting them improves reliability.
- **Debuggability**: Users can see the generated SQL and verify correctness.
- **Error recovery**: If SQL fails, we can show the error without losing the explanation.

### Context in Prompt

The system prompt includes:
- All 19 CREATE TABLE statements (exact column names)
- Key foreign-key relationships in plain English
- Domain-specific notes (currency is INR, company code is ABCD, status codes)
- The O2C flow sequence: Sales Order → Delivery → Billing → Journal Entry → Payment
- Conversation history (last 10 messages) for follow-up questions

---

## Guardrails

### Multi-Layer Protection

1. **Pre-filter**: Regex patterns detect obviously off-topic queries (poems, recipes, general knowledge) before hitting the LLM.
2. **LLM classification**: The system prompt instructs the LLM to return `"is_relevant": false` for non-dataset questions. If the response contains "OFF_TOPIC", the request is rejected.
3. **SQL validation**: Generated SQL is checked for:
   - Must start with `SELECT` or `WITH` (CTEs)
   - No DDL/DML keywords (DROP, DELETE, INSERT, UPDATE, ALTER, CREATE)
   - Single statement only (no semicolons mid-query)
4. **Read-only execution**: SQLite connection opened in `?mode=ro` (read-only mode). Even if SQL validation is bypassed, the database cannot be modified.

**Rejection response:**
> "This system is designed to answer questions related to the SAP Order-to-Cash dataset only."

---

## Features

### Core
- **Graph visualization** with 11 color-coded node types, click-to-expand, hover tooltips
- **Node inspector** with full metadata + incoming/outgoing relationships
- **Natural language chat** with data-backed answers grounded in SQL
- **SQL transparency** — every answer shows the generated SQL (collapsible)
- **Search** — find nodes by ID, name, or description

### Bonus Extensions
- **Node highlighting** — entities referenced in chat responses glow in the graph
- **Conversation memory** — follow-up questions use the last 10 messages as context
- **SSE streaming** — `/api/chat/stream` endpoint for streaming responses
- **Referenced entity links** — clickable entity badges in chat responses

---

## Quick Start

### Prerequisites
- Docker and Docker Compose
- A [Google Gemini API key](https://ai.google.dev) (free tier)

### Run with Docker Compose

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/sap-o2c-graph-explorer.git
cd sap-o2c-graph-explorer

# 2. Set your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env

# 3. Start everything
docker compose up --build

# 4. Open http://localhost:3000
```

The backend ingests data on first start (~5 seconds), builds the graph, then serves the API.

### Run Locally (without Docker)

```bash
# Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
echo "GEMINI_API_KEY=your_key_here" > .env
python ingest.py          # Load data into SQLite
python main.py            # Start API server on :8000

# Frontend (in a new terminal)
cd frontend
npm install
npm run dev               # Start dev server on :5173 (proxies /api to :8000)
```

---

## Example Queries

| Query | What It Does |
|-------|-------------|
| "Which products have the most billing documents?" | JOIN billing_document_items + products, GROUP BY, ORDER BY COUNT DESC |
| "Trace the full flow of sales order 1" | Multi-table chain: SO → Delivery → Billing → JournalEntry |
| "Find sales orders delivered but not billed" | LEFT JOIN deliveries + billing, check for NULL billing |
| "What is the total revenue by customer?" | Aggregate billing amounts grouped by customer |
| "Show me cancelled billing documents" | Filter billing_document_cancellations |
| "Write me a poem" | **Rejected** — off-topic guardrail |

---

## Project Structure

```
├── backend/
│   ├── main.py            # FastAPI server, all endpoints
│   ├── ingest.py          # JSONL → SQLite loader
│   ├── database.py        # SQLite connection + query execution
│   ├── graph.py           # NetworkX graph construction
│   ├── llm.py             # Gemini integration, NL↔SQL
│   ├── guardrails.py      # Off-topic + SQL safety checks
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main layout
│   │   ├── api.ts               # Backend API client
│   │   ├── types.ts             # TypeScript types
│   │   └── components/
│   │       ├── GraphView.tsx    # Force-directed graph
│   │       ├── ChatPanel.tsx    # Chat interface
│   │       └── NodeDetail.tsx   # Node metadata sidebar
│   ├── nginx.conf
│   └── Dockerfile
├── sap-o2c-data/          # Source JSONL dataset (19 entity dirs)
├── docker-compose.yml
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check + node/edge counts |
| GET | `/api/graph?summary=true` | Graph data for visualization |
| GET | `/api/graph/node/{id}` | Node metadata + neighbors |
| GET | `/api/graph/expand/{id}` | Expand node (subgraph) |
| GET | `/api/graph/search?q=...` | Search nodes by text |
| GET | `/api/schema` | Full DB schema |
| POST | `/api/chat` | NL chat → SQL → answer |
| POST | `/api/chat/stream` | SSE streaming version |
