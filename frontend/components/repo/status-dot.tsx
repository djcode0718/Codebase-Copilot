import clsx from "clsx";
import type { RepoStatus } from "@/lib/types";

export function StatusDot({ status }: { status: RepoStatus }) {
  return (
    <span
      className={clsx("inline-block size-2.5 rounded-full", {
        "bg-amber-400 animate-pulse": status === "indexing",
        "bg-emerald-400": status === "ready",
        "bg-rose-400": status === "failed",
      })}
      title={status}
    />
  );
}

