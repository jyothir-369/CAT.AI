/**
 * SSE streaming utilities for the chat interface.
 *
 * The server sends events in this format:
 *   data: {"token": "Hello"}\n\n
 *   data: {"token": ", "}\n\n
 *   data: {"done": true, "conversation_id": "abc-123"}\n\n
 *   data: {"error": "Provider unavailable"}\n\n
 */
import { getAccessToken } from "./api";

export interface StreamChunk {
  token?: string;
  done?: boolean;
  conversation_id?: string;
  error?: string;
}

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onDone: (conversationId: string) => void;
  onError: (error: string) => void;
}

export interface ChatStreamRequest {
  message: string;
  conversation_id?: string;
  model_id?: string;
  kb_id?: string;
  use_memory?: boolean;
}

/**
 * Open an SSE connection to the chat stream endpoint.
 * Returns an AbortController so the caller can cancel mid-stream.
 */
export function streamChat(
  request: ChatStreamRequest,
  callbacks: StreamCallbacks,
  workspaceId?: string
): AbortController {
  const controller = new AbortController();
  const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };

  const token = getAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (workspaceId) {
    headers["X-Workspace-Id"] = workspaceId;
  }

  (async () => {
    try {
      const response = await fetch(`${BASE_URL}/api/v1/chat/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        callbacks.onError(body.detail ?? `HTTP ${response.status}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError("No response body");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE events (separated by \n\n)
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? ""; // last element may be incomplete

        for (const event of events) {
          for (const line of event.split("\n")) {
            if (!line.startsWith("data:")) continue;
            const raw = line.slice(5).trim();
            if (!raw) continue;

            try {
              const chunk: StreamChunk = JSON.parse(raw);

              if (chunk.error) {
                callbacks.onError(chunk.error);
                return;
              }
              if (chunk.token) {
                callbacks.onToken(chunk.token);
              }
              if (chunk.done) {
                callbacks.onDone(chunk.conversation_id ?? "");
                return;
              }
            } catch {
              // Malformed JSON — skip
            }
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name === "AbortError") {
        return; // User cancelled — not an error
      }
      callbacks.onError((err as Error).message ?? "Stream failed");
    }
  })();

  return controller;
}

/**
 * Accumulate streaming tokens into a mutable ref.
 * Useful for copying the full response after streaming completes.
 */
export function createTokenAccumulator() {
  let accumulated = "";
  return {
    append: (token: string) => {
      accumulated += token;
    },
    get: () => accumulated,
    reset: () => {
      accumulated = "";
    },
  };
}