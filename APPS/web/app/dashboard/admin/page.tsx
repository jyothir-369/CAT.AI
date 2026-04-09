"use client";

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

interface PlatformMetrics {
  total_users: number;
  active_users_30d: number;
  total_orgs: number;
  total_conversations: number;
  total_requests_30d: number;
  total_tokens_30d: number;
  total_cost_usd_30d: number;
}

interface UserRow {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  is_superadmin: boolean;
  created_at: string;
  last_login: string | null;
}

export default function AdminPage() {
  const { user } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (user && !(user as { is_superadmin?: boolean }).is_superadmin) {
      router.push("/dashboard/chat");
    }
  }, [user, router]);

  const { data: metrics, isLoading: metricsLoading } = useQuery<PlatformMetrics>({
    queryKey: ["admin-metrics"],
    queryFn: () => api.get("/admin/metrics").then((r) => r.data),
  });

  const { data: users = [], isLoading: usersLoading } = useQuery<UserRow[]>({
    queryKey: ["admin-users"],
    queryFn: () => api.get("/admin/users?limit=50").then((r) => r.data),
  });

  return (
    <div className="flex h-full flex-col overflow-y-auto p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">Platform-wide metrics and user management.</p>
      </div>

      {/* Metrics grid */}
      {metricsLoading ? (
        <div className="text-sm text-gray-400">Loading metrics…</div>
      ) : metrics ? (
        <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {[
            { label: "Total Users",      value: metrics.total_users.toLocaleString() },
            { label: "Active (30d)",     value: metrics.active_users_30d.toLocaleString() },
            { label: "Workspaces",       value: metrics.total_orgs.toLocaleString() },
            { label: "Conversations",    value: metrics.total_conversations.toLocaleString() },
            { label: "Requests (30d)",   value: metrics.total_requests_30d.toLocaleString() },
            { label: "Tokens (30d)",     value: (metrics.total_tokens_30d / 1_000).toFixed(1) + "K" },
            { label: "Cost (30d)",       value: `$${metrics.total_cost_usd_30d.toFixed(2)}` },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-xl border bg-white p-4 shadow-sm">
              <p className="text-xs text-gray-500">{label}</p>
              <p className="mt-1 text-xl font-bold text-gray-900">{value}</p>
            </div>
          ))}
        </div>
      ) : null}

      {/* Users table */}
      <div className="rounded-xl border bg-white shadow-sm">
        <div className="border-b px-4 py-3">
          <h2 className="font-semibold text-gray-900">Users</h2>
        </div>
        {usersLoading ? (
          <div className="p-6 text-sm text-gray-400">Loading users…</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 text-xs text-gray-500">
                  <th className="px-4 py-2 text-left">Name</th>
                  <th className="px-4 py-2 text-left">Email</th>
                  <th className="px-4 py-2 text-left">Status</th>
                  <th className="px-4 py-2 text-left">Role</th>
                  <th className="px-4 py-2 text-left">Joined</th>
                  <th className="px-4 py-2 text-left">Last Login</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium text-gray-900">{u.name}</td>
                    <td className="px-4 py-2 text-gray-600">{u.email}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          u.is_active
                            ? "bg-green-100 text-green-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {u.is_active ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-500">
                      {u.is_superadmin ? (
                        <span className="font-medium text-amber-700">Superadmin</span>
                      ) : (
                        "User"
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-500">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-500">
                      {u.last_login
                        ? new Date(u.last_login).toLocaleDateString()
                        : "Never"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}