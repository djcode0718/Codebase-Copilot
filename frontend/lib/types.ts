export type RepoStatus = "indexing" | "ready" | "failed";

export interface IndexRepoRequest {
  source: string;
}

export interface IndexRepoResponse {
  repo_id: string;
  index_name: string;
  status: RepoStatus;
  message: string;
}

export interface IndexProgressEvent {
  step: "cloning" | "filtering" | "parsing" | "embedding" | "indexing" | "summary" | "done" | "error";
  message: string;
  progress: number;
  file_count?: number;
  node_count?: number;
  index_name?: string;
}

export interface RepoStatusResponse {
  id: string;
  name: string;
  source_url: string;
  index_name: string;
  status: RepoStatus;
  file_count?: number;
  node_count?: number;
  llm_provider?: string;
  created_at?: string;
  indexed_at?: string;
}

export interface SuggestionsResponse {
  questions: string[];
}

export interface CreateSessionRequest {
  repo_id: string;
}

export interface CreateSessionResponse {
  chat_id: string;
  repo_id: string;
}

export type QueryMode = "code_lookup" | "architectural";

export interface RetrievedFile {
  path: string;
  score: number;
}

export interface MessageResponse {
  id: string;
  chat_id: string;
  role: "user" | "assistant";
  content: string;
  query_mode?: QueryMode;
  retrieved_files?: RetrievedFile[];
  latency_ms?: number;
  created_at?: string;
}

export interface ChatListItem {
  id: string;
  repo_id: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
}

export interface SendMessageRequest {
  query: string;
}

export interface TokenEvent {
  type: "token";
  content: string;
}

export interface MetadataEvent {
  type: "metadata";
  query_mode: QueryMode;
  retrieved_files: RetrievedFile[];
  latency_retrieval_ms: number;
  latency_llm_ms: number;
  latency_total_ms: number;
}

export interface DoneEvent {
  type: "done";
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export type ChatStreamEvent = TokenEvent | MetadataEvent | DoneEvent | ErrorEvent;

export interface RunEvalRequest {
  repo_id: string;
  index_name: string;
}

export interface EvalSummaryResponse {
  id?: string;
  repo_id: string;
  hit_rate: number;
  mrr: number;
  avg_faithfulness: number;
  avg_relevancy: number;
  mode_accuracy: number;
  avg_latency_total: number;
  avg_latency_retrieval: number;
  avg_latency_rerank: number;
  avg_latency_llm: number;
  colbert_enabled: boolean;
  total_queries: number;
  created_at?: string;
}

export interface EvalProgressEvent {
  type: "progress";
  message: string;
}

export interface EvalResultEvent {
  type: "result";
  summary: EvalSummaryResponse;
}

export interface EvalDoneEvent {
  type: "done";
}

export interface EvalErrorEvent {
  type: "error";
  message: string;
}

export type EvalStreamEvent = EvalProgressEvent | EvalResultEvent | EvalDoneEvent | EvalErrorEvent;

