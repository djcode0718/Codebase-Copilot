import type { EvalStreamEvent } from "@/lib/types";

export function EvalProgress({ events }: { events: EvalStreamEvent[] }) {
  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4">
      <h3 className="mb-2 text-sm font-semibold">Evaluation progress</h3>
      <ul className="space-y-1 text-sm text-[var(--text-secondary)]">
        {events.map((event, index) => (
          <li key={index}>
            {event.type === "progress" ? event.message : event.type === "error" ? `Error: ${event.message}` : event.type}
          </li>
        ))}
      </ul>
    </div>
  );
}

