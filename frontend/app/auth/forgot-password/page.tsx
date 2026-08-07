'use client';

import { useMemo, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { createClient } from '@/lib/supabase/client';
import { auditPasswordResetRequest, normalizeEmail } from '@/lib/auth-api';
import { validateEmailForRecovery, getPasswordResetRedirectUrl, showPasswordRecoveryError } from '@/lib/auth-recovery-utils';
import { AuthRecoveryFooterLink, AuthRecoveryPageFrame, AuthRecoverySubmitButton, AuthSuccessPanel } from '@/components/auth/AuthRecoveryPrimitives';

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
      <AuthRecoverySubmitButton loading={loading} idleLabel="Send reset link" />
    </form>
  );

  return (
    <AuthRecoveryPageFrame
      heading="Reset password"
      subtitle="Recover your account with a secure one-time reset link."
      authCard={card}
      footer={<AuthRecoveryFooterLink text="Remembered your password?" href="/auth/sign-in" linkLabel="Sign in" />}
    />
  );
}

