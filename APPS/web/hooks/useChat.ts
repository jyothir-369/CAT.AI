"use client";

/**
 * useChat — manages the full chat interaction lifecycle.
 * Connects to the SSE stream, accumulates tokens, updates store state.
 */
import { useCallback, useRef } from "react";
import { streamChat, createTokenAccumulator } from "@/lib/streaming";
import {
  useConversationStore,
} from "@/lib/store/conversation";
import { useAuthStore } from "@/lib/store/auth";
import { toast } from "@/lib/store/ui";

export function useChat() {
  const abortRef = useRef<AbortController | null>(null);
  const accumulator = useRef(createTokenAccumulator());

  const {
    addMessage,
    appendStreamToken,
    finalizeStream,
    setStreaming,
    activeConversationId,
  } = useConversationStore();

  const { activeWorkspaceId } = useAuthStore();

  const sendMessage = useCallback(
    async (
      content: string,
      options?: {
        modelId?: string;
        kbId?: string;
        useMemory?: boolean;
      }
    ) => {
      if (!content.trim()) return;

      // Cancel any in-flight stream
      if (abortRef.current) {
        abortRef.current.abort();
      }
      accumulator.current.reset();

      // Optimistically add user message to UI
      addMessage({
        id: `user-${Date.now()}`,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      });

      setStreaming(true);

      abortRef.current = streamChat(
        {
          message: content,
          conversation_id: activeConversationId ?? undefined,
          model_id: options?.modelId,
          kb_id: options?.kbId,
          use_memory: options?.useMemory ?? true,
        },
        {
          onToken: (token) => {
            accumulator.current.append(token);
            appendStreamToken(token);
          },
          onDone: (conversationId) => {
            const fullContent = accumulator.current.get();
            accumulator.current.reset();
            finalizeStream(conversationId, fullContent);
          },
          onError: (error) => {
            setStreaming(false);
            accumulator.current.reset();
            toast.error("Stream failed", error);
          },
        },
        activeWorkspaceId ?? undefined
      );
    },
    [
      activeConversationId,
      activeWorkspaceId,
      addMessage,
      appendStreamToken,
      finalizeStream,
      setStreaming,
    ]
  );

  const cancelStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      setStreaming(false);
      accumulator.current.reset();
    }
  }, [setStreaming]);

  return { sendMessage, cancelStream };
}