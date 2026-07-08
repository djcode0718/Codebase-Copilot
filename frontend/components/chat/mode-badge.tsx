import clsx from "clsx";
import type { QueryMode } from "@/lib/types";

export function ModeBadge({ mode }: { mode?: QueryMode }) {
  if (!mode) {
    return null;
  }

  return (
    <span
      className={clsx("inline-flex rounded px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide", {
        "bg-[color:var(--mode-code)]/20 text-[color:var(--mode-code)]": mode === "code_lookup",
        "bg-[color:var(--mode-arch)]/20 text-[color:var(--mode-arch)]": mode === "architectural",
      })}
    >
      {mode}
    </span>
  );
}

