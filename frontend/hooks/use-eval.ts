"use client";

import { useQuery } from "@tanstack/react-query";
import { getLatestEvaluation } from "@/lib/api/eval";
import { useAuthedFetch } from "@/hooks/use-authed-fetch";

export function useLatestEval(repoId: string) {
  const authedFetch = useAuthedFetch();
  return useQuery({
    queryKey: ["evalLatest", repoId],
    queryFn: () => getLatestEvaluation(authedFetch, repoId),
    enabled: Boolean(repoId),
  });
}

