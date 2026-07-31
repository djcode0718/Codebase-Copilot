'use client';

import { MoonStar, SunMedium } from 'lucide-react';
import { useTheme } from 'next-themes';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export function ThemeToggle({
  className,
  variant = 'sidebar',
}: {
  className?: string;
  variant?: 'sidebar' | 'landing';
}) {
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

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
    >
      {isDark ? <SunMedium size={14} /> : <MoonStar size={14} />}
    </Button>
  );
}

