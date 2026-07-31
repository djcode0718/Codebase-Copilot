# Codebase Copilot Frontend — Implementation Plan

## What this builds
A world-class Next.js 15 frontend for a developer RAG product. Every design decision is derived from the `ui-ux-pro-max` library and locked to the real backend API contract. Zero decorative mock data.

---

## Design System (from `ui-ux-pro-max` query results)

### Colors — "Code dark + run green"
| Token | Value | Use |
|---|---|---|
| `--bg` | `#0F172A` | Page background (slate-900) |
| `--surface` | `#1E293B` | Cards, panels (slate-800) |
| `--surface-2` | `#334155` | Elevated surfaces (slate-700) |
| `--text` | `#F8FAFC` | Primary text (slate-50) |
| `--text-muted` | `#94A3B8` | Secondary text (slate-400) |
| `--accent` | `#22C55E` | CTA, success, active (green-500) |
| `--accent-dim` | `#166534` | Accent bg tint (green-900) |
| `--border` | `#334155` | Dividers (slate-700) |
| `--error` | `#EF4444` | Error states (red-500) |
| `--warn` | `#F59E0B` | Warning (amber-500) |

**Why:** The query returned `#1E293B / #22C55E` as the primary/CTA pair for "AI developer tools" — dark slate feels premium and technical, green reads as "running/healthy/success" (git green, terminal green) — exactly right for a pipeline status UI.

### Typography
- **Heading font:** `JetBrains Mono` — precision, code, technical authority
- **Body font:** `IBM Plex Sans` — readable, modern, neutral, developer-friendly
- **Why:** The query matched "developer tools, code editors" and returned this pairing explicitly. JetBrains Mono in headings gives the product its distinctive developer aesthetic without making body text painful to read.

### Motion
- Framer Motion throughout
- All transitions: `duration: 200ms, ease: [0.4, 0, 0.2, 1]` (Material easing)
- Page transitions: fade + 8px y-slide
- List entrances: staggered 40ms delay per item
- Streaming text: cursor blink at natural typing rhythm
- Animated counters: count up from 0 on mount
- `prefers-reduced-motion`: all animations wrapped in `useReducedMotion()` check

### Spacing scale
8px base unit. `4/8/12/16/24/32/48/64/80/96px`

---

## What I'm doing differently from ChatGPT/Claude/Gemini

| Pattern | GPT/Claude approach | Codebase Copilot approach |
|---|---|---|
| AI response | Black box — just text | Every response shows retrieval mode, source files, scores, latency |
| Loading | Indeterminate spinner | Real SSE pipeline step list with elapsed time per step |
| Chat history | Simple message list | Message list + per-message inspector that expands inline |
| Evaluation | None | ML experiment dashboard with radar chart + trend line |
| Trust signals | None | Grounding badge + retrieved chunk previews with file path |

**Core UX thesis:** this system's answers are grounded. The UI makes that inspectable at every turn, without requiring the user to dig.

---

## Information Architecture

```
/ (Landing)
/auth/sign-in
/auth/sign-up
/auth/forgot-password
/dashboard              — repo list + recent chats
/repo/new               — index new repo (URL input)
/repo/[id]/indexing     — SSE pipeline progress screen
/repo/[id]              — repo overview (files, langs, tech)
/repo/[id]/chat         — chat + AI inspector
/repo/[id]/chat/[chatId]— specific chat session
/repo/[id]/eval         — evaluation dashboard
/settings               — model config, profile, API keys
```

---

## Screen-by-screen plan

### 1. Landing page
**Sections (in order):**
1. Hero: headline + animated pipeline architecture diagram + "Index a repo" CTA
2. How it works: 3-step visual (Index → Chat → Inspect)
3. AI Inspector feature highlight: live demo of retrieved chunks
4. Evaluation dashboard preview
5. Testimonials placeholder (3 cards)
6. Pricing placeholder (3 tiers)
7. Footer

**Key design decisions:**
- Hero background: animated particle/grid pattern (pure CSS, no heavy canvas)
- Headline font: JetBrains Mono at 56px — bold, code-native
- CTA button: `#22C55E` with `cursor-pointer`, `hover:bg-green-400` transition 200ms
- Pipeline architecture: SVG diagram with Framer Motion path-drawing animation on scroll

### 2. Auth screens
- Minimal centered card on dark bg
- GitHub social login placeholder
- Form: shadcn `Input`, `Button`, `Label` — all accessible
- Error states: inline, not toasts

### 3. Dashboard
**Left sidebar (240px):** repo list, pinned repos, user avatar, settings link
**Main area:**
- "Index a new repo" input at top (GitHub URL, prominent)
- Recent chats grid (3 columns)
- Activity feed

**Repo card:** name, status chip (indexing=amber pulse / ready=green / failed=red), file count, node count, last indexed date, tech stack chips

### 4. Indexing screen ⭐ (centerpiece)
**Layout:** full-page centered, max-w-2xl

