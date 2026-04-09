/**
 * UI store — sidebar state, active modals, toast notifications.
 */
import { create } from "zustand";

export interface Toast {
  id: string;
  type: "success" | "error" | "info" | "warning";
  title: string;
  message?: string;
  duration?: number;
}

interface UIState {
  sidebarOpen: boolean;
  activeModal: string | null;
  toasts: Toast[];

  // Actions
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  openModal: (modalId: string) => void;
  closeModal: () => void;
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}

let toastCounter = 0;

export const useUIStore = create<UIState>((set, get) => ({
  sidebarOpen: true,
  activeModal: null,
  toasts: [],

  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  openModal: (modalId) => set({ activeModal: modalId }),
  closeModal: () => set({ activeModal: null }),

  addToast: (toast) => {
    const id = `toast-${++toastCounter}`;
    const duration = toast.duration ?? 4000;
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
    if (duration > 0) {
      setTimeout(() => get().removeToast(id), duration);
    }
  },

  removeToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

// Convenience helper for triggering toasts from outside components
export const toast = {
  success: (title: string, message?: string) =>
    useUIStore.getState().addToast({ type: "success", title, message }),
  error: (title: string, message?: string) =>
    useUIStore.getState().addToast({ type: "error", title, message }),
  info: (title: string, message?: string) =>
    useUIStore.getState().addToast({ type: "info", title, message }),
  warning: (title: string, message?: string) =>
    useUIStore.getState().addToast({ type: "warning", title, message }),
};