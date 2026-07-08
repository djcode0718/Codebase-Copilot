import { API_BASE_URL } from "@/lib/config";

export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(status: number, message: string, detail?: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export type AuthedFetch = (input: string, init?: RequestInit) => Promise<Response>;

export async function apiJson<T>(authedFetch: AuthedFetch, path: string, init?: RequestInit): Promise<T> {
  const response = await authedFetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = "Request failed";
    try {
      const payload = await response.json();
      detail = payload.detail ?? payload.message ?? detail;
    } catch {
      // Ignore JSON parse errors.
    }
    throw new ApiError(response.status, detail, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function apiStream(authedFetch: AuthedFetch, path: string, init?: RequestInit): Promise<Response> {
  const response = await authedFetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    let detail = "Stream request failed";
    try {
      const payload = await response.json();
      detail = payload.detail ?? payload.message ?? detail;
    } catch {
      // Ignore JSON parse errors.
    }
    throw new ApiError(response.status, detail, detail);
  }
  return response;
}

