'use client';
/**
 * components/repo/IntelligenceActions.tsx
 * Pre-built intelligence queries grouped by capability.
 * Clicking a query navigates to the chat page with that prompt pre-loaded.
 */
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  Network, ShieldAlert, Code2, BookOpen, BarChart3, Layers, GitMerge,
  Users, Wrench, FlaskConical, Zap, FileSearch, Brain, ArrowRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Action {
  icon: React.ElementType;
  label: string;
  description: string;
  prompt: string;
  color: string;
}

const INTELLIGENCE_ACTIONS: Action[] = [
  {
    icon: Network,
    label: 'Architecture Map',
    description: 'System design, patterns & service relationships',
    prompt: 'Generate a comprehensive repository executive summary. Include: architecture style (monolith/microservices/etc), tech stack, service map, component relationships, data flow, and a Mermaid diagram of the architecture. Provide confidence level. Use exactly one valid Mermaid `flowchart TD` fenced block and do not mix graph syntax with participant declarations.',
    color: 'text-blue-400 bg-blue-500/10 border-blue-500/20 hover:border-blue-500/40',
  },
  {
    icon: ShieldAlert,
    label: 'Security Review',
    description: 'Auth, input validation, secrets & API risks',
    prompt: 'Perform a comprehensive security intelligence review. Analyze: authentication, authorization, input validation, secret management, token handling, API security, dependency vulnerabilities. For each finding provide: Severity (Critical/High/Medium/Low), Impact, Risk, and Recommendation with file evidence.',
    color: 'text-red-400 bg-red-500/10 border-red-500/20 hover:border-red-500/40',
  },
  {
    icon: Layers,
    label: 'Business Flows',
    description: 'Discover all business capabilities & workflows',
    prompt: 'Discover all business capabilities and workflows in this repository. For each workflow provide: Purpose, Entry Point, Services Involved, Data Sources, Events, Dependencies, Exit Point, and Business Value. Generate a workflow summary for each capability found.',
    color: 'text-amber-400 bg-amber-500/10 border-amber-500/20 hover:border-amber-500/40',
  },
  {
    icon: Code2,
    label: 'Code Quality',
    description: 'Quality score, anti-patterns & tech debt',
    prompt: 'Evaluate code quality across this repository. Assess: Maintainability, Readability, Scalability, Modularity, Performance, Reliability. Detect: Dead Code, Duplicate Logic, Large Functions, Anti-Patterns, Excessive Complexity. Generate a Quality Score (0-100) and an actionable remediation plan.',
    color: 'text-violet-400 bg-violet-500/10 border-violet-500/20 hover:border-violet-500/40',
  },
  {
    icon: Brain,
    label: 'Impact Analysis',
    description: 'Identify change risk & dependency chain',
    prompt: 'Perform a comprehensive impact analysis. Identify the most critical components where changes would have the highest blast radius. For each critical area, list: Affected Files, Affected APIs, Affected Services, Affected Tests, Risk Level (Low/Medium/High/Critical), and reasoning.',
    color: 'text-pink-400 bg-pink-500/10 border-pink-500/20 hover:border-pink-500/40',
  },
  {
    icon: FlaskConical,
    label: 'Test Intelligence',
    description: 'Coverage gaps, missing tests & edge cases',
    prompt: 'Analyze test coverage intelligence. Identify: Coverage Gaps, Untested Critical Logic, Missing Edge Cases, High Risk Untested Areas. Suggest specific missing unit tests, integration tests, and performance test scenarios with example test names and what they should verify.',
    color: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20 hover:border-cyan-500/40',
  },
  {
    icon: BookOpen,
    label: 'Onboarding Guide',
    description: 'Role-based 30-day mastery plan',
    prompt: 'Generate a comprehensive developer onboarding plan for a new Full Stack Engineer. Provide: 30-Minute Quick Understanding, 1-Day Deep Dive Plan, 1-Week Competency Plan, 30-Day Mastery Plan. Identify Critical Modules, Learning Path, Core Systems, and High Value areas to focus on.',
    color: 'text-green-400 bg-green-500/10 border-green-500/20 hover:border-green-500/40',
  },
  {
    icon: FileSearch,
    label: 'API Documentation',
    description: 'Generate enterprise-grade API docs',
    prompt: 'Generate comprehensive API documentation for all endpoints in this repository. For each endpoint provide: Path, Method, Purpose, Request Schema, Response Schema, Authentication, Error Codes, Example Usage, and Business Context. Format as structured documentation.',
    color: 'text-orange-400 bg-orange-500/10 border-orange-500/20 hover:border-orange-500/40',
  },
  {
    icon: GitMerge,
    label: 'Dependency Graph',
    description: 'Module dependencies & coupling analysis',
    prompt: 'Analyze all module and service dependencies. Generate a dependency map showing: External Libraries, Internal Module Coupling, Circular Dependencies, High-Fan-Out Modules, Critical Path Dependencies. Create a Mermaid dependency graph. Identify risky or outdated dependencies.',
    color: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20 hover:border-indigo-500/40',
  },
  {
    icon: BarChart3,
    label: 'Engineering Report',
    description: 'Executive summary for engineering managers',
    prompt: 'Generate an Engineering Manager Report. Include: Executive Summary, Repository Health Assessment, Technical Debt Report, Risk Assessment, Ownership Insights, Dependency Risks, Productivity Hotspots, Refactoring Opportunities. Provide both Technical View and Business View.',
    color: 'text-teal-400 bg-teal-500/10 border-teal-500/20 hover:border-teal-500/40',
  },
  {
    icon: Wrench,
    label: 'Tech Debt Scan',
    description: 'Identify & prioritize technical debt',
    prompt: 'Identify all technical debt in this repository. Categorize by: Type (Design Debt, Code Debt, Test Debt, Documentation Debt, Infrastructure Debt), Severity (Critical/High/Medium/Low), Estimated Effort to Fix, Business Impact. Generate a prioritized remediation roadmap.',
    color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20 hover:border-yellow-500/40',
  },
  {
    icon: Users,
    label: 'Digital Twin',
    description: 'Living architecture model of the repository',
    prompt: 'Build a Repository Digital Twin model that combines Repository Chat, Architecture Intelligence, Knowledge Graph reasoning, Business Flow Discovery, Code Validation, Live Visualization, and Conversation Export. Map all: Services, Modules, APIs, Databases, External Integrations, and Event Flows. Include one valid Mermaid `flowchart TD` diagram with confidence level and evidence references.',
    color: 'text-lime-400 bg-lime-500/10 border-lime-500/20 hover:border-lime-500/40',
  },
];

