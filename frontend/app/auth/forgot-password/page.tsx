'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { createClient } from '@/lib/supabase/client';
import { auditPasswordResetRequest, normalizeEmail } from '@/lib/auth-api';
import { validateEmailForRecovery, getPasswordResetRedirectUrl, showPasswordRecoveryError } from '@/lib/auth-recovery-utils';
import { AuthExperienceShell } from '@/components/auth/AuthExperienceShell';
import { AuthBusyLabel, AuthScreenMotion, AuthSuccessPanel } from '@/components/auth/AuthRecoveryPrimitives';

export default function ForgotPasswordPage() {
  const supabase = useMemo(() => createClient(), []);
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;

    const normalizedEmail = normalizeEmail(email);
    const validation = validateEmailForRecovery(normalizedEmail);
    if (!validation.valid) {
      return;
    }

    setLoading(true);

    const redirectTo = getPasswordResetRedirectUrl();
    const { error } = await supabase.auth.resetPasswordForEmail(normalizedEmail, { redirectTo });
    await auditPasswordResetRequest(normalizedEmail).catch(() => undefined);
    setLoading(false);

    if (error) {
      showPasswordRecoveryError('forgot');
      return;
    }

    setDone(true);
  }

  const card = done ? (
    <AuthSuccessPanel
      message="If an account exists, password reset instructions were sent to your email."
      ctaHref="/auth/sign-in"
      ctaLabel="Back to sign in"
    />
  ) : (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={() => setEmail((prev) => normalizeEmail(prev))}
          required
          autoComplete="email"
          className="h-11 bg-background border-border focus-visible:ring-brand"
        />
      </div>
      <Button
        type="submit"
        disabled={loading}
        className="w-full bg-brand hover:bg-green-400 text-green-950 font-semibold transition-colors duration-200"
      >
        <AuthBusyLabel loading={loading} idleLabel="Send reset link" />
      </Button>
    </form>
  );

  return (
    <AuthScreenMotion>
      <AuthExperienceShell
        heading="Reset password"
        subtitle="Recover your account with a secure one-time reset link."
        authCard={card}
        footer={(
          <p className="text-center text-sm text-muted-foreground">
            Remembered your password?{' '}
            <Link href="/auth/sign-in" className="text-brand hover:underline">
              Sign in
            </Link>
          </p>
        )}
      />
    </AuthScreenMotion>
  );
}

