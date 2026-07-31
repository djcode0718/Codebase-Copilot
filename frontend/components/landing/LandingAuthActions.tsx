'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { createClient } from '@/lib/supabase/client';
import { toast } from 'sonner';
import type { Session } from '@supabase/supabase-js';

type LandingAuthActionsProps = {
  initialSignedIn: boolean;
  initialIsGuest: boolean;
  initialEmail?: string;
};

export function LandingAuthActions({
  initialSignedIn,
  initialIsGuest,
  initialEmail,
}: LandingAuthActionsProps) {
  const router = useRouter();
  const supabase = useMemo(() => createClient(), []);
  const [signedIn, setSignedIn] = useState(initialSignedIn);
  const [isGuest, setIsGuest] = useState(initialIsGuest);
  const [email, setEmail] = useState(initialEmail);
  const [signingOut, setSigningOut] = useState(false);

  const applySession = useCallback((session: Session | null) => {
    setSignedIn(Boolean(session?.user));
    setIsGuest(Boolean(session?.user?.is_anonymous));
    setEmail(session?.user?.email ?? undefined);
  }, []);

  useEffect(() => {
    let mounted = true;

    async function syncSession() {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!mounted) {
        return;
      }

      applySession(session);
    }

    syncSession();

    return () => {
      mounted = false;
    };
  }, [supabase, applySession]);

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
    setSignedIn(false);
    setIsGuest(false);
    setEmail(undefined);
    router.push('/');
    router.refresh();
  }

  function openWorkspace() {
    router.push('/dashboard');
  }

  function openSignIn() {
    router.push('/auth/sign-in');
  }

  if (!signedIn) {
    return (
      <div className="flex items-center gap-2">
        <Button variant="outline" className="border-border" onClick={openSignIn}>
          Sign in
        </Button>
        <Button className="bg-brand text-green-950 hover:bg-green-400" onClick={openWorkspace}>
          Open workspace
        </Button>
      </div>
    );
  }

  if (isGuest) {
    return (
      <div className="flex items-center gap-2">
        <span className="hidden rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground sm:inline-flex">
          Guest session
        </span>
        <Button variant="outline" className="border-border" onClick={handleSignOut} disabled={signingOut}>
          {signingOut ? 'Signing out…' : 'Sign out'}
        </Button>
        <Button className="bg-brand text-green-950 hover:bg-green-400" onClick={openWorkspace}>
          Open workspace
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {email ? (
        <span className="hidden max-w-[220px] truncate rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground sm:inline-flex">
          {email}
        </span>
      ) : null}
      <Button variant="outline" className="border-border" onClick={handleSignOut} disabled={signingOut}>
        {signingOut ? 'Signing out…' : 'Sign out'}
      </Button>
      <Button className="bg-brand text-green-950 hover:bg-green-400" onClick={openWorkspace}>
        Open workspace
      </Button>
    </div>
  );
}


