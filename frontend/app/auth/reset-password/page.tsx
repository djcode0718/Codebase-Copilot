'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { createClient } from '@/lib/supabase/client';
import { auditPasswordResetComplete } from '@/lib/auth-api';
import { validatePasswordForReset, validatePasswordsMatch, showPasswordRecoveryError } from '@/lib/auth-recovery-utils';
import { AuthBusyLabel, AuthRecoveryPageFrame, AuthSuccessPanel } from '@/components/auth/AuthRecoveryPrimitives';

export default function ResetPasswordPage() {
  const supabase = useMemo(() => createClient(), []);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;

    const passwordValidation = validatePasswordForReset(password);
    if (!passwordValidation.valid) {
      return;
    }

    const matchValidation = validatePasswordsMatch(password, confirmPassword);
    if (!matchValidation.valid) {
      return;
    }

    setLoading(true);
    const { error } = await supabase.auth.updateUser({ password });
    const {
      data: { session },
    } = await supabase.auth.getSession();

    await auditPasswordResetComplete({
      token: session?.access_token,
      email: session?.user?.email,
      success: !error,
    }).catch(() => undefined);

    setLoading(false);

    if (error) {
      showPasswordRecoveryError('reset');
      return;
    }

    setDone(true);
  }

  const card = done ? (
    <AuthSuccessPanel
      message="Your password has been updated successfully."
      ctaHref="/auth/sign-in"
      ctaLabel="Continue to sign in"
    />
  ) : (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor="password">New password</Label>
        <Input
          id="password"
          type="password"
          placeholder="At least 8 characters"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="h-11 bg-background border-border focus-visible:ring-brand"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="confirm-password">Confirm password</Label>
        <Input
          id="confirm-password"
          type="password"
          placeholder="Re-enter new password"
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          className="h-11 bg-background border-border focus-visible:ring-brand"
        />
      </div>
      <Button
        type="submit"
        disabled={loading}
        className="w-full bg-brand hover:bg-green-400 text-green-950 font-semibold transition-colors duration-200"
      >
        <AuthBusyLabel loading={loading} idleLabel="Update password" />
      </Button>
    </form>
  );

  return (
    <AuthRecoveryPageFrame
      heading="Set new password"
      subtitle="Create a new secure password for your Codebase Copilot account."
      authCard={card}
      footer={(
        <p className="text-center text-sm text-muted-foreground">
          Need a fresh link?{' '}
          <Link href="/auth/forgot-password" className="text-brand hover:underline">
            Request password reset
          </Link>
        </p>
      )}
    />
  );
}

