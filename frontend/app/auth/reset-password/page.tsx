'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Loader2, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { createClient } from '@/lib/supabase/client';
import { auditPasswordResetComplete } from '@/lib/auth-api';
import { toast } from 'sonner';
import { AuthExperienceShell } from '@/components/auth/AuthExperienceShell';

export default function ResetPasswordPage() {
  const supabase = useMemo(() => createClient(), []);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;

    if (!password.trim() || password.length < 8) {
      toast.error('Use at least 8 characters for your new password.');
      return;
    }

    if (password !== confirmPassword) {
      toast.error('Passwords do not match.');
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
      toast.error('Unable to update password. Request a new reset link and try again.');
      return;
    }

    setDone(true);
  }

  const card = done ? (
    <div className="rounded-2xl border border-border bg-background/60 px-4 py-8 text-center">
      <CheckCircle2 size={20} className="mx-auto text-brand" />
      <p className="mt-3 text-sm text-muted-foreground">Your password has been updated successfully.</p>
      <Button asChild variant="outline" className="mt-4 border-border">
        <Link href="/auth/sign-in">Continue to sign in</Link>
      </Button>
    </div>
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
        {loading ? <Loader2 size={16} className="animate-spin mr-2" /> : null}
        Update password
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
    </motion.div>
  );
}

