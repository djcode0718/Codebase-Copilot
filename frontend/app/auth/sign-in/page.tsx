'use client';
/**
 * app/auth/sign-in/page.tsx
 */
import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { Loader2, Eye, EyeOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { createClient } from '@/lib/supabase/client';
import { toast } from 'sonner';
import { Suspense } from 'react';

type AuthHandlers = {
  handleSignIn: (e: React.FormEvent) => Promise<void>;
  handleGuestAccess: () => Promise<void>;
};

function LogoHeader() {
  return (
    <div className="text-center mb-8">
      <Link href="/" className="inline-flex items-center gap-2">
        <div className="w-8 h-8 bg-brand rounded-lg flex items-center justify-center">
          <span className="font-code font-bold text-sm text-green-950">CC</span>
        </div>
        <span className="font-heading font-semibold text-lg tracking-tight">Codebase Copilot</span>
      </Link>
      <p className="text-muted-foreground text-sm mt-2">Sign in to your account</p>
    </div>
  );
}

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
}: {
  email: string;
  onChange: (value: string) => void;
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
        className="bg-background border-border focus-visible:ring-brand"
      />
    </div>
  );
}

function PasswordField({
  password,
  showPassword,
  onChange,
  onToggle,
}: {
  password: string;
  showPassword: boolean;
  onChange: (value: string) => void;
  onToggle: () => void;
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
          required
          autoComplete="current-password"
          className="bg-background border-border focus-visible:ring-brand pr-10"
        />
        <PasswordVisibilityButton showPassword={showPassword} onToggle={onToggle} />
      </div>
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


function useAuthActions(
  supabase: ReturnType<typeof createClient>,
  router: ReturnType<typeof useRouter>,
  next: string,
  email: string,
  password: string,
  setLoading: (loading: boolean) => void,
  setGuestLoading: (loading: boolean) => void,
): AuthHandlers {
  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) {
      toast.error(error.message);
    } else {
      router.push(next);
      router.refresh();
    }
  }

  async function handleGuestAccess() {
    setGuestLoading(true);
    const { error } = await supabase.auth.signInAnonymously();
    setGuestLoading(false);
    if (error) {
      toast.error('Guest access unavailable: ' + error.message);
    } else {
      router.push('/dashboard');
      router.refresh();
    }
  }

  return { handleSignIn, handleGuestAccess };
}

function SignInForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get('next') ?? '/dashboard';
  const supabase = createClient();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);

  const { handleSignIn, handleGuestAccess } = useAuthActions(
    supabase,
    router,
    next,
    email,
    password,
    setLoading,
    setGuestLoading,
  );

  const guestButton = (
    <Button
      variant="outline"
      className="w-full border-border hover:border-brand/50 hover:bg-accent transition-all duration-200 cursor-pointer"
      onClick={handleGuestAccess}
      disabled={guestLoading}
    >
      {guestLoading ? <Loader2 size={16} className="animate-spin mr-2" /> : null}
      Continue as Guest
    </Button>
  );

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      {/* Background grid */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(51,65,85,0.15)_1px,transparent_1px),linear-gradient(90deg,rgba(51,65,85,0.15)_1px,transparent_1px)] bg-[size:48px_48px] pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
        className="relative w-full max-w-sm"
      >
        {/* Logo */}
        <LogoHeader />

        {/* Card */}
        <div className="bg-card border border-border rounded-xl p-6 space-y-5">
          <form onSubmit={handleSignIn} className="space-y-4">
            <EmailField email={email} onChange={setEmail} />
            <PasswordField
              password={password}
              showPassword={showPassword}
              onChange={setPassword}
              onToggle={() => setShowPassword(!showPassword)}
            />
            <SubmitButton loading={loading} />
          </form>

          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs text-muted-foreground">or</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          {guestButton}
        </div>

        <p className="text-center text-sm text-muted-foreground mt-5">
          Don&apos;t have an account?{' '}
          <Link href="/auth/sign-up" className="text-brand hover:underline">
            Sign up
          </Link>
        </p>
      </motion.div>
    </div>
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
