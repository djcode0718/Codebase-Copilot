/**
 * lib/types.ts
 * Verified TypeScript types — sourced directly from backend source code.
 * All fields confirmed against api/services/*.py and app/retrieval/*.py
 */

// ── Repository ─────────────────────────────────────────────────────────────

export interface Repo {
  id: string;
  name: string;
  source_url: string;
  index_name: string;
  status: 'indexing' | 'ready' | 'failed';
  file_count?: number;    // populated only after 'done' event
  node_count?: number;    // populated only after 'done' event
  llm_provider?: string;
  created_at: string;
}

// ── Indexing SSE ───────────────────────────────────────────────────────────
// Verified step strings from api/services/indexing_service.py lines 269-366
// NOTE: 'error' can be the FIRST event (Ollama not running / model missing)
// NOTE: 'summary' at progress:90 is a "finalising" message, not a summary index

export type IndexingStepName =
  | 'cloning'    // progress: 10
  | 'filtering'  // progress: 20
  | 'parsing'    // progress: 40
  | 'embedding'  // progress: 65
  | 'summary'    // progress: 90
  | 'done'       // progress: 100 — includes index_name, file_count, node_count
  | 'error';     // progress: 100 — can arrive at any point, including first

export interface IndexingEvent {
  step: IndexingStepName;
  message: string;
  progress: number; // 0–100
  // Only present on 'done':
  index_name?: string;
  file_count?: number;
  node_count?: number;
}

// ── Chat SSE ────────────────────────────────────────────────────────────────
// Verified from api/services/chat_service.py lines 188, 205-213, 217, 220
// IMPORTANT: latency_rerank_ms is NOT emitted — rerank cost is in latency_total_ms

export interface RetrievedFile {
  path: string;   // n.node.metadata.get("path", "unknown")
  score: number;  // round(float(n.score or 0.0), 4) — 4 decimal places
}

export type QueryMode = 'code_lookup' | 'architectural';

export type ChatEvent =
  | { type: 'token'; content: string }
  | {
      type: 'metadata';
      query_mode: QueryMode;
      retrieved_files: RetrievedFile[];
      latency_retrieval_ms: number;
      latency_llm_ms: number;
      latency_total_ms: number;
      // NOTE: latency_rerank_ms is NOT in this event
    }
  | { type: 'suggestions'; questions: string[] }
  | { type: 'done' }
  | { type: 'error'; message: string };

// ── Message (from Supabase) ─────────────────────────────────────────────────
// Verified from api/services/supabase_service.py save_message (lines 145-168)

export interface Message {
  id: string;
  chat_id: string;
  role: 'user' | 'assistant';
  content: string;
  query_mode?: QueryMode;          // assistant only
  retrieved_files?: RetrievedFile[]; // assistant only
  latency_ms?: number;             // maps to latency_total_ms from metadata
  created_at: string;
}

// ── Chat session ────────────────────────────────────────────────────────────

export interface Chat {
  id: string;
  repo_id: string;
  user_id: string;
  title?: string;
  created_at: string;
}

// ── Evaluation ─────────────────────────────────────────────────────────────
// Verified from api/services/supabase_service.py save_evaluation (lines 184-207)
// and api/routers/eval.py EvalSummaryResponse (lines 141-156)
// IMPORTANT: total_queries is NOT a top-level DB column — lives in result_json

export interface EvalSummary {
  id: string;
  repo_id: string;
  // Top-level DB columns (all present after a completed eval):
  hit_rate: number;               // 0.0–1.0
  mrr: number;                    // 0.0–1.0
  avg_faithfulness: number;       // 0.0–1.0
  avg_relevancy: number;          // 0.0–1.0
  mode_accuracy: number;          // 0.0–1.0
  avg_latency_total: number;      // ms
  avg_latency_retrieval: number;  // ms
  avg_latency_rerank: number;     // ms
  avg_latency_llm: number;        // ms
  colbert_enabled: boolean;
  // From result_json (read via: eval_record.get("result_json", {}).get("total_queries", 0))
  total_queries?: number;
  created_at: string;
}

// Eval SSE events from api/routers/eval.py lines 59-108
export type EvalEvent =
  | { type: 'progress'; message: string }
  | { type: 'result'; summary: EvalSummary }
  | { type: 'done' }
  | { type: 'error'; message: string };

// ── Suggestions ─────────────────────────────────────────────────────────────

export interface SuggestionsResponse {
  questions: string[];
}

// ── API responses ────────────────────────────────────────────────────────────

export interface IndexRepoResponse {
  repo_id: string;
  index_name: string;
  status: 'indexing';
  message: string;
}

export interface CreateSessionResponse {
  chat_id: string;
  repo_id: string;
}

// ── UI state helpers ─────────────────────────────────────────────────────────

export type StepStatus = 'pending' | 'active' | 'done' | 'error';

export interface PipelineStep {
  id: IndexingStepName;
  label: string;
  description: string;
  status: StepStatus;
  message?: string;
  elapsedMs?: number;
  startedAt?: number;
}
