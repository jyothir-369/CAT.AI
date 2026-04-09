/**
 * Conversation store — active conversation, streaming state.
 */
import { create } from "zustand";

export interface Message {
  id: string;
  role: "user" | "assistant" | "system" | "tool" | "tool_result";
  content: string;
  model_id?: string | null;
  created_at: string;
  isStreaming?: boolean;
}

export interface Conversation {
  id: string;
  title: string | null;
  model_id: string | null;
  created_at: string;
  updated_at: string;
}

interface ConversationState {
  conversations: Conversation[];
  activeConversationId: string | null;
  messages: Message[];
  isStreaming: boolean;
  streamingContent: string;

  // Actions
  setConversations: (conversations: Conversation[]) => void;
  addConversation: (conversation: Conversation) => void;
  removeConversation: (id: string) => void;
  setActiveConversation: (id: string | null) => void;
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  appendStreamToken: (token: string) => void;
  finalizeStream: (conversationId: string, fullContent: string) => void;
  setStreaming: (streaming: boolean) => void;
  reset: () => void;
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  messages: [],
  isStreaming: false,
  streamingContent: "",

  setConversations: (conversations) => set({ conversations }),

  addConversation: (conversation) =>
    set((state) => ({
      conversations: [conversation, ...state.conversations],
    })),

  removeConversation: (id) =>
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      activeConversationId:
        state.activeConversationId === id ? null : state.activeConversationId,
    })),

  setActiveConversation: (id) =>
    set({ activeConversationId: id, messages: [], streamingContent: "" }),

  setMessages: (messages) => set({ messages }),

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  appendStreamToken: (token) =>
    set((state) => ({ streamingContent: state.streamingContent + token })),

  finalizeStream: (conversationId, fullContent) => {
    const state = get();
    const assistantMessage: Message = {
      id: `stream-${Date.now()}`,
      role: "assistant",
      content: fullContent,
      created_at: new Date().toISOString(),
    };

    // Update conversation list to mark as recently updated
    const updatedConversations = state.conversations.map((c) =>
      c.id === conversationId
        ? { ...c, updated_at: new Date().toISOString() }
        : c
    );

    set({
      messages: [...state.messages, assistantMessage],
      isStreaming: false,
      streamingContent: "",
      activeConversationId: conversationId,
      conversations: updatedConversations,
    });
  },

  setStreaming: (streaming) =>
    set({ isStreaming: streaming, streamingContent: streaming ? "" : get().streamingContent }),

  reset: () =>
    set({
      messages: [],
      isStreaming: false,
      streamingContent: "",
      activeConversationId: null,
    }),
}));