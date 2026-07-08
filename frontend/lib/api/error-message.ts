import { ApiError } from "@/lib/api/base";

export function toErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Session expired or invalid token. Please sign in again.";
    }
    if (error.status === 403) {
      return "Access denied: this resource belongs to another user.";
    }
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Unexpected error";
}

