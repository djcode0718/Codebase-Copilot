"use client";

import { useAuth } from "@/components/providers/auth-provider";

export function useAuthedFetch() {
  const { authedFetch } = useAuth();
  return authedFetch;
}

