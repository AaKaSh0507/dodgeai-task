"""
FastAPI server for the O2C Graph Query System.
"""

import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

import database
from graph import build_graph, graph_to_json, get_node_with_neighbors, get_summary_graph, search_nodes
from llm import chat

# Global graph instance
_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build graph on startup."""
    global _graph
    print("Building graph from database...")
    _graph = build_graph()
    print(f"Graph ready: {_graph.number_of_nodes()} nodes, {_graph.number_of_edges()} edges")
    yield
    _graph = None


app = FastAPI(title="O2C Graph Query System", lifespan=lifespan)

# CORS - allow all origins for demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic models ---

class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    answer: str
    sql_query: str | None = None
    referenced_nodes: list[str] = []
    is_off_topic: bool = False


# --- Endpoints ---

@app.get("/api/health")
def health():
    return {"status": "ok", "nodes": _graph.number_of_nodes() if _graph else 0,
            "edges": _graph.number_of_edges() if _graph else 0}


@app.get("/api/graph")
def get_graph(summary: bool = True):
    """Return the graph data for visualization.
    
    If summary=True (default), returns only top-level entities.
    If summary=False, returns the full graph.
    """
    if not _graph:
        raise HTTPException(status_code=503, detail="Graph not ready")
    if summary:
        return get_summary_graph(_graph)
    return graph_to_json(_graph)


@app.get("/api/graph/node/{node_id:path}")
def get_node(node_id: str):
    """Get a specific node and its immediate neighbors."""
    if not _graph:
        raise HTTPException(status_code=503, detail="Graph not ready")
    result = get_node_with_neighbors(_graph, node_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return result


@app.get("/api/graph/expand/{node_id:path}")
def expand_node(node_id: str):
    """Get all neighbors of a node for expanding the graph view."""
    if not _graph:
        raise HTTPException(status_code=503, detail="Graph not ready")
    if not _graph.has_node(node_id):
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return graph_to_json(_graph, [node_id])


@app.get("/api/graph/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100)):
    """Search nodes by ID, label, or description."""
    if not _graph:
        raise HTTPException(status_code=503, detail="Graph not ready")
    return {"results": search_nodes(_graph, q, limit)}


@app.get("/api/schema")
def get_schema():
    """Return the database schema."""
    return {"schema": database.get_schema(), "tables": database.get_table_info()}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat with the system using natural language."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    result = await chat(request.message, request.history)
    return ChatResponse(**result)


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat responses using Server-Sent Events."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    async def event_generator():
        # Send processing status
        yield f"data: {json.dumps({'type': 'status', 'content': 'Analyzing your question...'})}\n\n"

        result = await chat(request.message, request.history)

        # Send SQL if available
        if result.get("sql_query"):
            yield f"data: {json.dumps({'type': 'sql', 'content': result['sql_query']})}\n\n"

        # Send answer
        yield f"data: {json.dumps({'type': 'answer', 'content': result['answer']})}\n\n"

        # Send referenced nodes
        if result.get("referenced_nodes"):
            yield f"data: {json.dumps({'type': 'nodes', 'content': result['referenced_nodes']})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