**Pipeline step list** — each SSE event renders a new animated row:
```
[✓ done]  [step name]        [2.3s]   ← elapsed for that step
[▶ active] [step name]       [running…]  ← pulsing green dot
[○ pending] [step name]      —
[✗ error]  [step name]       [message]   ← red, with retry
```

Each step has an expandable "logs" chevron → terminal-styled pre block with the raw backend message.

**Live stats bar (below list):**
- Files found: animated counter
- Chunks generated: animated counter
- Nodes indexed: animated counter
- Elapsed: live clock
- Extension breakdown: colored chips (`py: 24`, `js: 8`, etc.)

**Backend SSE event mapping:**
```
step: "cloning"    → progress: 10
step: "filtering"  → progress: 20
step: "parsing"    → progress: 40
step: "embedding"  → progress: 65
step: "summary"    → progress: 90
step: "done"       → progress: 100, file_count, node_count → navigate to /repo/[id]
step: "error"      → fail in place, show retry button
```

### 5. Repository overview
- Language/extension breakdown (horizontal bar chart using CSS, no library)
- Directory tree (collapsible, shadcn Accordion)
- File count, total size, largest files table
- Tech stack detection chips (from file extensions)
- Timeline of indexing runs

### 6. Chat screen ⭐
**Layout:** 60/40 split on desktop (messages | AI Inspector). Bottom sheet on mobile.

**Message thread:**
- User message: right-aligned, slate-700 bg
- Assistant message: left-aligned, no bubble — just markdown text
- Streaming: token-by-token with a soft blinking `▌` caret
- Under each assistant message: `Retrieved in 68ms · 5 chunks · architectural mode` (always visible, no click needed)
- Collapsible chunk previews below that line
- Suggested follow-up chips (from backend suggestions endpoint)
- Actions: copy / regenerate

**AI Inspector panel (right rail):**
Per message, shows:
- Query mode badge: `CODE LOOKUP` (monospace, green) or `ARCHITECTURAL` (monospace, amber)
- Retriever path: `BM25 + Dense → RRF → ColBERT` (visual pipeline chips)
- Retrieved chunks list: file path + similarity score + preview
- Latency breakdown bar chart: retrieval / rerank / LLM / total (4 segments, horizontal)
- Token counts (from metadata event when available)

**SSE event mapping for chat:**
```
type: "token"    → append to streaming text
type: "metadata" → {query_mode, retrieved_files[], latency_retrieval_ms, latency_rerank_ms, latency_llm_ms, latency_total_ms}
type: "done"     → stop caret, enable actions
type: "error"    → show inline error with retry
```

### 7. Evaluation dashboard
**Layout:** full-width, tabs for [Overview | History | Compare]

**Overview tab:**
- Most recent run: large metric cards for Hit Rate, MRR, Faithfulness, Relevancy, Mode Accuracy
- Radar chart: 5 quality metrics on 5 axes (Recharts RadarChart)
- Latency breakdown: 4 metric cards (avg_latency_total/retrieval/rerank/llm)
- ColBERT enabled badge

**History tab:**
- Trend line chart: quality metrics over time (Recharts LineChart)
- Table of all runs with date, key metrics, download button

**Compare tab:**
- Select two runs → side-by-side diff table with delta indicators (▲/▼)

### 8. Settings
- Model/provider switcher (Groq/Ollama/Gemini/OpenAI)
- Retrieval config: top-k slider, ColBERT toggle, hybrid toggle
- Profile section
- Danger zone: delete account

### 9. Command palette (⌘K)
- shadcn `CommandDialog`
- Items: all repos, all chats, settings pages
- Recent history

---

## Component hierarchy

```
app/
├── layout.tsx              (IBM Plex Sans + JetBrains Mono, dark bg)
├── (landing)/page.tsx
├── auth/
│   ├── sign-in/page.tsx
│   └── sign-up/page.tsx
├── dashboard/
│   ├── layout.tsx          (sidebar + main)
│   └── page.tsx
├── repo/
│   ├── new/page.tsx        (URL input form)
│   ├── [id]/
│   │   ├── indexing/page.tsx
│   │   ├── page.tsx        (overview)
│   │   ├── chat/
│   │   │   ├── page.tsx    (new chat)
│   │   │   └── [chatId]/page.tsx
│   │   └── eval/page.tsx
└── settings/page.tsx

components/
├── ui/                     (shadcn primitives)
├── layout/
│   ├── Sidebar.tsx
│   ├── Navbar.tsx
│   └── CommandPalette.tsx
├── landing/
│   ├── Hero.tsx
│   ├── PipelineVisual.tsx
│   └── FeatureSection.tsx
├── indexing/
│   ├── PipelineStepList.tsx
│   ├── PipelineStep.tsx    (single step row)
│   ├── LiveStats.tsx
│   └── useIndexingStream.ts (SSE hook)
├── chat/
│   ├── MessageThread.tsx
│   ├── MessageBubble.tsx
│   ├── StreamingText.tsx
│   ├── AIInspector.tsx
│   ├── ChunkPreview.tsx
│   ├── LatencyBar.tsx
│   └── useChatStream.ts    (SSE hook)
├── eval/
│   ├── MetricCard.tsx
│   ├── QualityRadar.tsx
│   ├── LatencyMetrics.tsx
│   └── HistoryChart.tsx
└── repo/
    ├── RepoCard.tsx
    ├── StatusChip.tsx
    └── ExtensionBreakdown.tsx

lib/
├── api.ts                  (typed API client)
├── auth.ts                 (Supabase auth helpers)
├── supabase.ts             (client init)
└── types.ts                (shared TypeScript types)

hooks/
├── useRepos.ts             (React Query)
├── useChats.ts
├── useMessages.ts
└── useEval.ts
```

