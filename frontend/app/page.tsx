"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/auth-provider";

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) {
      return;
    }
    router.replace(user ? "/repos" : "/login");
  }, [user, loading, router]);

  return <div className="p-6 text-sm text-[var(--text-secondary)]">Loading...</div>;
}
