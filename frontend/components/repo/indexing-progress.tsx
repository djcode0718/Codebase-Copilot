"use client";

import clsx from "clsx";
import type { IndexProgressEvent } from "@/lib/types";

const steps: IndexProgressEvent["step"][] = [
  "cloning",
  "filtering",
  "parsing",
  "embedding",
  "indexing",
  "summary",
  "done",
];

export function IndexingProgress({
  events,
  finalState,
}: {
  events: IndexProgressEvent[];
  finalState: "idle" | "streaming" | "done" | "error";
}) {
  const latest = events[events.length - 1];
  const latestStep = latest?.step;

  return (
    <div className="space-y-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4">
      <div className="flex items-center justify-between text-sm">
        <p className="font-medium">Indexing progress</p>
        <span className="font-mono text-xs text-[var(--text-secondary)]">{latest?.progress ?? 0}%</span>
      </div>

      <div className="h-2 overflow-hidden rounded bg-[var(--bg-primary)]">
        <div className="h-full bg-[var(--accent)] transition-all" style={{ width: `${latest?.progress ?? 0}%` }} />
      </div>

      <div className="space-y-1.5 text-xs">
        {steps.map((step) => {
          const reached = events.some((event) => event.step === step);
          const isActive = latestStep === step && finalState === "streaming";
          return (
            <div key={step} className="flex items-center justify-between">
              <span className="capitalize text-[var(--text-secondary)]">{step}</span>
              <span
                className={clsx("inline-flex h-4 w-4 items-center justify-center rounded-full text-[10px]", {
                  "bg-zinc-700": !reached,
                  "bg-emerald-600": reached && !isActive,
                  "bg-amber-500 animate-pulse": isActive,
                })}
              />
            </div>
          );
        })}
      </div>

      {latest?.message ? <p className="text-xs text-[var(--text-secondary)]">{latest.message}</p> : null}

      {latestStep === "done" ? (
        <p className="text-xs text-[var(--success)]">
          Indexed {latest.file_count ?? 0} files, {latest.node_count ?? 0} chunks.
        </p>
      ) : null}

      {finalState === "error" ? <p className="text-xs text-[var(--error)]">The stream ended in error.</p> : null}
    </div>
  );
}

