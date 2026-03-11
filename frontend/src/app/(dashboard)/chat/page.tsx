"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquarePlus, Loader2, Trash2 } from "lucide-react";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { api, type ChatMessage } from "@/lib/api";
import MessageBubble from "@/components/chat/MessageBubble";
import ChatInput from "@/components/chat/ChatInput";
import DocumentDetailModal from "@/components/documents/DocumentDetailModal";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  references?: { id: string; title: string }[];
  isStreaming?: boolean;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load recent messages on mount
  useEffect(() => {
    api
      .getMessages(50)
      .then((msgs) => {
        setMessages(
          msgs.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            references: undefined,
          })),
        );
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleClear = useCallback(async () => {
    if (!confirm("Clear all chat history?")) return;
    try {
      await api.clearMessages();
      setMessages([]);
    } catch (err) {
      console.error("Failed to clear messages:", err);
    }
  }, []);

  const handleSend = useCallback(
    async (content: string) => {
      // Add user message
      const userMsg: DisplayMessage = {
        id: `temp-${Date.now()}`,
        role: "user",
        content,
      };
      setMessages((prev) => [...prev, userMsg]);

      // Add placeholder for assistant
      const assistantId = `assistant-${Date.now()}`;
      const assistantMsg: DisplayMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setStreaming(true);

      try {
        await fetchEventSource(`${API_BASE}/chat/messages`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
          onmessage(ev) {
            if (ev.event === "token") {
              const data = JSON.parse(ev.data);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + data.text }
                    : m,
                ),
              );
            } else if (ev.event === "references") {
              const data = JSON.parse(ev.data);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        references: data.documents,
                        isStreaming: false,
                      }
                    : m,
                ),
              );
            } else if (ev.event === "done") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, isStreaming: false } : m,
                ),
              );
            }
          },
          onerror(err) {
            console.error("SSE error:", err);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      content:
                        m.content ||
                        "Sorry, an error occurred. Please try again.",
                      isStreaming: false,
                    }
                  : m,
              ),
            );
            throw err;
          },
        });
      } catch (err) {
        console.error("Chat error:", err);
      } finally {
        setStreaming(false);
      }
    },
    [],
  );

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 px-6 py-3">
        <h1 className="text-lg font-semibold text-gray-900">Chat</h1>
        {messages.length > 0 && (
          <button
            onClick={handleClear}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          >
            <Trash2 className="h-4 w-4" />
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto px-6 py-4">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-gray-400">
            <MessageSquarePlus className="mb-3 h-12 w-12" />
            <p className="text-lg font-medium">Ask anything about your documents</p>
            <p className="mt-1 text-sm">
              Your AI assistant has access to all your uploaded PDFs
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                role={msg.role}
                content={msg.content}
                references={msg.references}
                isStreaming={msg.isStreaming}
                onReferenceClick={setSelectedDocId}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 bg-white px-6 py-4">
        <ChatInput onSend={handleSend} disabled={streaming} />
      </div>

      {/* Document detail modal */}
      {selectedDocId && (
        <DocumentDetailModal
          documentId={selectedDocId}
          onClose={() => setSelectedDocId(null)}
        />
      )}
    </div>
  );
}
