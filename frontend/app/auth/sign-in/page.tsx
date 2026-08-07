'use client';
/**
 * app/auth/sign-in/page.tsx
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { Loader2, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { buildOAuthRedirectUrl, createClient } from '@/lib/supabase/client';
import { toast } from 'sonner';
import { Suspense } from 'react';
import { AuthExperienceShell, OAuthButtons, type OAuthProvider } from '@/components/auth/AuthExperienceShell';

const REMEMBER_EMAIL_KEY = 'codebase-copilot.remember-email.v1';

type InlineErrors = { email?: string; password?: string; form?: string };

function PasswordVisibilityButton({
  showPassword,
  onToggle,
}: {
  showPassword: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
      aria-label={showPassword ? 'Hide password' : 'Show password'}
    >
      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
    </button>
  );
}

function EmailField({
  email,
  onChange,
  error,
}: {
  email: string;
  onChange: (value: string) => void;
  error?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor="email">Email</Label>
      <Input
        id="email"
        type="email"
        placeholder="you@example.com"
        value={email}
        onChange={(e) => onChange(e.target.value)}
        required
        autoComplete="email"
        aria-invalid={Boolean(error)}
        aria-describedby={error ? 'email-error' : undefined}
        className="h-11 bg-background border-border focus-visible:ring-brand"
      />
      {error ? (
        <p id="email-error" className="text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function PasswordField({
  password,
  showPassword,
  onChange,
  onToggle,
  onCapsLock,
  error,
  capsLockOn,
}: {
  password: string;
  showPassword: boolean;
  onChange: (value: string) => void;
  onToggle: () => void;
  onCapsLock: (enabled: boolean) => void;
  error?: string;
  capsLockOn: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <Label htmlFor="password">Password</Label>
        <Link
          href="/auth/forgot-password"
          className="text-xs text-muted-foreground hover:text-brand transition-colors"
        >
          Forgot password?
        </Link>
      </div>
      <div className="relative">
        <Input
          id="password"
          type={showPassword ? 'text' : 'password'}
          placeholder="••••••••"
          value={password}
          onChange={(e) => onChange(e.target.value)}
          onKeyUp={(e) => onCapsLock(e.getModifierState('CapsLock'))}
          onKeyDown={(e) => onCapsLock(e.getModifierState('CapsLock'))}
          required
          autoComplete="current-password"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? 'password-error' : capsLockOn ? 'caps-lock-hint' : undefined}
          className="h-11 bg-background border-border focus-visible:ring-brand pr-10"
        />
        <PasswordVisibilityButton showPassword={showPassword} onToggle={onToggle} />
      </div>
      {capsLockOn ? (
        <p id="caps-lock-hint" className="text-xs text-amber-500" role="status">
          Caps Lock is on.
        </p>
      ) : null}
      {error ? (
        <p id="password-error" className="text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function SubmitButton({ loading }: { loading: boolean }) {
  return (
    <Button
      type="submit"
      className="w-full bg-brand hover:bg-green-400 text-green-950 font-semibold transition-colors duration-200 cursor-pointer"
      disabled={loading}
    >
      {loading ? (
        <>
          <Loader2 size={16} className="animate-spin mr-2" />
          Signing in…
        </>
      ) : (
        'Sign in'
      )}
    </Button>
  );
}

function validateSignIn(email: string, password: string): InlineErrors {
  const errors: InlineErrors = {};
  if (!email.trim()) {
    errors.email = 'Email is required.';
  } else if (!/^\S+@\S+\.\S+$/.test(email)) {
    errors.email = 'Enter a valid email address.';
  }
  if (!password.trim()) {
    errors.password = 'Password is required.';
  }
  return errors;
}

function SignInForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get('next') ?? '/dashboard';
  const authProvider = searchParams.get('auth_provider');
  const oauthCode = searchParams.get('code');
  const supabase = useMemo(() => createClient(), []);

  const [email, setEmail] = useState(() => {
    if (typeof window === 'undefined') return '';
    try {
      return window.localStorage.getItem(REMEMBER_EMAIL_KEY) ?? '';
    } catch {
      return '';
    }
  });
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);
  const [loadingProvider, setLoadingProvider] = useState<OAuthProvider | null>(null);
  const [rememberMe, setRememberMe] = useState(() => {
    if (typeof window === 'undefined') return false;
    try {
      return Boolean(window.localStorage.getItem(REMEMBER_EMAIL_KEY));
    } catch {
      return false;
    }
  });
  const [capsLockOn, setCapsLockOn] = useState(false);
  const [errors, setErrors] = useState<InlineErrors>({});
  const formErrorRef = useRef<HTMLDivElement | null>(null);
  const [resolvingOAuthCallback, setResolvingOAuthCallback] = useState(Boolean(authProvider || oauthCode));

  useEffect(() => {
    const nextPath = next.startsWith('/') ? next : '/dashboard';

    async function redirectIfAuthenticated() {
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (user && !user.is_anonymous) {
        router.replace(nextPath);
        router.refresh();
        return;
      }

      setResolvingOAuthCallback(false);
    }

    // OAuth callbacks can land here depending on provider/site-url setup.
    if (authProvider || oauthCode) {
      void redirectIfAuthenticated();
    }

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user && !session.user.is_anonymous) {
        router.replace(nextPath);
        router.refresh();
        return;
      }

      if (authProvider || oauthCode) {
        setResolvingOAuthCallback(false);
      }
    });

    return () => subscription.unsubscribe();
  }, [authProvider, oauthCode, next, router, supabase]);


  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;

    const nextErrors = validateSignIn(email, password);
    setErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) {
      formErrorRef.current?.focus();
      return;
    }

    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    setLoading(false);

    if (error) {
      setErrors({ form: 'Unable to sign in. Check your credentials and try again.' });
      formErrorRef.current?.focus();
      toast.error('Unable to sign in.');
      return;
    }

    try {
      if (rememberMe) {
        window.localStorage.setItem(REMEMBER_EMAIL_KEY, email.trim());
      } else {
        window.localStorage.removeItem(REMEMBER_EMAIL_KEY);
      }
      sessionStorage.setItem('codebase-copilot.auth.just-signed-in', '1');
    } catch {
      // Ignore storage write failures.
    }

    router.push(next);
    router.refresh();
  }

  async function handleGuestAccess() {
    if (guestLoading) return;
    setGuestLoading(true);

    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (user) {
      const { error: signOutError } = await supabase.auth.signOut();
      if (signOutError) {
        setGuestLoading(false);
        toast.error('Unable to start a guest session right now.');
        return;
      }
    }

    const { error } = await supabase.auth.signInAnonymously();
    setGuestLoading(false);
    if (error) {
      toast.error('Guest access unavailable. Please try again.');
      return;
    }
    router.push('/dashboard');
    router.refresh();
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
          redirectTo: buildOAuthRedirectUrl(next, provider),
        },
      });
      if (error) {
        toast.error('OAuth sign-in is unavailable for this provider right now.');
      }
    } finally {
      setLoadingProvider(null);
    }
  }

  const card = resolvingOAuthCallback ? (
    <div className="rounded-2xl border border-border bg-background/60 px-4 py-8 text-center">
      <Loader2 size={20} className="mx-auto animate-spin text-brand" />
      <p className="mt-3 text-sm text-muted-foreground">Finalizing secure sign-in...</p>
    </div>
  ) : (
    <div className="space-y-5">
      <OAuthButtons loadingProvider={loadingProvider} onOAuth={handleOAuth} />

      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground">or continue with email</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      <form onSubmit={handleSignIn} className="space-y-4" noValidate>
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

        <EmailField email={email} onChange={setEmail} error={errors.email} />
        <PasswordField
          password={password}
          showPassword={showPassword}
          onChange={setPassword}
          onToggle={() => setShowPassword(!showPassword)}
          onCapsLock={setCapsLockOn}
          capsLockOn={capsLockOn}
          error={errors.password}
        />

        <div className="flex items-center justify-between gap-3 text-sm">
          <label htmlFor="remember-me" className="flex items-center gap-2 text-muted-foreground">
            <input
              id="remember-me"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="h-4 w-4 rounded border-border accent-[hsl(var(--brand))]"
            />
            Remember me
          </label>
        </div>

        <SubmitButton loading={loading} />
      </form>

      <Button
        variant="outline"
        className="w-full border-border hover:border-brand/50 hover:bg-accent transition-all duration-200 cursor-pointer"
        onClick={handleGuestAccess}
        disabled={guestLoading}
      >
        {guestLoading ? <Loader2 size={16} className="animate-spin mr-2" /> : null}
        Explore Demo Workspace
      </Button>

      <p className="text-center text-xs text-muted-foreground">
        No account required. Experience repository intelligence instantly.
      </p>
    </div>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
    >
      <AuthExperienceShell
        heading="Sign in"
        subtitle="Access your AI Engineering Workspace to chat with repositories, run reviews, and ship with confidence."
        authCard={card}
        footer={(
          <p className="text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{' '}
            <Link href="/auth/sign-up" className="text-brand hover:underline">
              Sign up
            </Link>
          </p>
        )}
      />
    </motion.div>
  );
}

export default function SignInPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-muted-foreground" />
      </div>
    }>
      <SignInForm />
    </Suspense>
  );
}
