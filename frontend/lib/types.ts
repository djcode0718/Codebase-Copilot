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
  active_branch?: string;
  default_branch?: string;
  active_commit_sha?: string;
}

export interface BranchListResponse {
  current_branch: string;
  default_branch: string;
  recent_branches: string[];
  local_branches: string[];
  remote_branches: string[];
}

export interface BranchStatus {
  current_branch: string;
  default_branch: string;
  last_commit: string;
  author: string;
  commit_sha: string;
  short_commit_sha: string;
  ahead: number;
  behind: number;
  changed_files: number;
  changed_paths: string[];
  captured_at: string;
  indexed_at?: string | null;
  index_status: string;
  evaluation_status: string;
  health_score?: number | null;
}

export interface BranchActionResponse {
  message: string;
  current_branch: string;
  commit_sha: string;
  status: BranchStatus;
}

export interface MergeReadiness {
  overall_score: number;
  blocking_issues: string[];
  warnings: string[];
  suggested_reviewers: string[];
  estimated_review_time_minutes: number;
  deployment_risk: string;
  safe_to_merge: boolean;
}

export interface BranchComparison {
  base_branch: string;
  target_branch: string;
  changed_files: number;
  sample_changed_files: string[];
  architecture_changes: number;
  security_changes: number;
  performance_changes: number;
  technical_debt_changes: number;
  api_changes: number;
  database_changes: number;
  business_logic_changes: number;
  dependency_changes: number;
  risk_assessment: string;
  merge_readiness: MergeReadiness;
  ai_executive_summary: string;
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
      llm_provider?: string | null;
      llm_model?: string | null;
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
  role: 'system' | 'user' | 'assistant';
  content: string;
  query_mode?: QueryMode;          // assistant only
  retrieved_files?: RetrievedFile[]; // assistant only
  latency_ms?: number;             // maps to latency_total_ms from metadata
  token_count?: number;
  llm_provider?: string | null;
  llm_model?: string | null;
  metadata?: Record<string, unknown>;
  sequence?: number;
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
  last_message_at?: string | null;
  last_message_preview?: string | null;
  message_count?: number;
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
  mode?: 'quick' | 'standard' | 'deep' | 'benchmark';
  cache_key?: string | null;
  cache_hit?: boolean;
  ai_summary?: EvalAiSummary | null;
  top_recommendations?: EvalRecommendation[];
  efficiency?: EvalEfficiency | null;
  comparison?: EvalComparison | null;
  created_at: string;
}

export interface EvalAiSummary {
  overall_score: number;
  strengths: string[];
  weaknesses: string[];
  top_priority_improvements: string[];
  estimated_score_improvement: number;
}

export interface EvalRecommendation {
  rank: number;
  title: string;
  description: string;
  estimated_impact: number;
  expected_effort: 'Low' | 'Medium' | 'High';
  one_click_action?: {
    type: 'run_mode' | 'open_explorer' | 'open_settings';
    mode?: 'quick' | 'standard' | 'deep' | 'benchmark';
    target?: string;
  } | null;
}

export interface EvalEfficiency {
  cache_hit_rate: number;
  ai_calls: number;
  static_analysis_percentage: number;
  estimated_token_usage: number;
  estimated_cost_usd: number;
  estimated_savings_usd: number;
}

export interface EvalComparison {
  baseline_eval_id?: string | null;
  overall_score_delta: number;
  hit_rate_delta: number;
  faithfulness_delta: number;
  latency_delta_ms: number;
  estimated_cost_delta_usd: number;
}

export interface EvalHistoryPoint {
  id: string;
  created_at: string;
  overall_score: number;
  hit_rate: number;
  avg_faithfulness: number;
  avg_latency_total: number;
  cache_hit_rate: number;
  estimated_ai_cost_usd: number;
}

export interface EvalHistoryResponse {
  repo_id: string;
  points: EvalHistoryPoint[];
}

export interface EvalComparisonResponse {
  repo_id: string;
  current: EvalSummary | null;
  baseline: EvalSummary | null;
  comparison: EvalComparison | null;
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

// -- AI Engineering Review -----------------------------------------------------

export type ReviewSeverity = 'low' | 'medium' | 'high' | 'critical';
export type ReviewRiskLevel = 'low' | 'medium' | 'high';
export type ReviewTargetType = 'file' | 'files' | 'commit' | 'pr';

export interface ReviewFinding {
  id: string;
  severity: ReviewSeverity;
  file: string;
  code_area: string;
  finding: string;
  recommendation: string;
  suggested_fix: string;
  risk_level: ReviewRiskLevel;
  impact: string;
  complexity: string;
  estimated_effort: string;
  expected_benefit: string;
}

export interface ReviewRun {
  review_id: string;
  repo_id: string;
  target_type: ReviewTargetType;
  status: string;
  summary: string;
  findings: ReviewFinding[];
  changed_files: string[];
  commit_hash?: string | null;
  created_at?: string;
}

export interface ReviewHistoryItem {
  review_id: string;
  repo_id: string;
  target_type: ReviewTargetType;
  status: string;
  summary: string;
  commit_hash?: string | null;
  changed_files: string[];
  created_at?: string;
}

export interface ReviewListResponse {
  items: ReviewHistoryItem[];
}

export interface ReviewFixResponse {
  review_id: string;
  suggested_fix: string;
  target_file?: string | null;
  metadata: Record<string, unknown>;
}

// -- Repository Explorer ------------------------------------------------------

export type ExplorerHealth = 'healthy' | 'review_suggested' | 'critical' | 'not_analyzed';
export type ExplorerAiIndicator = 'recently_changed' | 'not_analyzed';

export interface ExplorerTreeNode {
  name: string;
  path: string;
  type: 'file' | 'folder';
  has_children: boolean;
  size: number;
  modified_at?: string | null;
  language: string;
  health: ExplorerHealth;
  ai_indicator: ExplorerAiIndicator;
  git_status: string;
  is_modified: boolean;
}

export interface ExplorerTreeResponse {
  repo_root: string;
  path: string;
  nodes: ExplorerTreeNode[];
  truncated: boolean;
  count: number;
}

export interface ExplorerFileDetails {
  path: string;
  language: string;
  content: string;
  sha256: string;
  summary: string;
  complexity: number;
  health: ExplorerHealth;
  dependencies: Record<string, unknown>;
  classes: string[];
  functions: string[];
  imports: string[];
  line_count: number;
  size: number;
  owner?: string | null;
  last_modified?: string | null;
}

export interface ExplorerReviewResult {
  review_id: string;
  scope: 'file' | 'files';
  overall_score: number;
  summary: string;
  findings: ReviewFinding[];
  changed_files: string[];
  sections: Record<string, unknown>;
  generated_at: string;
}

export interface ExplorerFixProposal {
  fix_id: string;
  path: string;
  current_content: string;
  suggested_content: string;
  diff: string;
  current_sha256: string;
  generated_at: string;
}

export interface ExplorerTestDiscoveryResult {
  tests: string[];
  count: number;
}

export interface ExplorerTestRunResult {
  status: 'passed' | 'failed' | 'timeout' | 'skipped';
  tests: string[];
  passed: number;
  failed: number;
  duration_seconds: number;
  coverage: number | null;
  output: string;
}

export interface ExplorerHistory {
  path: string;
  reviews: Array<Record<string, unknown>>;
  fixes: Array<Record<string, unknown>>;
  applied_fixes: Array<Record<string, unknown>>;
  rejected_fixes: Array<Record<string, unknown>>;
  test_runs: Array<Record<string, unknown>>;
  conversations: Array<Record<string, unknown>>;
}