---

## TypeScript types (mapped to real backend fields)

```typescript
// Repo
interface Repo {
  id: string;
  name: string;
  source_url: string;
  index_name: string;
  status: 'indexing' | 'ready' | 'failed';
  file_count?: number;
  node_count?: number;
  llm_provider?: string;
  created_at: string;
}

// Indexing SSE
interface IndexingEvent {
  step: 'cloning' | 'filtering' | 'parsing' | 'embedding' | 'summary' | 'done' | 'error';
  message: string;
  progress: number; // 0-100
  file_count?: number;
  node_count?: number;
}

// Chat SSE
type ChatEvent =
  | { type: 'token'; content: string }
  | { type: 'metadata'; query_mode: 'code_lookup' | 'architectural'; retrieved_files: RetrievedFile[]; latency_retrieval_ms: number; latency_rerank_ms: number; latency_llm_ms: number; latency_total_ms: number }
  | { type: 'done' }
  | { type: 'error'; message: string }

interface RetrievedFile {
  path: string;
  score: number;
}

// Message (from DB)
interface Message {
  id: string;
  chat_id: string;
  role: 'user' | 'assistant';
  content: string;
  query_mode?: 'code_lookup' | 'architectural';
  retrieved_files?: RetrievedFile[];
  latency_ms?: number;
  created_at: string;
}

// Evaluation
interface EvalSummary {
  id: string;
  repo_id: string;
  hit_rate: number;        // 0.0-1.0
  mrr: number;             // 0.0-1.0
  avg_faithfulness: number;
  avg_relevancy: number;
  mode_accuracy: number;
  avg_latency_total: number;  // ms
  avg_latency_retrieval: number;
  avg_latency_rerank: number;
  avg_latency_llm: number;
  colbert_enabled: boolean;
  total_queries: number;
  created_at: string;
}
```

---

## Accessibility plan
- WCAG AA minimum (4.5:1 text contrast, 3:1 UI elements)
- All interactive elements: visible focus ring (`focus-visible:ring-2 ring-green-500`)
- `aria-live="polite"` on streaming text region
- `aria-busy="true"` on loading states
- Keyboard: Tab through all UI, Esc closes modals/inspector, ⌘K for command palette
- `prefers-reduced-motion`: all Framer Motion animations wrapped in `useReducedMotion()`
- `role="log"` on the indexing pipeline step list
- `alt` text on all images

---

## Responsive strategy
- Mobile-first Tailwind
- Chat: single column on mobile, AI Inspector as bottom sheet (`Sheet` from shadcn)
- Dashboard: sidebar collapses to hamburger on mobile
- Eval: tabs still work, charts scale down, metric cards stack vertically
- Breakpoints: `sm:640 md:768 lg:1024 xl:1280`

---

## Build order
1. Next.js 15 project scaffold + Tailwind + shadcn init
2. `lib/types.ts` + `lib/api.ts` + `lib/supabase.ts`
3. Auth screens (sign-in, sign-up)
4. Dashboard layout (sidebar + main)
5. Repo list + RepoCard + StatusChip
6. Repo new (URL input) → Indexing screen with SSE stream
7. Chat screen + AI Inspector
8. Repository overview page
9. Evaluation dashboard
10. Settings page
11. Landing page
12. Command palette

> [!IMPORTANT]
> The project will be created in a NEW folder called `frontend/` at the project root — completely separate from `codebase-copilot-frontend/` which will remain untouched.

---

## Open Questions

> [!NOTE]
> **Q1: New folder location** — I'll create the frontend at `/Users/sj/Documents/AI-Copilot/codebase-copilot/frontend/`. Confirm this is okay or specify another path.
>
> **Q2: Supabase env vars** — I'll need `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. The `.env` already has `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` for the backend. I'll create a separate `frontend/.env.local`.
>
> **Q3: Auth mode** — Should guests be able to try the product without signing up (guest/anonymous mode via Supabase anon auth)? The prompt mentions this. I'll implement it unless you say no.
>
> **Q4: Recharts vs another charting library** — I'll use Recharts for the eval dashboard (Radar + Line charts) as it's the most React-native option. Confirm or suggest an alternative.
