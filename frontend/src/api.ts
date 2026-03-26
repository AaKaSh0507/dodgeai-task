import type { ChatResponse, GraphData, NodeDetail, SearchResult } from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "";

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30_000);

  try {
    const res = await fetch(`${API_BASE}${url}`, {
      ...options,
      signal: controller.signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(
        res.status === 429
          ? "Rate limit exceeded — please wait a moment and try again."
          : `API error ${res.status}: ${text || res.statusText}`
      );
    }
    return res.json();
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Request timed out. The server may be busy — try again.");
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

export async function getGraph(summary = true): Promise<GraphData> {
  return fetchJSON(`/api/graph?summary=${summary}`);
}

export async function getNodeDetail(nodeId: string): Promise<NodeDetail> {
  return fetchJSON(`/api/graph/node/${encodeURIComponent(nodeId)}`);
}

export async function expandNode(nodeId: string): Promise<GraphData> {
  return fetchJSON(`/api/graph/expand/${encodeURIComponent(nodeId)}`);
}

export async function searchNodes(query: string): Promise<SearchResult> {
  return fetchJSON(`/api/graph/search?q=${encodeURIComponent(query)}`);
}

export async function sendChatMessage(
  message: string,
  history: { role: string; content: string }[]
): Promise<ChatResponse> {
  return fetchJSON("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
}

export function streamChat(
  message: string,
  history: { role: string; content: string }[],
  onEvent: (event: { type: string; content: unknown }) => void,
  onDone: () => void,
  onError: (err: Error) => void
) {
  fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  })
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No reader");

      function read() {
        reader!.read().then(({ done, value }) => {
          if (done) {
            onDone();
            return;
          }
          const text = decoder.decode(value);
          const lines = text.split("\n");
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                onEvent(data);
                if (data.type === "done") {
                  onDone();
                  return;
                }
              } catch {
                // ignore parse errors
              }
            }
          }
          read();
        });
      }
      read();
    })
    .catch(onError);
}
