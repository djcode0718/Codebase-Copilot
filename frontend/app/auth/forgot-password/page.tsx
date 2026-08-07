'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Loader2, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { createClient } from '@/lib/supabase/client';
import { auditPasswordResetRequest, normalizeEmail } from '@/lib/auth-api';
import { toast } from 'sonner';
import { AuthExperienceShell } from '@/components/auth/AuthExperienceShell';

export default function ForgotPasswordPage() {
  const supabase = useMemo(() => createClient(), []);
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;

    const normalizedEmail = normalizeEmail(email);
    if (!normalizedEmail || !/^\S+@\S+\.\S+$/.test(normalizedEmail)) {
      toast.error('Enter a valid email address.');
      return;
    }

    setLoading(true);

    const redirectTo = `${window.location.origin}/auth/reset-password`;
    const { error } = await supabase.auth.resetPasswordForEmail(normalizedEmail, { redirectTo });
    await auditPasswordResetRequest(normalizedEmail).catch(() => undefined);
    setLoading(false);

    if (error) {
      toast.error('Unable to start password reset right now. Please try again.');
      return;
    }

    setDone(true);
  }

  const card = done ? (
    <div className="rounded-2xl border border-border bg-background/60 px-4 py-8 text-center">
      <CheckCircle2 size={20} className="mx-auto text-brand" />
      <p className="mt-3 text-sm text-muted-foreground">
        If an account exists, password reset instructions were sent to your email.
      </p>
      <Button asChild variant="outline" className="mt-4 border-border">
        <Link href="/auth/sign-in">Back to sign in</Link>
      </Button>
    </div>
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
        {loading ? <Loader2 size={16} className="animate-spin mr-2" /> : null}
        Send reset link
      </Button>
    </form>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
    >
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
    </motion.div>
  );
}

