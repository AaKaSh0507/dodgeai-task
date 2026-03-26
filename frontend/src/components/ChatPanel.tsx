import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Send, Loader2, ChevronDown, ChevronRight, Database } from "lucide-react";
import { sendChatMessage } from "../api";
import type { ChatMessage } from "../types";

interface Props {
  onReferencedNodes: (nodes: string[]) => void;
}

export default function ChatPanel({ onReferencedNodes }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hello! I can help you explore the SAP Order-to-Cash dataset. Ask me about sales orders, deliveries, billing documents, payments, customers, or products.\n\n**Try asking:**\n- Which products have the most billing documents?\n- Trace the full flow of a sales order\n- Find sales orders that were delivered but not billed",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [expandedSql, setExpandedSql] = useState<Set<number>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const history = messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({ role: m.role, content: m.content }));

      const response = await sendChatMessage(text, history);

      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: response.answer,
        sql_query: response.sql_query,
        referenced_nodes: response.referenced_nodes,
        is_off_topic: response.is_off_topic,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      if (response.referenced_nodes?.length) {
        onReferencedNodes(response.referenced_nodes);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err instanceof Error ? err.message : "Something went wrong"}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleSql = (index: number) => {
    setExpandedSql((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 border-l border-slate-700">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700">
        <h2 className="text-sm font-semibold text-white">Chat</h2>
        <p className="text-xs text-slate-500">Ask questions about the O2C dataset</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[90%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-200"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-sm prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                <span>{msg.content}</span>
              )}

              {/* SQL toggle */}
              {msg.sql_query && (
                <div className="mt-2 border-t border-slate-700 pt-2">
                  <button
                    onClick={() => toggleSql(i)}
                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-300"
                  >
                    <Database size={12} />
                    {expandedSql.has(i) ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                    SQL Query
                  </button>
                  {expandedSql.has(i) && (
                    <pre className="mt-1 p-2 bg-slate-900 rounded text-xs text-green-400 overflow-x-auto">
                      {msg.sql_query}
                    </pre>
                  )}
                </div>
              )}

              {/* Referenced nodes */}
              {msg.referenced_nodes && msg.referenced_nodes.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {msg.referenced_nodes.slice(0, 10).map((nodeId, j) => (
                    <button
                      key={j}
                      onClick={() => onReferencedNodes([nodeId])}
                      className="text-xs px-1.5 py-0.5 bg-slate-700 rounded text-blue-400 hover:bg-slate-600"
                    >
                      {nodeId}
                    </button>
                  ))}
                  {msg.referenced_nodes.length > 10 && (
                    <span className="text-xs text-slate-500">
                      +{msg.referenced_nodes.length - 10} more
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-slate-800 rounded-lg px-3 py-2 flex items-center gap-2">
              <Loader2 size={14} className="animate-spin text-blue-400" />
              <span className="text-sm text-slate-400">Analyzing...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-slate-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder="Ask about the dataset..."
            className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg px-3 py-2 transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
