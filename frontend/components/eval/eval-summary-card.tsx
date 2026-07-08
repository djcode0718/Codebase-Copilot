import type { EvalSummaryResponse } from "@/lib/types";

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export function EvalSummaryCard({ summary }: { summary: EvalSummaryResponse }) {
  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4">
      <h3 className="mb-3 text-base font-semibold">Latest evaluation</h3>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Tile label="Hit Rate" value={percent(summary.hit_rate)} />
        <Tile label="MRR" value={summary.mrr.toFixed(3)} />
        <Tile label="Faithfulness" value={summary.avg_faithfulness.toFixed(3)} />
        <Tile label="Relevancy" value={summary.avg_relevancy.toFixed(3)} />
        <Tile label="Mode Accuracy" value={percent(summary.mode_accuracy)} />
        <Tile label="Queries" value={String(summary.total_queries)} />
        <Tile label="Latency Total" value={`${summary.avg_latency_total.toFixed(1)} ms`} />
        <Tile label="Latency Retrieval" value={`${summary.avg_latency_retrieval.toFixed(1)} ms`} />
        <Tile label="Latency Rerank" value={`${summary.avg_latency_rerank.toFixed(1)} ms`} />
        <Tile label="Latency LLM" value={`${summary.avg_latency_llm.toFixed(1)} ms`} />
      </div>
    </div>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--border-subtle)] bg-[var(--bg-primary)] p-3">
      <p className="text-xs text-[var(--text-secondary)]">{label}</p>
      <p className="mt-1 font-mono text-sm">{value}</p>
    </div>
  );
}

