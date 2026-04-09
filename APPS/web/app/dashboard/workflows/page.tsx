"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { toast } from "@/lib/store/ui";

interface Workflow {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  trigger: { type: string };
  created_at: string;
}

interface WorkflowRun {
  id: string;
  workflow_id: string;
  status: string;
  trigger_type: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  pending:   "bg-yellow-100 text-yellow-800",
  running:   "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed:    "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-700",
};

export default function WorkflowsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [selectedRuns, setSelectedRuns] = useState<WorkflowRun[]>([]);
  const [selectedWfName, setSelectedWfName] = useState("");

  const { data: workflows = [], isLoading } = useQuery<Workflow[]>({
    queryKey: ["workflows"],
    queryFn: () => api.get("/workflows").then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (body: object) => api.post("/workflows", body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
      setShowCreate(false);
      setNewName("");
      toast.success("Workflow created");
    },
    onError: () => toast.error("Failed to create workflow"),
  });

  const runMutation = useMutation({
    mutationFn: (id: string) =>
      api.post(`/workflows/${id}/run`, {}).then((r) => r.data),
    onSuccess: (run) => {
      toast.success("Workflow triggered", `Run ID: ${run.id.slice(0, 8)}`);
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
    onError: () => toast.error("Failed to trigger workflow"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/workflows/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
      toast.success("Workflow deleted");
    },
    onError: () => toast.error("Failed to delete"),
  });

  async function loadRuns(wf: Workflow) {
    try {
      // Fetch runs for this workflow via the runs endpoint
      const { data } = await api.get(`/workflows?limit=1`); // placeholder
      setSelectedWfName(wf.name);
      setSelectedRuns([]);
    } catch {
      toast.error("Could not load runs");
    }
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Workflow list */}
      <div className="flex w-72 flex-col border-r bg-white">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="font-semibold text-gray-900">Workflows</h2>
          <button
            onClick={() => setShowCreate(true)}
            className="text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            + New
          </button>
        </div>

        {isLoading ? (
          <div className="flex flex-1 items-center justify-center text-sm text-gray-400">
            Loading…
          </div>
        ) : workflows.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 p-4 text-center text-sm text-gray-400">
            <span className="text-3xl">⚡</span>
            <p>No workflows yet</p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            {workflows.map((wf) => (
              <div
                key={wf.id}
                className="border-b px-4 py-3 hover:bg-gray-50 cursor-pointer"
                onClick={() => loadRuns(wf)}
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-gray-900 truncate">{wf.name}</p>
                  <span
                    className={`ml-2 h-2 w-2 rounded-full flex-shrink-0 ${
                      wf.is_active ? "bg-green-500" : "bg-gray-300"
                    }`}
                  />
                </div>
                <p className="mt-0.5 text-xs text-gray-500 capitalize">
                  {wf.trigger?.type ?? "manual"} trigger
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-y-auto p-6">
        {/* Create form */}
        {showCreate && (
          <div className="mb-6 rounded-xl border bg-white p-5 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold text-gray-900">New Workflow</h2>
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Workflow name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <input
                type="text"
                placeholder="Description (optional)"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <div className="flex gap-2">
                <button
                  onClick={() =>
                    createMutation.mutate({
                      name: newName,
                      description: newDesc,
                      trigger: { type: "manual" },
                      definition: { steps: [], edges: [] },
                    })
                  }
                  disabled={!newName.trim() || createMutation.isPending}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {createMutation.isPending ? "Creating…" : "Create"}
                </button>
                <button
                  onClick={() => setShowCreate(false)}
                  className="rounded-lg border px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Workflow actions */}
        {workflows.length > 0 && (
          <div className="space-y-4">
            <h1 className="text-2xl font-bold text-gray-900">
              {selectedWfName || "Select a workflow"}
            </h1>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {workflows.map((wf) => (
                <div key={wf.id} className="rounded-xl border bg-white p-4 shadow-sm">
                  <h3 className="font-semibold text-gray-900">{wf.name}</h3>
                  {wf.description && (
                    <p className="mt-1 text-xs text-gray-500">{wf.description}</p>
                  )}
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => runMutation.mutate(wf.id)}
                      disabled={runMutation.isPending}
                      className="flex-1 rounded-lg bg-blue-600 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      ▶ Run
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(wf.id)}
                      className="rounded-lg border px-3 py-1.5 text-xs text-red-500 hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {selectedRuns.length > 0 && (
              <div className="mt-6">
                <h2 className="mb-3 text-sm font-semibold text-gray-700">
                  Recent Runs — {selectedWfName}
                </h2>
                <div className="overflow-hidden rounded-xl border bg-white">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-gray-50 text-xs text-gray-500">
                        <th className="px-4 py-2 text-left">Run ID</th>
                        <th className="px-4 py-2 text-left">Status</th>
                        <th className="px-4 py-2 text-left">Triggered</th>
                        <th className="px-4 py-2 text-left">Started</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedRuns.map((run) => (
                        <tr key={run.id} className="border-b last:border-0">
                          <td className="px-4 py-2 font-mono text-xs text-gray-600">
                            {run.id.slice(0, 8)}
                          </td>
                          <td className="px-4 py-2">
                            <span
                              className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                                STATUS_COLORS[run.status] ?? "bg-gray-100 text-gray-700"
                              }`}
                            >
                              {run.status}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-xs text-gray-500">{run.trigger_type}</td>
                          <td className="px-4 py-2 text-xs text-gray-500">
                            {run.started_at
                              ? new Date(run.started_at).toLocaleString()
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {workflows.length === 0 && !showCreate && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center text-gray-400">
              <p className="text-5xl mb-4">⚡</p>
              <p className="text-lg font-medium text-gray-600">No workflows yet</p>
              <p className="mt-1 text-sm">Create a workflow to automate tasks with AI.</p>
              <button
                onClick={() => setShowCreate(true)}
                className="mt-4 rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              >
                Create your first workflow
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}