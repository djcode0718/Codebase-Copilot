import { Hero } from '@/components/landing/Hero';
import { FeatureSection } from '@/components/landing/FeatureSection';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Navbar placeholder */}
      <header className="absolute top-0 w-full p-6 flex justify-between items-center z-50">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-brand rounded-lg flex items-center justify-center">
            <span className="font-code font-bold text-sm text-green-950">CC</span>
          </div>
          <span className="font-heading font-semibold text-lg">Codebase Copilot</span>
        </div>
      </header>

      <main>
        <Hero />
        <FeatureSection />
      </main>

      <footer className="py-8 text-center text-sm text-muted-foreground border-t border-border mt-20">
        <p>&copy; 2026 Codebase Copilot. All rights reserved.</p>
      </footer>
    </div>
  );
}
