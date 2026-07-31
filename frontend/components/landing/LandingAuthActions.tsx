'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { createClient } from '@/lib/supabase/client';
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
  const supabase = useMemo(() => createClient(), []);
  const [authState, setAuthState] = useState<AuthState>({
    signedIn: initialSignedIn,
    isGuest: initialIsGuest,
    email: initialEmail,
  });
  const [isResolving, setIsResolving] = useState(!initialSignedIn);
  const [signingOut, setSigningOut] = useState(false);

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
    });

    return () => subscription.unsubscribe();
  }, [supabase, applySession]);

  async function handleSignOut() {
    setSigningOut(true);
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


