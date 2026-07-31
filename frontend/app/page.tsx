import { Hero } from '@/components/landing/Hero';
import { FeatureSection } from '@/components/landing/FeatureSection';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { LandingAuthActions } from '@/components/landing/LandingAuthActions';

export default async function LandingPage() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const signedIn = Boolean(session?.user);
  const isGuest = Boolean(session?.user?.is_anonymous);
  const email = session?.user?.email ?? undefined;

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl border border-brand/20 bg-brand/10 text-brand shadow-sm shadow-black/5">
              <span className="font-code text-sm font-bold">CC</span>
            </div>
            <span className="font-heading text-lg font-semibold tracking-tight">Codebase Copilot</span>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle variant="landing" />
            <LandingAuthActions
              initialSignedIn={signedIn}
              initialIsGuest={isGuest}
              initialEmail={email}
            />
          </div>
        </div>
      </header>

      <main>
        <Hero signedIn={signedIn} />
        <FeatureSection />
      </main>

      <footer className="border-t border-border/60 py-8 text-center text-sm text-muted-foreground">
        <p>&copy; 2026 Codebase Copilot. All rights reserved.</p>
      </footer>
    </div>
  );
}
