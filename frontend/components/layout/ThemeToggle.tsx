'use client';

import { useSyncExternalStore } from 'react';
import { MoonStar, SunMedium } from 'lucide-react';
import { useTheme } from 'next-themes';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// Stable subscribe / snapshot helpers for useSyncExternalStore
function subscribe(cb: () => void) {
  // Nothing to subscribe to — fires once after hydration
  window.addEventListener('storage', cb);
  return () => window.removeEventListener('storage', cb);
}
const getClientSnapshot = () => true;
const getServerSnapshot = () => false;

export function ThemeToggle({
  className,
  variant = 'sidebar',
}: {
  className?: string;
  variant?: 'sidebar' | 'landing';
}) {
  const { resolvedTheme, setTheme } = useTheme();
  // mounted is false on server, true on client — no setState, no hydration mismatch
  const mounted = useSyncExternalStore(subscribe, getClientSnapshot, getServerSnapshot);

  const isDark = mounted && resolvedTheme === 'dark';

  const variantClass =
    variant === 'landing'
      ? 'border-border bg-card/80 text-foreground hover:bg-muted'
      : 'border-sidebar-border bg-sidebar-accent/70 text-sidebar-foreground hover:bg-sidebar-accent';

  return (
    <Button
      type="button"
      variant="outline"
      size="icon-sm"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      className={cn(variantClass, className)}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Light theme' : 'Dark theme'}
      suppressHydrationWarning
    >
      {isDark ? <SunMedium size={14} /> : <MoonStar size={14} />}
    </Button>
  );
}

