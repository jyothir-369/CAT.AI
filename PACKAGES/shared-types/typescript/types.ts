/**
 * CAT AI — Shared TypeScript types.
 * Auto-generation target: these mirror packages/shared-types/python/schemas.py
 * In production, generate from OpenAPI spec via openapi-typescript.
 */

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// ── Conversation ──────────────────────────────────────────────────────────────

export type MessageRole = "user" | "assistant" | "system" | "tool" | "tool_result";

export interface Message {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  tokens_in: number;
  tokens_out: number;
  model_id?: string | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  org_id: string;
  user_id: string;
  title?: string | null;
  model_id?: string | null;
  summary?: string | null;
  created_at: string;
  updated_at: string;
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  model_id?: string;
  kb_id?: string;
  use_memory?: boolean;
}

export interface StreamChunk {
  token?: string;
  done?: boolean;
  conversation_id?: string;
  error?: string;
}

// ── Knowledge ─────────────────────────────────────────────────────────────────

export interface KnowledgeBase {
  id: string;
  org_id: string;
  name: string;
  description?: string | null;
  embedding_model: string;
  chunk_strategy: string;
  doc_count: number;
  created_at: string;
}

export interface ChunkResult {
  content: string;
  chunk_id: string;
  document_id: string;
  metadata: Record<string, unknown>;
}

export interface KBQueryResponse {
  query: string;
  results: ChunkResult[];
}

// ── Files ─────────────────────────────────────────────────────────────────────

export type FileStatus = "pending" | "processing" | "ready" | "failed";

export interface UploadedFile {
  id: string;
  filename: string;
  mime_type?: string | null;
  size_bytes: number;
  status: FileStatus;
  knowledge_base_id?: string | null;
  created_at: string;
}

export interface PresignedUrlResponse {
  file_id: string;
  upload_url: string;
  s3_key: string;
}

// ── Workflow ──────────────────────────────────────────────────────────────────

export type TriggerType = "webhook" | "cron" | "manual" | "event";
export type StepType = "llm" | "condition" | "api_call" | "retrieval" | "approval" | "transform" | "loop" | "tool";
export type WorkflowRunStatus = "pending" | "running" | "completed" | "failed" | "cancelled";
export type StepRunStatus = "pending" | "running" | "completed" | "failed" | "awaiting_approval" | "skipped";

export interface WorkflowStep {
  id: string;
  type: StepType;
  config: Record<string, unknown>;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
}

export interface WorkflowEdge {
  from: string;
  to: string;
  condition?: string;
}

export interface WorkflowDefinition {
  steps: WorkflowStep[];
  edges: WorkflowEdge[];
}

export interface Workflow {
  id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  trigger: { type: TriggerType; config?: Record<string, unknown> };
  created_at: string;
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  version: number;
  trigger_type: string;
  status: WorkflowRunStatus;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
}

// ── Integration ───────────────────────────────────────────────────────────────

export type IntegrationProvider = "slack" | "gmail" | "notion" | "google_sheets";

export interface Integration {
  id: string;
  provider: IntegrationProvider | string;
  scopes: string[];
  expires_at?: string | null;
  created_at: string;
}

// ── Billing ───────────────────────────────────────────────────────────────────

export type Plan = "free" | "pro" | "team" | "enterprise";

export interface Subscription {
  plan: Plan;
  status: string;
  current_period_end?: string | null;
  stripe_customer_id?: string | null;
}

export interface UsageSummary {
  org_id: string;
  period_start?: string;
  period_end?: string;
  total_requests: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_tokens: number;
  total_cost_usd: number;
}

// ── Notifications ─────────────────────────────────────────────────────────────

export interface Notification {
  id: string;
  type: string;
  title: string;
  body?: string | null;
  read_at?: string | null;
  action_url?: string | null;
  created_at: string;
}

// ── API errors ────────────────────────────────────────────────────────────────

export interface APIError {
  detail: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}