"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useCreateRepo } from "@/hooks/use-repos";
import { useAuthedFetch } from "@/hooks/use-authed-fetch";
import { parseSSE } from "@/lib/sse";
import { streamIndexProgress } from "@/lib/api/repo";
import { toErrorMessage } from "@/lib/api/error-message";
import type { IndexProgressEvent } from "@/lib/types";
import { RepoSourceInput } from "@/components/repo/repo-source-input";
import { IndexingProgress } from "@/components/repo/indexing-progress";

export default function NewRepoPage() {
  const router = useRouter();
  const createRepo = useCreateRepo();
  const authedFetch = useAuthedFetch();

  const [events, setEvents] = useState<IndexProgressEvent[]>([]);
  const [streamState, setStreamState] = useState<"idle" | "streaming" | "done" | "error">("idle");
  const [repoId, setRepoId] = useState<string | null>(null);
  const streamStartedRef = useRef(false);

  useEffect(() => {
    if (!repoId || streamStartedRef.current || streamState !== "idle") {
      return;
    }

    let cancelled = false;
    streamStartedRef.current = true;
    setStreamState("streaming");

    const run = async () => {
      try {
        const response = await streamIndexProgress(authedFetch, repoId);
        for await (const event of parseSSE<IndexProgressEvent>(response)) {
          if (cancelled) {
            break;
          }

          setEvents((prev) => [...prev, event]);

          if (event.step === "error") {
            setStreamState("error");
            return;
          }

          if (event.step === "done") {
            setStreamState((current) => (current === "error" ? current : "done"));
            setTimeout(() => {
              router.push(`/repos/${repoId}`);
            }, 1500);
            return;
          }
        }
      } catch {
        setStreamState("error");
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [repoId, streamState, authedFetch, router]);

  const handleStart = async (source: string) => {
    setEvents([]);
    setStreamState("idle");
    streamStartedRef.current = false;

    const response = await createRepo.mutateAsync({ source });
    setRepoId(response.repo_id);
  };

  return (
    <section className="mx-auto grid w-full max-w-3xl gap-4">
      <h2 className="text-xl font-semibold">Add repository</h2>
      <RepoSourceInput disabled={createRepo.isPending || streamState === "streaming"} onSubmit={handleStart} />
      {events.length > 0 || streamState !== "idle" ? <IndexingProgress events={events} finalState={streamState} /> : null}
      {createRepo.error ? <p className="text-sm text-[var(--error)]">{toErrorMessage(createRepo.error)}</p> : null}
      {streamState === "error" ? (
        <p className="text-sm text-[var(--warning)]">
          Connection lost or indexing failed. Indexing may still be running on the backend; refresh to re-check repository status.
        </p>
      ) : null}
    </section>
  );
}
