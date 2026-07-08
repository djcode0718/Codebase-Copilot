import { apiJson, apiStream, type AuthedFetch } from "@/lib/api/base";
import type { EvalSummaryResponse, RunEvalRequest } from "@/lib/types";

export function runEvaluation(authedFetch: AuthedFetch, body: RunEvalRequest) {
  return apiStream(authedFetch, "/api/eval/run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export function getLatestEvaluation(authedFetch: AuthedFetch, repoId: string) {
  return apiJson<EvalSummaryResponse | null>(authedFetch, `/api/eval/${repoId}/latest`);
}

