"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { useState } from "react";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/auth";
import { toast } from "@/lib/store/ui";

interface Subscription {
  plan: string;
  status: string;
  current_period_end: string | null;
}

interface UsageSummary {
  total_requests: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost_usd: number;
}

const PLAN_LABELS: Record<string, { label: string; color: string }> = {
  free:       { label: "Free",       color: "text-gray-600 bg-gray-100" },
  pro:        { label: "Pro",        color: "text-blue-700 bg-blue-100" },
  team:       { label: "Team",       color: "text-purple-700 bg-purple-100" },
  enterprise: { label: "Enterprise", color: "text-amber-700 bg-amber-100" },
};

export default function SettingsPage() {
  const { user } = useAuthStore();
  const [tab, setTab] = useState<"profile" | "billing" | "usage">("billing");

  const { data: subscription } = useQuery<Subscription>({
    queryKey: ["subscription"],
    queryFn: () => api.get("/billing/subscription").then((r) => r.data),
  });

  const { data: usage } = useQuery<UsageSummary>({
    queryKey: ["usage"],
    queryFn: () => api.get("/usage/summary?days=30").then((r) => r.data),
    enabled: tab === "usage",
  });

  const portalMutation = useMutation({
    mutationFn: () =>
      api.post("/billing/portal", { return_url: window.location.href }).then((r) => r.data),
    onSuccess: (data: { portal_url: string }) => {
      window.location.href = data.portal_url;
    },
    onError: () => toast.error("Failed to open billing portal"),
  });

  const checkoutMutation = useMutation({
    mutationFn: (plan: string) =>
      api.post("/billing/checkout", { plan }).then((r) => r.data),
    onSuccess: (data: { checkout_url: string }) => {
      window.location.href = data.checkout_url;
    },
    onError: () => toast.error("Failed to start checkout"),
  });

  const planMeta = PLAN_LABELS[subscription?.plan ?? "free"] ?? PLAN_LABELS["free"];

  return (
    <div className="flex h-full flex-col overflow-y-auto p-6">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Settings</h1>

      {/* Tabs */}
      <div className="mb-6 flex gap-1 rounded-lg bg-gray-100 p-1 w-fit">
        {(["billing", "usage", "profile"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium capitalize transition-colors ${
              tab === t
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Billing tab */}
      {tab === "billing" && (
        <div className="space-y-4 max-w-2xl">
          <div className="rounded-xl border bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-900">Current Plan</h2>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${planMeta.color}`}>
                {planMeta.label}
              </span>
            </div>

            {subscription?.current_period_end && (
              <p className="text-sm text-gray-500 mb-4">
                Renews {new Date(subscription.current_period_end).toLocaleDateString()}
              </p>
            )}

            <div className="flex gap-3">
              {subscription?.plan !== "pro" && (
                <button
                  onClick={() => checkoutMutation.mutate("pro")}
                  disabled={checkoutMutation.isPending}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  Upgrade to Pro — $20/mo
                </button>
              )}
              {subscription?.plan !== "team" && (
                <button
                  onClick={() => checkoutMutation.mutate("team")}
                  disabled={checkoutMutation.isPending}
                  className="rounded-lg border px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  Upgrade to Team — $79/mo
                </button>
              )}
              {subscription?.plan !== "free" && (
                <button
                  onClick={() => portalMutation.mutate()}
                  disabled={portalMutation.isPending}
                  className="rounded-lg border px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                >
                  Manage subscription
                </button>
              )}
            </div>
          </div>

          {/* Plan comparison */}
          <div className="rounded-xl border bg-white p-5 shadow-sm">
            <h2 className="mb-4 font-semibold text-gray-900">Plan Comparison</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 border-b">
                  <th className="pb-2 text-left">Feature</th>
                  <th className="pb-2 text-center">Free</th>
                  <th className="pb-2 text-center">Pro</th>
                  <th className="pb-2 text-center">Team</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {[
                  ["Messages/day", "50", "Unlimited", "Unlimited"],
                  ["Storage",      "10 MB", "5 GB",   "50 GB"],
                  ["Workspaces",   "1",     "1",       "5"],
                  ["All models",   "✗",     "✓",       "✓"],
                  ["Automations",  "✗",     "Basic",   "Full"],
                  ["RBAC",         "✗",     "✗",       "✓"],
                ].map(([feat, ...vals]) => (
                  <tr key={feat}>
                    <td className="py-2 text-gray-700">{feat}</td>
                    {vals.map((v, i) => (
                      <td key={i} className="py-2 text-center text-gray-600">{v}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Usage tab */}
      {tab === "usage" && (
        <div className="max-w-2xl space-y-4">
          {usage ? (
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "Total Requests",  value: usage.total_requests.toLocaleString() },
                { label: "Tokens In",       value: usage.total_tokens_in.toLocaleString() },
                { label: "Tokens Out",      value: usage.total_tokens_out.toLocaleString() },
                { label: "Cost (30 days)",  value: `$${usage.total_cost_usd.toFixed(4)}` },
              ].map(({ label, value }) => (
                <div key={label} className="rounded-xl border bg-white p-5 shadow-sm">
                  <p className="text-sm text-gray-500">{label}</p>
                  <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-gray-400">Loading usage data…</div>
          )}
        </div>
      )}

      {/* Profile tab */}
      {tab === "profile" && (
        <div className="max-w-md space-y-4">
          <div className="rounded-xl border bg-white p-5 shadow-sm">
            <h2 className="mb-4 font-semibold text-gray-900">Profile</h2>
            <div className="space-y-3 text-sm">
              <div>
                <span className="text-gray-500">Name:</span>
                <span className="ml-2 font-medium text-gray-900">{user?.name}</span>
              </div>
              <div>
                <span className="text-gray-500">Email:</span>
                <span className="ml-2 font-medium text-gray-900">{user?.email}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}