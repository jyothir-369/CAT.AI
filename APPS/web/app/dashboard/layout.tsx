"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/lib/store/auth";
import { useAuth } from "@/hooks/useAuth";

const NAV_ITEMS = [
  { href: "/dashboard/chat",         label: "Chat",         icon: "💬" },
  { href: "/dashboard/knowledge",    label: "Knowledge",    icon: "📚" },
  { href: "/dashboard/workflows",    label: "Workflows",    icon: "⚡" },
  { href: "/dashboard/integrations", label: "Integrations", icon: "🔗" },
  { href: "/dashboard/settings",     label: "Settings",     icon: "⚙️" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useAuthStore();
  const { logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside className="flex w-60 flex-col border-r bg-white">
        {/* Logo */}
        <div className="flex h-14 items-center border-b px-4">
          <span className="text-lg font-bold text-gray-900">CAT AI</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 overflow-y-auto p-2">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-gray-900 transition-colors"
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>

        {/* User info + logout */}
        <div className="border-t p-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-gray-900">{user.name}</p>
              <p className="truncate text-xs text-gray-500">{user.email}</p>
            </div>
            <button
              onClick={logout}
              className="text-xs text-gray-400 hover:text-gray-600"
              title="Sign out"
            >
              ↩
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {children}
      </main>
    </div>
  );
}