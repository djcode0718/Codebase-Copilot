"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteRepository, getRepositories, getRepository, getSuggestions, indexRepository } from "@/lib/api/repo";
import type { IndexRepoRequest } from "@/lib/types";
import { useAuthedFetch } from "@/hooks/use-authed-fetch";

export function useRepos() {
  const authedFetch = useAuthedFetch();
  return useQuery({
    queryKey: ["repos"],
    queryFn: () => getRepositories(authedFetch),
  });
}

export function useRepo(repoId: string) {
  const authedFetch = useAuthedFetch();
  return useQuery({
    queryKey: ["repo", repoId],
    queryFn: () => getRepository(authedFetch, repoId),
    enabled: Boolean(repoId),
  });
}

export function useSuggestions(repoId: string) {
  const authedFetch = useAuthedFetch();
  return useQuery({
    queryKey: ["suggestions", repoId],
    queryFn: () => getSuggestions(authedFetch, repoId),
    enabled: Boolean(repoId),
  });
}

export function useCreateRepo() {
  const authedFetch = useAuthedFetch();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: IndexRepoRequest) => indexRepository(authedFetch, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repos"] });
    },
  });
}

export function useDeleteRepo() {
  const authedFetch = useAuthedFetch();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (repoId: string) => deleteRepository(authedFetch, repoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repos"] });
    },
  });
}

