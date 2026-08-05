import { Hero } from '@/components/landing/Hero';
import { FeatureSection } from '@/components/landing/FeatureSection';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { LandingAuthActions } from '@/components/landing/LandingAuthActions';

export default async function LandingPage() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const signedIn = Boolean(user);
  const isGuest = Boolean(user?.is_anonymous);
  const email = user?.email ?? undefined;

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border/50 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3.5 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl border border-brand/25 bg-brand/10 text-brand shadow-sm">
              <span className="font-code text-sm font-bold">CC</span>
            </div>
            <div>
              <span className="font-heading text-base font-semibold tracking-tight">Codebase Copilot</span>
              <span className="ml-2 hidden rounded-full border border-brand/30 bg-brand/8 px-2 py-0.5 text-[10px] font-medium text-brand sm:inline-flex">
                v2.0
              </span>
            </div>
          </div>
          <nav className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
            <a href="#features" className="transition-colors hover:text-foreground">
              Features
            </a>
            <a href="#how-it-works" className="transition-colors hover:text-foreground">
              How it works
            </a>
            <a href="/dashboard" className="transition-colors hover:text-foreground">
              Dashboard
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle variant="landing" />
            <LandingAuthActions
              key={`${signedIn ? 'in' : 'out'}-${isGuest ? 'guest' : 'member'}-${email ?? 'none'}`}
              initialSignedIn={signedIn}
              initialIsGuest={isGuest}
              initialEmail={email}
            />
          </div>
        </div>
      </header>

      <main id="features">
        <Hero signedIn={signedIn} />
        <div id="how-it-works">
          <FeatureSection />
        </div>
      </main>

      <footer className="border-t border-border/60 bg-muted/20 py-10">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-xl border border-brand/20 bg-brand/10 text-brand">
                <span className="font-code text-[10px] font-bold">CC</span>
              </div>
              <span className="text-sm font-medium text-foreground/70">Codebase Copilot</span>
            </div>
            <p className="text-sm text-muted-foreground">
              &copy; 2026 Codebase Copilot. Enterprise Repository Intelligence Platform.
            </p>
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <a href="/dashboard" className="hover:text-foreground transition-colors">
                Dashboard
              </a>
              <a href="/auth/sign-in" className="hover:text-foreground transition-colors">
                Sign in
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
