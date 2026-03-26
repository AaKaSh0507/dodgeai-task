"""
FastAPI server for the O2C Graph Query System.
"""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, field_validator

load_dotenv()

import database
from graph import build_graph, graph_to_json, get_node_with_neighbors, get_summary_graph, search_nodes
from llm import chat

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("o2c")

# Global graph instance
_graph = None

# --- Simple in-memory rate limiter ---
_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))
CHAT_TIMEOUT = int(os.getenv("CHAT_TIMEOUT_SEC", "60"))


def _check_rate_limit(key: str) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.time()
    window = now - 60
    _rate_store[key] = [t for t in _rate_store[key] if t > window]
    if len(_rate_store[key]) >= RATE_LIMIT:
        return False
    _rate_store[key].append(now)
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build graph on startup."""
    global _graph
    logger.info("Building graph from database...")
    _graph = build_graph()
    logger.info("Graph ready: %d nodes, %d edges", _graph.number_of_nodes(), _graph.number_of_edges())
    yield
    _graph = None


app = FastAPI(title="O2C Graph Query System", lifespan=lifespan)

# CORS
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Global error handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# --- Pydantic models ---

class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()[:2000]  # cap at 2000 chars


class ChatResponse(BaseModel):
    answer: str
    sql_query: str | None = None
    referenced_nodes: list[str] = []
    is_off_topic: bool = False


# --- Endpoints ---

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "nodes": _graph.number_of_nodes() if _graph else 0,
        "edges": _graph.number_of_edges() if _graph else 0,
    }


@app.get("/api/graph")
def get_graph(summary: bool = True):
    if not _graph:
        raise HTTPException(status_code=503, detail="Graph not ready")
    if summary:
        return get_summary_graph(_graph)
    return graph_to_json(_graph)


@app.get("/api/graph/node/{node_id:path}")
def get_node(node_id: str):
    if not _graph:
        raise HTTPException(status_code=503, detail="Graph not ready")
    result = get_node_with_neighbors(_graph, node_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return result


@app.get("/api/graph/expand/{node_id:path}")
def expand_node(node_id: str):
    if not _graph:
        raise HTTPException(status_code=503, detail="Graph not ready")
    if not _graph.has_node(node_id):
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return graph_to_json(_graph, [node_id])


@app.get("/api/graph/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100)):
    if not _graph:
        raise HTTPException(status_code=503, detail="Graph not ready")
    return {"results": search_nodes(_graph, q, limit)}


@app.get("/api/schema")
def get_schema():
    return {"schema": database.get_schema(), "tables": database.get_table_info()}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, raw_request: Request):
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")

    logger.info("Chat request from %s: %s", client_ip, request.message[:120])

    try:
        result = await asyncio.wait_for(
            chat(request.message, request.history),
            timeout=CHAT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("Chat timed out for: %s", request.message[:120])
        return ChatResponse(answer="The query took too long to process. Please try a simpler question.")
    except Exception:
        logger.exception("Chat error")
        return ChatResponse(answer="An error occurred while processing your question. Please try again.")

    logger.info("Chat response — sql: %s, refs: %d, off_topic: %s",
                bool(result.get("sql_query")), len(result.get("referenced_nodes", [])), result.get("is_off_topic"))
    return ChatResponse(**result)


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, raw_request: Request):
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")

    logger.info("Stream chat from %s: %s", client_ip, request.message[:120])

    async def event_generator():
        yield f"data: {json.dumps({'type': 'status', 'content': 'Analyzing your question...'})}\n\n"

        try:
            result = await asyncio.wait_for(
                chat(request.message, request.history),
                timeout=CHAT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'answer', 'content': 'The query took too long. Please try a simpler question.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
        except Exception:
            logger.exception("Stream chat error")
            yield f"data: {json.dumps({'type': 'answer', 'content': 'An error occurred. Please try again.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        if result.get("sql_query"):
            yield f"data: {json.dumps({'type': 'sql', 'content': result['sql_query']})}\n\n"

        yield f"data: {json.dumps({'type': 'answer', 'content': result['answer']})}\n\n"

        if result.get("referenced_nodes"):
            yield f"data: {json.dumps({'type': 'nodes', 'content': result['referenced_nodes']})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
