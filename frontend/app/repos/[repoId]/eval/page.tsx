"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useRepo } from "@/hooks/use-repos";
import { useLatestEval } from "@/hooks/use-eval";
import { useAuthedFetch } from "@/hooks/use-authed-fetch";
import { runEvaluation } from "@/lib/api/eval";
import { parseSSE } from "@/lib/sse";
import { toErrorMessage } from "@/lib/api/error-message";
import type { EvalStreamEvent } from "@/lib/types";
import { EvalSummaryCard } from "@/components/eval/eval-summary-card";
import { EvalProgress } from "@/components/eval/eval-progress";

export default function EvalPage() {
  const params = useParams<{ repoId: string }>();
  const repoId = params.repoId;

  const authedFetch = useAuthedFetch();
  const repoQuery = useRepo(repoId);
  const latestEval = useLatestEval(repoId);

  const [events, setEvents] = useState<EvalStreamEvent[]>([]);
  const [running, setRunning] = useState(false);

  const runEval = async () => {
    if (!repoQuery.data) {
      return;
    }

    setEvents([]);
    setRunning(true);

    try {
      const response = await runEvaluation(authedFetch, {
        repo_id: repoId,
        index_name: repoQuery.data.index_name,
      });

      for await (const event of parseSSE<EvalStreamEvent>(response)) {
        setEvents((prev) => [...prev, event]);
        if (event.type === "error") {
          setRunning(false);
          return;
        }
        if (event.type === "done") {
          setRunning(false);
          await latestEval.refetch();
          return;
        }
      }
    } catch (error) {
      setEvents((prev) => [
        ...prev,
        {
          type: "error",
          message: toErrorMessage(error),
        },
      ]);
      setRunning(false);
    }
  };

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Evaluation</h2>
        <button
          type="button"
          onClick={() => void runEval()}
          disabled={running || repoQuery.data?.status !== "ready"}
          className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm text-white disabled:opacity-60"
        >
          {running ? "Running..." : "Run evaluation"}
        </button>
      </div>

      <p className="text-sm text-[var(--text-secondary)]">An evaluation run typically takes 3-10 minutes.</p>

      {repoQuery.error ? <p className="text-sm text-[var(--error)]">{toErrorMessage(repoQuery.error)}</p> : null}
      {latestEval.error ? <p className="text-sm text-[var(--error)]">{toErrorMessage(latestEval.error)}</p> : null}

      {latestEval.data ? (
        <EvalSummaryCard summary={latestEval.data} />
      ) : (
        <div className="rounded-lg border border-dashed border-[var(--border-subtle)] p-6 text-sm text-[var(--text-secondary)]">
          No evaluation run yet.
        </div>
      )}

      {events.length > 0 ? <EvalProgress events={events} /> : null}
    </section>
  );
}
