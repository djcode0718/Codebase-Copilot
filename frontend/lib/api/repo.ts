import { apiJson, apiStream, type AuthedFetch } from "@/lib/api/base";
import type { IndexProgressEvent, IndexRepoRequest, IndexRepoResponse, RepoStatusResponse, SuggestionsResponse } from "@/lib/types";

export function indexRepository(authedFetch: AuthedFetch, body: IndexRepoRequest) {
  return apiJson<IndexRepoResponse>(authedFetch, "/api/repo/index", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function streamIndexProgress(authedFetch: AuthedFetch, repoId: string) {
  return apiStream(authedFetch, `/api/repo/${repoId}/index-progress`);
}

export function getRepositories(authedFetch: AuthedFetch) {
  return apiJson<RepoStatusResponse[]>(authedFetch, "/api/repo/list");
}

export function getRepository(authedFetch: AuthedFetch, repoId: string) {
  return apiJson<RepoStatusResponse>(authedFetch, `/api/repo/${repoId}`);
}

export function deleteRepository(authedFetch: AuthedFetch, repoId: string) {
  return apiJson<{ message: string }>(authedFetch, `/api/repo/${repoId}`, {
    method: "DELETE",
  });
}

export function getSuggestions(authedFetch: AuthedFetch, repoId: string) {
  return apiJson<SuggestionsResponse>(authedFetch, `/api/repo/${repoId}/suggestions`);
}

export type { IndexProgressEvent };