interface IntelligenceActionsProps {
  repoId: string;
  disabled?: boolean;
}

export default function IntelligenceActions({ repoId, disabled }: IntelligenceActionsProps) {
  const router = useRouter();

  function handleAction(prompt: string) {
    if (disabled) return;
    // Store the prompt in sessionStorage so the chat page can pick it up
    sessionStorage.setItem(`codebase:preload-prompt:${repoId}`, prompt);
    router.push(`/repo/${repoId}/chat`);
  }

  return (
    <div className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 backdrop-blur-sm">
      <div className="mb-4 flex items-center gap-2">
        <Zap size={15} className="text-brand" />
        <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Intelligence Actions
        </h2>
        {disabled && (
          <span className="ml-auto text-xs text-muted-foreground bg-muted/60 px-2 py-0.5 rounded-full">
            Available after indexing
          </span>
        )}
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {INTELLIGENCE_ACTIONS.map((action, i) => (
          <motion.button
            key={action.label}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.03 }}
            onClick={() => handleAction(action.prompt)}
            disabled={disabled}
            className={cn(
              'group flex items-start gap-3 rounded-2xl border p-3.5 text-left transition-all duration-150',
              disabled
                ? 'opacity-50 cursor-not-allowed border-border bg-background/40'
                : cn('cursor-pointer', action.color)
            )}
          >
            <div className={cn('mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-xl border', disabled ? 'border-border bg-muted/40 text-muted-foreground' : action.color)}>
              <action.icon size={13} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-1">
                <p className="text-sm font-medium">{action.label}</p>
                {!disabled && <ArrowRight size={12} className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />}
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">{action.description}</p>
            </div>
          </motion.button>
        ))}
      </div>
    </div>
  );
}
