'use client';
/**
 * app/auth/sign-up/page.tsx
 */
import { useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Loader2, Eye, EyeOff, CheckCircle2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { buildOAuthRedirectUrl, createClient } from '@/lib/supabase/client';
import { normalizeEmail, preflightRegister } from '@/lib/auth-api';
import { toast } from 'sonner';
import { AuthExperienceShell, OAuthButtons, type OAuthProvider } from '@/components/auth/AuthExperienceShell';

type InlineErrors = { email?: string; password?: string; confirmPassword?: string; form?: string };

type PasswordStrength = {
  score: number;
  label: 'Weak' | 'Fair' | 'Strong' | 'Excellent';
  checks: {
    length: boolean;
    uppercase: boolean;
    number: boolean;
    symbol: boolean;
  };
};

function validateSignUp(email: string, password: string, confirmPassword: string): InlineErrors {
  const errors: InlineErrors = {};
  if (!email.trim()) {
    errors.email = 'Email is required.';
  } else if (!/^\S+@\S+\.\S+$/.test(email)) {
    errors.email = 'Enter a valid email address.';
  }
  if (!password.trim()) {
    errors.password = 'Password is required.';
  } else if (password.length < 8) {
    errors.password = 'Use at least 8 characters.';
  }
  if (!confirmPassword.trim()) {
    errors.confirmPassword = 'Please confirm your password.';
  } else if (password !== confirmPassword) {
    errors.confirmPassword = 'Passwords do not match.';
  }
  return errors;
}

function getPasswordStrength(password: string): PasswordStrength {
  const checks = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    number: /[0-9]/.test(password),
    symbol: /[^A-Za-z0-9]/.test(password),
  };
  const score = Object.values(checks).filter(Boolean).length;
  if (score <= 1) return { score, label: 'Weak', checks };
  if (score === 2) return { score, label: 'Fair', checks };
  if (score === 3) return { score, label: 'Strong', checks };
  return { score, label: 'Excellent', checks };
}

