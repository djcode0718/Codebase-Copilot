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
  indexed_at?: string;
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
  session_type?: 'main' | 'quick_ask';
  is_pinned?: boolean;
  is_favorite?: boolean;
  is_archived?: boolean;
  deleted_at?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface ConversationSummary {
  chat_id: string;
  repo_id: string;
  user_id: string;
  title?: string;
  executive_summary?: string;
  technical_summary?: string;
  key_decisions: string[];
  action_items: string[];
  risks_identified: string[];
  files_discussed: string[];
  services_discussed: string[];
  modules_discussed: string[];
  classes_discussed: string[];
  apis_discussed: string[];
  tags: string[];
  keywords: string[];
  updated_at?: string;
}

export interface ChatSearchResultItem {
  chat: Chat;
  matched_messages: Message[];
  snippets: string[];
}

export interface ChatSearchResponse {
  query: string;
  total: number;
  items: ChatSearchResultItem[];
}

export interface MemoryExportResponse {
  filename: string;
  format: 'md' | 'txt' | 'json' | 'pdf' | 'docx';
  content_type: string;
  content: string;
  meta: Record<string, unknown>;
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

// -- Repository Health Intelligence ------------------------------------------

export type HealthCategoryName =
  | 'Architecture'
  | 'Security'
  | 'Testing'
  | 'Documentation'
  | 'Performance'
  | 'Maintainability'
  | 'Technical Debt'
  | 'Dependencies'
  | 'Code Quality'
  | 'Scalability'
  | 'Observability'
  | 'Developer Experience';

export interface HealthTopLevel {
  repository_health: number;
  grade: string;
  status: string;
  trend: number;
  last_analysis: string;
  repository_size: 'Small' | 'Medium' | 'Large';
  language_detection: string[];
  framework_detection: string[];
}

export interface HealthCategoryScore {
  category: HealthCategoryName;
  score: number;
  grade: string;
  trend: number;
  explanation: string;
  detected_problems: string[];
  positive_findings: string[];
  recommendations: string[];
  affected_files: string[];
  affected_modules: string[];
}

export interface HealthFinding {
  id: string;
  category: HealthCategoryName;
  finding_type: 'problem' | 'positive';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  details: string;
  evidence: Record<string, unknown>;
  recommendation?: string;
  affected_files: string[];
  affected_modules: string[];
  expected_score_gain: number;
}

export interface HealthRecommendation {
  rank: number;
  title: string;
  description: string;
  category: HealthCategoryName;
  estimated_effort: string;
  expected_score_gain: number;
  impact_score: number;
  action_items: string[];
  affected_files: string[];
}

export interface HealthRun {
  run_id: string;
  repo_id: string;
  generated_at: string;
  top_level: HealthTopLevel;
  categories: HealthCategoryScore[];
  findings: HealthFinding[];
  recommendations: HealthRecommendation[];
  executive_summary: string;
  strengths: string[];
  weaknesses: string[];
  critical_risks: string[];
  architecture_risks: string[];
  security_risks: string[];
  performance_risks: string[];
  recommended_sprint: string[];
}

export interface HealthLatestResponse {
  repo_id: string;
  latest: HealthRun | null;
}

export interface HealthHistoryPoint {
  run_id: string;
  created_at: string;
  repository_health: number;
  grade: string;
  category_scores: Record<string, number>;
}

export interface HealthHistoryResponse {
  repo_id: string;
  points: HealthHistoryPoint[];
  improved_categories: string[];
  declining_categories: string[];
  new_risks: string[];
  resolved_risks: string[];
}

export interface HealthCategoryDetailResponse {
  repo_id: string;
  run_id: string;
  category: HealthCategoryName;
  score: HealthCategoryScore;
  findings: HealthFinding[];
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
