"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/auth-provider";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading, configError } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (configError) {
      return;
    }
    if (!loading && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname ?? "/repos")}`);
    }
  }, [loading, user, router, pathname, configError]);

  if (configError) {
    return <div className="p-6 text-sm text-[var(--error)]">{configError}</div>;
  }

  if (loading || !user) {
    return <div className="p-6 text-sm text-zinc-400">Checking authentication...</div>;
  }

  return <>{children}</>;
}