export default function SignUpPage() {
  const router = useRouter();
  const supabase = createClient();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingProvider, setLoadingProvider] = useState<OAuthProvider | null>(null);
  const [capsLockOn, setCapsLockOn] = useState(false);
  const [errors, setErrors] = useState<InlineErrors>({});
  const [done, setDone] = useState(false);
  const formErrorRef = useRef<HTMLDivElement | null>(null);
  const passwordStrength = getPasswordStrength(password);

  async function handleSignUp(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;

    const normalizedEmail = normalizeEmail(email);
    const nextErrors = validateSignUp(normalizedEmail, password, confirmPassword);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      formErrorRef.current?.focus();
      return;
    }

    setLoading(true);
    try {
      const preflight = await preflightRegister(normalizedEmail, password);
      if (!preflight.ok) {
        const providerGuidance = preflight.providers.length > 0
          ? ` Continue with ${preflight.providers.map((p) => p[0].toUpperCase() + p.slice(1)).join(', ')}.`
          : ' Please sign in using your existing account.';
        const message = `${preflight.message}${providerGuidance}`;
        setErrors({ form: message });
        formErrorRef.current?.focus();
        setLoading(false);
        return;
      }
    } catch {
      setErrors({ form: 'Unable to validate this email right now. Please try again.' });
      formErrorRef.current?.focus();
      setLoading(false);
      return;
    }

    const { error } = await supabase.auth.signUp({ email: normalizedEmail, password });
    setLoading(false);

    if (error) {
      if (/already|exists|registered/i.test(error.message)) {
        setErrors({
          form: 'This email is already registered with Codebase Copilot. Please sign in using your existing account.',
        });
      } else {
        setErrors({ form: 'Unable to create your account. Please try again.' });
      }
      formErrorRef.current?.focus();
      toast.error('Unable to create your account.');
    } else {
      setEmail(normalizedEmail);
      setDone(true);
    }
  }

  async function handleOAuth(provider: OAuthProvider) {
    if (loadingProvider || loading) return;
    setLoadingProvider(provider);
    try {
      try {
        sessionStorage.setItem('codebase-copilot.auth.just-signed-in', '1');
      } catch {
        // Ignore storage write failures.
      }
      const { error } = await supabase.auth.signInWithOAuth({
        provider,
        options: {
          redirectTo: buildOAuthRedirectUrl('/dashboard', provider),
        },
      });
      if (error) {
        toast.error('OAuth sign-up is unavailable for this provider right now.');
      }
    } finally {
      setLoadingProvider(null);
    }
  }

  if (done) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center max-w-sm"
        >
          <CheckCircle2 size={48} className="text-brand mx-auto mb-4" />
          <h2 className="font-heading text-xl font-semibold mb-2">Check your email</h2>
          <p className="text-muted-foreground text-sm">
            We sent a confirmation link to <strong className="text-foreground">{email}</strong>.
            Click it to activate your account.
          </p>
          <p className="mt-3 text-xs text-muted-foreground">
            Tip: GitHub sign-in can automatically connect to your engineering workspace profile.
          </p>
          <Button
            variant="outline"
            className="mt-6 border-border cursor-pointer"
            onClick={() => router.push('/auth/sign-in')}
          >
            Back to sign in
          </Button>
        </motion.div>
      </div>
    );
  }

  const card = (
    <div className="space-y-5">
      <OAuthButtons loadingProvider={loadingProvider} onOAuth={handleOAuth} />

      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground">or create an account with email</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      <form onSubmit={handleSignUp} className="space-y-4" noValidate>
        {errors.form ? (
          <div
            ref={formErrorRef}
            tabIndex={-1}
            role="alert"
            className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive focus:outline-none focus:ring-2 focus:ring-destructive/40"
          >
            <AlertCircle size={14} aria-hidden="true" />
            <span>{errors.form}</span>
          </div>
        ) : null}

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
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? 'email-error' : undefined}
            className="h-11 bg-background border-border focus-visible:ring-brand"
          />
          {errors.email ? (
            <p id="email-error" className="text-xs text-destructive" role="alert">
              {errors.email}
            </p>
          ) : null}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder="Min 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyUp={(e) => setCapsLockOn(e.getModifierState('CapsLock'))}
              onKeyDown={(e) => setCapsLockOn(e.getModifierState('CapsLock'))}
              required
              minLength={8}
              autoComplete="new-password"
              aria-invalid={Boolean(errors.password)}
              aria-describedby={errors.password ? 'password-error' : capsLockOn ? 'caps-lock-hint' : undefined}
              className="h-11 bg-background border-border focus-visible:ring-brand pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          {capsLockOn ? (
            <p id="caps-lock-hint" className="text-xs text-amber-500" role="status">
              Caps Lock is on.
            </p>
          ) : null}
          {errors.password ? (
            <p id="password-error" className="text-xs text-destructive" role="alert">
              {errors.password}
            </p>
          ) : null}

          <div className="rounded-xl border border-border bg-card/95 p-3.5 shadow-sm" aria-live="polite">
            <div className="mb-2 flex items-center justify-between text-xs">
              <span className="font-semibold text-foreground/85">Password strength</span>
              <span className="font-semibold text-foreground">{password ? passwordStrength.label : 'Add a password'}</span>
            </div>
            <div className="grid grid-cols-4 gap-1">
              {[0, 1, 2, 3].map((segment) => (
                <span
                  key={segment}
                  className={[
                    'h-1.5 rounded-full transition-colors duration-200',
                    password && segment < passwordStrength.score
                      ? passwordStrength.score <= 1
                        ? 'bg-red-500'
                        : passwordStrength.score === 2
                        ? 'bg-amber-500'
                        : passwordStrength.score === 3
                        ? 'bg-blue-500'
                        : 'bg-brand'
                      : 'bg-border/90',
                  ].join(' ')}
                />
              ))}
            </div>
            <div className="mt-2 grid gap-1 text-[11px] text-foreground/70 sm:grid-cols-2">
              <p className={passwordStrength.checks.length ? 'text-brand font-medium' : undefined}>- At least 8 characters</p>
              <p className={passwordStrength.checks.uppercase ? 'text-brand font-medium' : undefined}>- One uppercase letter</p>
              <p className={passwordStrength.checks.number ? 'text-brand font-medium' : undefined}>- One number</p>
              <p className={passwordStrength.checks.symbol ? 'text-brand font-medium' : undefined}>- One symbol</p>
            </div>
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="confirm-password">Confirm password</Label>
          <Input
            id="confirm-password"
            type={showPassword ? 'text' : 'password'}
            placeholder="Re-enter your password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            autoComplete="new-password"
            aria-invalid={Boolean(errors.confirmPassword)}
            aria-describedby={errors.confirmPassword ? 'confirm-password-error' : undefined}
            className="h-11 bg-background border-border focus-visible:ring-brand"
          />
          {errors.confirmPassword ? (
            <p id="confirm-password-error" className="text-xs text-destructive" role="alert">
              {errors.confirmPassword}
            </p>
          ) : null}
        </div>

        <Button
          type="submit"
          className="w-full bg-brand hover:bg-green-400 text-green-950 font-semibold transition-colors duration-200 cursor-pointer"
          disabled={loading}
        >
          {loading ? (
            <>
              <Loader2 size={16} className="animate-spin mr-2" />
              Creating account…
            </>
          ) : (
            'Create account'
          )}
        </Button>
      </form>
    </div>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
    >
      <AuthExperienceShell
        showBrand={false}
        heading="Create account"
        subtitle="Set up your AI Engineering Workspace in seconds. Minimal setup, enterprise-grade outcomes."
        authCard={card}
        footer={(
          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link href="/auth/sign-in" className="text-brand hover:underline">
              Sign in
            </Link>
          </p>
        )}
      />
    </motion.div>
  );
}
