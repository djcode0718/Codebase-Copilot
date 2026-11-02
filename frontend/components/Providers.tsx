'use client';
/**
 * components/Providers.tsx
 * Client-side provider tree: React Query + Supabase auth context
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import ThemeProvider from '@/components/ThemeProvider';
import { createClient } from '@/lib/supabase/client';
import { clearAccountStorage } from '@/lib/auth-storage';

export default function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,      // 30 s
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  const previousUserIdRef = useRef<string | null | undefined>(undefined);

  useEffect(() => {
    const supabase = createClient();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      const currentUserId = session?.user?.id ?? null;

      if (event === 'INITIAL_SESSION') {
        previousUserIdRef.current = currentUserId;
        return;
      }

      if (event === 'SIGNED_OUT') {
        queryClient.clear();
        clearAccountStorage();
        previousUserIdRef.current = null;
        return;
      }

      // Handle direct user switch (switching between authenticated accounts)
      if (
        previousUserIdRef.current !== undefined &&
        previousUserIdRef.current !== null &&
        currentUserId !== null &&
        previousUserIdRef.current !== currentUserId
      ) {
        queryClient.clear();
        clearAccountStorage(previousUserIdRef.current);
      }

      // Preserve query cache on ordinary token refreshes for the same user
      previousUserIdRef.current = currentUserId;
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [queryClient]);

  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  );
}
