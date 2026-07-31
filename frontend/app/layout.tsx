/**
 * app/layout.tsx — Root layout
 * Sets up dark mode class, IBM Plex Sans + JetBrains Mono via next/font,
 * React Query provider, Supabase session provider, and Sonner toasts.
 */
import type { Metadata } from 'next';
import { IBM_Plex_Sans, JetBrains_Mono } from 'next/font/google';
import { Toaster } from '@/components/ui/sonner';
import Providers from '@/components/Providers';
import { CommandPalette } from '@/components/layout/CommandPalette';
import AppShell from '@/components/layout/AppShell';
import './globals.css';

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700'],
  variable: '--font-body',
  display: 'swap',
});

const jetBrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-code',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'Codebase Copilot',
    template: '%s | Codebase Copilot',
  },
  description:
    'Enterprise code intelligence for grounded chat, repository insight, indexing telemetry, and evaluation workflows.',
  keywords: ['RAG', 'AI', 'code search', 'GitHub', 'LlamaIndex', 'developer tools', 'enterprise'],
  openGraph: {
    title: 'Codebase Copilot',
    description: 'Enterprise repository intelligence with grounded answers, live indexing, and performance telemetry.',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      data-scroll-behavior="smooth"
      className={`${ibmPlexSans.variable} ${jetBrainsMono.variable}`}
      suppressHydrationWarning
    >
      <body
        className="min-h-screen bg-background text-foreground antialiased"
        suppressHydrationWarning
      >
        <Providers>
          <AppShell>{children}</AppShell>
          <CommandPalette />
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
