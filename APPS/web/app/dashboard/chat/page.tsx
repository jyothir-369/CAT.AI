"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { useChat } from "@/hooks/useChat";
import { useConversationStore, Message } from "@/lib/store/conversation";

export default function ChatPage() {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const { sendMessage, cancelStream } = useChat();
  const {
    messages,
    isStreaming,
    streamingContent,
    setMessages,
    setConversations,
    setActiveConversation,
  } = useConversationStore();

  // Load conversation list
  const { data: conversations } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.get("/conversations?limit=20").then((r) => r.data),
  });

  useEffect(() => {
    if (conversations) setConversations(conversations);
  }, [conversations, setConversations]);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");
    await sendMessage(text);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 chat-scroll">
        {messages.length === 0 && !isStreaming && (
          <div className="flex h-full items-center justify-center text-gray-400">
            <div className="text-center">
              <p className="text-2xl mb-2">💬</p>
              <p className="text-sm">Start a conversation</p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Streaming assistant message */}
        {isStreaming && (
          <div className="flex justify-start">
            <div className="max-w-[75%] rounded-2xl bg-white border px-4 py-3 text-sm text-gray-800 shadow-sm">
              <div className="message-content">
                {streamingContent || <span className="text-gray-400">Thinking…</span>}
                <span className="streaming-cursor" />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="border-t bg-white p-4">
        <form onSubmit={handleSubmit} className="flex items-end gap-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 max-h-40"
            style={{ height: "auto" }}
            onInput={(e) => {
              const ta = e.target as HTMLTextAreaElement;
              ta.style.height = "auto";
              ta.style.height = `${ta.scrollHeight}px`;
            }}
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={cancelStream}
              className="rounded-xl bg-red-100 px-4 py-3 text-sm font-medium text-red-700 hover:bg-red-200"
            >
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-40"
            >
              Send
            </button>
          )}
        </form>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-white border text-gray-800"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div
            className="message-content"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
          />
        )}
      </div>
    </div>
  );
}

/** Minimal markdown renderer — replace with react-markdown in production. */
function renderMarkdown(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br />");
}