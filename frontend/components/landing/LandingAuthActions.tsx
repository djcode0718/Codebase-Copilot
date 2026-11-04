'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { createClient } from '@/lib/supabase/client';
import { auditLogout } from '@/lib/auth-api';
import { clearUrlHash, getFriendlyAuthErrorMessage, parseAuthHash, sanitizeNextPath } from '@/lib/auth-hash';
import { clearAccountStorage } from '@/lib/auth-storage';
import { toast } from 'sonner';
import type { Session, User } from '@supabase/supabase-js';

type LandingAuthActionsProps = {
  initialSignedIn: boolean;
  initialIsGuest: boolean;
  initialEmail?: string;
};

type AuthState = {
  signedIn: boolean;
  isGuest: boolean;
  email?: string;
};

export function LandingAuthActions({
  initialSignedIn,
  initialIsGuest,
  initialEmail,
}: LandingAuthActionsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const supabase = useMemo(() => createClient(), []);
  const [authState, setAuthState] = useState<AuthState>({
    signedIn: initialSignedIn,
    isGuest: initialIsGuest,
    email: initialEmail,
  });
  const [isResolving, setIsResolving] = useState(!initialSignedIn);
  const [signingOut, setSigningOut] = useState(false);
  const oauthCode = searchParams.get('code');
  const oauthNext = searchParams.get('next') ?? '/dashboard';

  const [hasAuthHash] = useState(() => {
    if (typeof window === 'undefined' || !window.location.hash) return false;
    const hash = window.location.hash;
    return Boolean(hash.includes('access_token=') || hash.includes('error='));
  });

  const applySession = useCallback((session: Session | null) => {
    setAuthState({
      signedIn: Boolean(session?.user),
      isGuest: Boolean(session?.user?.is_anonymous),
      email: session?.user?.email ?? undefined,
    });
    setIsResolving(false);
  }, []);

  const applyUser = useCallback((user: User | null) => {
    setAuthState({
      signedIn: Boolean(user),
      isGuest: Boolean(user?.is_anonymous),
      email: user?.email ?? undefined,
    });
    setIsResolving(false);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.location.hash) return;
    const parsed = parseAuthHash(window.location.hash);
    if (parsed.hasError) {
      toast.error(getFriendlyAuthErrorMessage(parsed));
      clearUrlHash();
    } else if (parsed.hasTokens) {
      clearUrlHash();
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    async function syncUser() {
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (!mounted) {
        return;
      }

      applyUser(user);
    }

    syncUser();

    return () => {
      mounted = false;
    };
  }, [supabase, applyUser]);

  useEffect(() => {
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      applySession(session);

      if ((oauthCode || hasAuthHash) && session?.user && !session.user.is_anonymous) {
        const targetPath = sanitizeNextPath(oauthNext, '/dashboard');
        router.replace(targetPath);
        router.refresh();
      }
    });

    return () => subscription.unsubscribe();
  }, [supabase, applySession, oauthCode, hasAuthHash, oauthNext, router]);

  useEffect(() => {
    if (!oauthCode && !hasAuthHash) return;

    async function handleRootOAuthCallback() {
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (user && !user.is_anonymous) {
        const targetPath = sanitizeNextPath(oauthNext, '/dashboard');
        router.replace(targetPath);
        router.refresh();
      }
    }

    void handleRootOAuthCallback();
  }, [oauthCode, hasAuthHash, oauthNext, router, supabase]);

  async function handleSignOut() {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    await auditLogout({
      token: session?.access_token,
      email: session?.user?.email,
      sessionId: session?.access_token?.slice(-16),
    }).catch(() => undefined);

    setSigningOut(true);
    queryClient.clear();
    clearAccountStorage();
    const { error } = await supabase.auth.signOut();
    setSigningOut(false);

    if (error) {
      toast.error(error.message);
      return;
    }

    toast.success('Signed out');
    setAuthState({ signedIn: false, isGuest: false, email: undefined });
    setIsResolving(false);
    router.push('/');
    router.refresh();
  }

  function openSignIn() {
    router.push('/auth/sign-in');
  }

  if (isResolving) {
    return (
      <div className="flex items-center gap-2">
        <span className="hidden rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground sm:inline-flex">
          Checking session...
        </span>
      </div>
    );
  }

  if (!authState.signedIn) {
    return (
      <div className="flex items-center gap-2">
        <Button variant="outline" className="border-border" onClick={openSignIn}>
          Sign in
        </Button>
      </div>
    );
  }

  if (authState.isGuest) {
    return (
      <div className="flex items-center gap-2">
        <span className="hidden rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground sm:inline-flex">
          Guest session
        </span>
        <Button variant="outline" className="border-border" onClick={handleSignOut} disabled={signingOut}>
          {signingOut ? 'Signing out…' : 'Sign out'}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {authState.email ? (
        <span className="hidden max-w-[220px] truncate rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground sm:inline-flex">
          {authState.email}
        </span>
      ) : null}
      <Button variant="outline" className="border-border" onClick={handleSignOut} disabled={signingOut}>
        {signingOut ? 'Signing out…' : 'Sign out'}
      </Button>
    </div>
  );
}
