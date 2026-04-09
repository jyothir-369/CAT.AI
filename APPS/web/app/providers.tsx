"use client";

import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuth } from "@/hooks/useAuth";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,          // 1 minute
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function SessionRestorer({ children }: { children: React.ReactNode }) {
  const { restoreSession } = useAuth();
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    restoreSession().finally(() => setRestored(true));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!restored) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600" />
      </div>
    );
  }

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <SessionRestorer>{children}</SessionRestorer>
    </QueryClientProvider>
  );
}