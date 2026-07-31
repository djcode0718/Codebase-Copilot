'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronRight, Home } from 'lucide-react';
import { cn } from '@/lib/utils';

type Crumb = {
  label: string;
  href?: string;
};

const LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  settings: 'Settings',
  repo: 'Repository',
  chat: 'Chat',
  eval: 'Evaluation',
  indexing: 'Indexing',
  auth: 'Authentication',
  'sign-in': 'Sign in',
  'sign-up': 'Sign up',
};

function titleCase(value: string) {
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function buildCrumbs(pathname: string): Crumb[] {
  const segments = pathname.split('/').filter(Boolean);
  if (segments.length === 0) return [];

  if (segments[0] === 'dashboard') {
    return [{ label: 'Dashboard', href: '/dashboard' }];
  }

  if (segments[0] === 'settings') {
    return [
      { label: 'Dashboard', href: '/dashboard' },
      { label: 'Settings' },
    ];
  }

  if (segments[0] === 'repo') {
    const repoId = segments[1];
    const crumbs: Crumb[] = [
      { label: 'Dashboard', href: '/dashboard' },
      { label: 'Repository', href: repoId ? `/repo/${repoId}` : '/dashboard' },
    ];

    for (const segment of segments.slice(2)) {
      crumbs.push({ label: LABELS[segment] ?? titleCase(segment) });
    }

    return crumbs;
  }

  return segments.map((segment, index) => ({
    label: LABELS[segment] ?? titleCase(segment),
    href: index < segments.length - 1 ? `/${segments.slice(0, index + 1).join('/')}` : undefined,
  }));
}

export default function Breadcrumbs() {
  const pathname = usePathname();
  const crumbs = buildCrumbs(pathname);

  if (crumbs.length === 0) {
    return null;
  }

  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
        <li className="flex items-center gap-1.5">
          <Home size={12} className="shrink-0 text-brand" />
          <Link href="/dashboard" className="font-medium text-foreground/80 transition-colors hover:text-foreground">
            Workspace
          </Link>
        </li>
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <li key={`${crumb.label}-${index}`} className="flex min-w-0 items-center gap-1.5">
              <ChevronRight size={12} className="shrink-0 text-muted-foreground/70" />
              {crumb.href && !isLast ? (
                <Link
                  href={crumb.href}
                  className={cn(
                    'truncate rounded-full border border-transparent px-2 py-0.5 transition-colors hover:border-border hover:bg-card hover:text-foreground',
                    index === crumbs.length - 1 ? 'font-medium text-foreground' : ''
                  )}
                >
                  {crumb.label}
                </Link>
              ) : (
                <span
                  className={cn(
                    'truncate rounded-full px-2 py-0.5',
                    isLast ? 'font-medium text-foreground' : 'text-muted-foreground'
                  )}
                  aria-current={isLast ? 'page' : undefined}
                >
                  {crumb.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

