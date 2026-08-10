'use client';
/**
 * components/chat/RelationshipGraphViewer.tsx
 * ─────────────────────────────────────────────
 * Interactive force-directed relationship graph modal.
 *
 * Props:
 *   repoId      — current repo (used to fetch the correct graph)
 *   token       — auth token
 *   focusSymbol — open in focus mode centred on this symbol; null = overview
 *   onClose     — called when the modal is dismissed
 *
 * Modes:
 *   Overview  (focusSymbol = null)  — top 30 hubs by reference count, max 40 nodes
 *   Focus     (focusSymbol set)     — that symbol + its direct refs (max 15 in SVG,
 *                                     remainder listed in sidebar)
 *
 * Layout: full-screen overlay → two-column (sidebar | SVG canvas)
 *
 * Colors: 100% via CSS variables — adapts to light/dark mode automatically.
 * No hardcoded color values.
 */

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import * as d3 from 'd3';
import { X, Search, GitBranch, Loader2, AlertCircle, ChevronLeft, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useGraphCache } from '@/hooks/useGraphCache';

// ── Constants ─────────────────────────────────────────────────────────────────

const OVERVIEW_MAX_HUBS = 40;
const LABEL_TRUNCATE = 28;         // max chars for labels

// ── Types ─────────────────────────────────────────────────────────────────────

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  type: 'hub' | 'leaf';
  refCount: number;
}

interface GraphLink {
  source: string;
  target: string;
}

interface Props {
  repoId: string;
  token: string;
  focusSymbol?: string | null;
  onClose: () => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function truncateLabel(s: string, max = LABEL_TRUNCATE): string {
  // For file paths, show only the basename
  const base = s.includes('/') ? s.split('/').pop()! : s;
  if (base.length <= max) return base;
  return base.slice(0, max - 1) + '…';
}

function buildOverviewGraph(
  graph: Record<string, string[]>
): { nodes: GraphNode[]; links: GraphLink[]; overflowInfo: null } {
  // Sort keys by count of referencing items descending, pick top 20 hubs
  const sorted = Object.entries(graph)
    .map(([k, refs]) => ({ id: k, count: refs.length }))
    .sort((a, b) => b.count - a.count)
    .slice(0, OVERVIEW_MAX_HUBS);

  const nodesMap = new Map<string, GraphNode>();
  const links: GraphLink[] = [];

  sorted.forEach((s) => {
    nodesMap.set(s.id, { id: s.id, type: 'hub', refCount: s.count });
    const refs = graph[s.id] ?? [];
    // Take top 4 referencing sources to keep it clean and connected
    refs.slice(0, 4).forEach((r) => {
      if (!nodesMap.has(r)) {
        nodesMap.set(r, { id: r, type: 'leaf', refCount: 0 });
      }
      links.push({ source: s.id, target: r });
    });
  });

  const nodes = Array.from(nodesMap.values());
  return { nodes, links, overflowInfo: null };
}

function buildFocusGraph(
  graph: Record<string, string[]>,
  symbol: string
): { nodes: GraphNode[]; links: GraphLink[]; overflowRefs: string[]; totalRefs: number } {
  const allRefs = graph[symbol] ?? [];

  const nodes: GraphNode[] = [
    { id: symbol, type: 'hub', refCount: allRefs.length },
    ...allRefs.map((ref): GraphNode => ({
      id: ref, type: 'leaf', refCount: 0,
    })),
  ];
  const links: GraphLink[] = allRefs.map((ref) => ({ source: symbol, target: ref }));

  return { nodes, links, overflowRefs: [], totalRefs: allRefs.length };
}

// ── Main component ────────────────────────────────────────────────────────────

export default function RelationshipGraphViewer({ repoId, token, focusSymbol: initialFocus, onClose }: Props) {
  const { fetchGraph, getGraph } = useGraphCache();

  const [rawGraph, setRawGraph] = useState<Record<string, string[]> | null>(() => getGraph(repoId));
  const [graphLoading, setGraphLoading] = useState(() => getGraph(repoId) === null);
  const [graphError, setGraphError] = useState<string | null>(null);

  const [focus, setFocus] = useState<string | null>(initialFocus ?? null);
  const [searchQuery, setSearchQuery] = useState('');

  // ── Suggested views (top 6 connected symbols) ────────────────────────────
  const suggestedSymbols = useMemo(() => {
    if (!rawGraph) return [];
    return Object.entries(rawGraph)
      .map(([name, refs]) => ({ name, count: refs.length }))
      .filter((x) => x.count > 0)
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
  }, [rawGraph]);

  // ── Reset state when repoId changes during rendering (best practice) ─────
  const [prevRepoId, setPrevRepoId] = useState(repoId);
  if (repoId !== prevRepoId) {
    setPrevRepoId(repoId);
    const cached = getGraph(repoId);
    setGraphLoading(cached === null);
    setGraphError(null);
    setRawGraph(cached);
    setFocus(initialFocus ?? null);
    setSearchQuery('');
  }


  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphLink> | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // ── Load graph data ──────────────────────────────────────────────────────
  useEffect(() => {
    if (rawGraph !== null) return;
    let cancelled = false;

    fetchGraph(token, repoId).then((g) => {
      if (!cancelled) {
        if (g === null) {
          setGraphError('Failed to load relationship graph. Check your connection and try again.');
        } else if (Object.keys(g).length === 0) {
          setRawGraph({});
        } else {
          setRawGraph(g);
        }
        setGraphLoading(false);
      }
    });

    return () => { cancelled = true; };
  }, [repoId, token, fetchGraph, rawGraph]);

  // ── Escape key ───────────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  // ── Derived search results state ─────────────────────────────────────────
  const searchResults = useMemo(() => {
    if (!searchQuery.trim() || !rawGraph) return [];
    const q = searchQuery.trim().toLowerCase();
    return Object.keys(rawGraph).filter((k) => k.toLowerCase().includes(q)).slice(0, 20);
  }, [searchQuery, rawGraph]);

  // ── Build graph data for current view ────────────────────────────────────
  const graphData = useMemo(() => {
    if (!rawGraph || Object.keys(rawGraph).length === 0) return null;
    if (focus) return buildFocusGraph(rawGraph, focus);
    return { ...buildOverviewGraph(rawGraph), overflowRefs: [], totalRefs: 0 };
  }, [rawGraph, focus]);

  // ── D3 force simulation ───────────────────────────────────────────────────
  useEffect(() => {
    if (!svgRef.current || !graphData || graphData.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth || 700;
    const height = svgRef.current.clientHeight || 500;

    // Clear previous content
    svg.selectAll('*').remove();

    // Root group for pan/zoom
    const root = svg.append('g').attr('class', 'root');

    // ── Zoom behaviour ──────────────────────────────────────────────────────
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => {
        root.attr('transform', event.transform);
      });
    svg.call(zoom);
    // Start at a sensible default scale/translate
    svg.call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(0.85));

    // ── Arrow marker (unused if we keep edges subtle, but defined for extensibility)
    svg.append('defs');

    const style = getComputedStyle(svgRef.current);
    const colMuted   = style.getPropertyValue('--muted-foreground').trim() || '#64748b';
    const colFg      = style.getPropertyValue('--foreground').trim() || '#0f172a';
    const colBg      = style.getPropertyValue('--card').trim() || '#ffffff';

    // ── Helper functions for node colors and size ───────────────────────
    const getRadius = (d: GraphNode) => {
      if (focus) {
        return d.id === focus ? 18 : 10;
      }
      return d.type === 'hub' ? Math.min(8 + d.refCount, 26) : 6;
    };

    const colBlue = '#3b82f6';
    const colGreen = '#22c55e';
    const colOrange = '#f97316';
    const colGray = colMuted;

    const getNodeColor = (d: GraphNode) => {
      if (focus) {
        if (d.id === focus) return colBlue;
        const isKey = !!rawGraph && rawGraph[d.id] && rawGraph[d.id].length > 0;
        return isKey ? colGreen : colOrange;
      }
      return d.type === 'hub' ? colBlue : colGray;
    };

    // ── Links ────────────────────────────────────────────────────────────
    const linkGroup = root.append('g').attr('class', 'links');
    const linkSel = linkGroup.selectAll<SVGLineElement, GraphLink>('line')
      .data(graphData.links)
      .join('line')
      .attr('stroke', colMuted)
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.55);

    // ── Nodes ─────────────────────────────────────────────────────────────
    const nodeGroup = root.append('g').attr('class', 'nodes');

    const nodeSel = nodeGroup.selectAll<SVGGElement, GraphNode>('g')
      .data(graphData.nodes)
      .join('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .call(
        d3.drag<SVGGElement, GraphNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x; d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null; d.fy = null;
          })
      );

    // ── Force simulation ─────────────────────────────────────────────────
    const isFocusMode = !!focus;
    const distanceVal = isFocusMode ? 120 : 90;
    const chargeVal = isFocusMode ? -260 : -140;

    const simulation = d3.forceSimulation<GraphNode, GraphLink>(graphData.nodes as GraphNode[])
      .force('link', d3.forceLink<GraphNode, GraphLink>(graphData.links)
        .id((d) => d.id)
        .distance(distanceVal)
        .strength(isFocusMode ? 0.8 : 0.5)
      )
      .force('charge', d3.forceManyBody().strength(chargeVal))
      .force('collision', d3.forceCollide<GraphNode>()
        .radius((d) => getRadius(d) + (isFocusMode ? 12 : 8))
        .strength(0.85)
      )
      .force('center', d3.forceCenter(0, 0))
      .alphaDecay(isFocusMode ? 0.02 : 0.03);

    simulationRef.current = simulation;

    // Circle
    nodeSel.append('circle')
      .attr('r', (d) => getRadius(d))
      .attr('fill', (d) => getNodeColor(d))
      .attr('stroke', colBg)
      .attr('stroke-width', (d) => (focus && d.id === focus) ? 2.5 : 1.5)
      .attr('fill-opacity', 0.85)
      .on('mouseenter', function() {
        d3.select(this).attr('fill-opacity', 1);
      })
      .on('mouseleave', function() {
        d3.select(this).attr('fill-opacity', 0.85);
      })
      .on('click', (_, d) => {
        setFocus(d.id);
      });

    // Labels
    nodeSel.append('text')
      .attr('class', 'hover-label')
      .attr('x', (d) => getRadius(d) + 5)
      .attr('dy', '0.31em')
      .attr('font-size', '10px')
      .attr('font-family', 'var(--font-code, monospace)')
      .attr('font-weight', '500')
      .attr('fill', colFg)
      .attr('stroke', colBg)
      .attr('stroke-width', '2.5px')
      .attr('paint-order', 'stroke fill')
      .attr('pointer-events', 'none')
      .style('user-select', 'none')
      .text((d) => {
        const name = truncateLabel(d.id);
        if (focus) {
          return name;
        }
        return d.type === 'hub' ? `${name} (${d.refCount})` : '';
      });

    simulation.on('tick', () => {

      linkSel
        .attr('x1', (d) => (d.source as unknown as GraphNode).x ?? 0)
        .attr('y1', (d) => (d.source as unknown as GraphNode).y ?? 0)
        .attr('x2', (d) => (d.target as unknown as GraphNode).x ?? 0)
        .attr('y2', (d) => (d.target as unknown as GraphNode).y ?? 0);

      nodeSel.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => {
      simulation.stop();
    };
  }, [graphData, rawGraph, focus]);

  // ── Handlers ─────────────────────────────────────────────────────────────
  const handleBackToOverview = useCallback(() => {
    setFocus(null);
    setSearchQuery('');
  }, []);

  const handleSelectSearchResult = useCallback((sym: string) => {
    setFocus(sym);
    setSearchQuery('');
  }, []);

  // ── Sidebar content ────────────────────────────────────────────────────
  const overflowRefs = (graphData && 'overflowRefs' in graphData) ? graphData.overflowRefs : [];
  const totalRefs = (graphData && 'totalRefs' in graphData) ? graphData.totalRefs : 0;
  const sidebarRefs = focus && rawGraph ? (rawGraph[focus] ?? []) : [];

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    /* Overlay */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'color-mix(in oklab, var(--background) 85%, transparent)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      role="dialog"
      aria-modal="true"
      aria-label="Relationship graph viewer"
    >
      {/* Modal shell */}
      <div
        className="relative flex h-[90vh] w-full max-w-6xl overflow-hidden rounded-[1.5rem] border border-border bg-card shadow-2xl shadow-black/20"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Sidebar ─────────────────────────────────────────────────── */}
        <aside className="flex w-64 flex-shrink-0 flex-col border-r border-border bg-card/90 backdrop-blur-sm">
          {/* Header */}
          <div className="border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <GitBranch size={14} className="text-brand" />
              <span className="font-heading text-sm font-semibold text-foreground">Relationship Graph</span>
              <button
                type="button"
                onClick={onClose}
                className="ml-auto rounded-lg p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground cursor-pointer"
                aria-label="Close graph viewer"
              >
                <X size={13} />
              </button>
            </div>
            {focus && (
              <button
                type="button"
                onClick={handleBackToOverview}
                className="mt-2 flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground cursor-pointer"
              >
                <ChevronLeft size={11} />
                Back to overview
              </button>
            )}
          </div>

          {/* Search */}
          <div className="border-b border-border px-3 py-2 space-y-2">
            <div className="flex items-center gap-2 rounded-xl border border-border bg-background/70 px-2.5 py-1.5">
              <Search size={12} className="text-muted-foreground flex-shrink-0" />
              <input
                ref={searchRef}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Jump to symbol…"
                className="min-w-0 flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground/60"
                aria-label="Search symbols"
              />
            </div>
            {searchResults.length > 0 && (
              <div className="max-h-40 overflow-y-auto rounded-xl border border-border bg-card shadow-lg scrollbar-thin">
                {searchResults.map((sym) => (
                  <button
                    key={sym}
                    type="button"
                    onClick={() => handleSelectSearchResult(sym)}
                    className="w-full truncate px-3 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground cursor-pointer"
                  >
                    {sym}
                  </button>
                ))}
              </div>
            )}

            {/* Overview mode switch button (always present) */}
            <button
              type="button"
              onClick={handleBackToOverview}
              className={cn(
                "w-full rounded-xl border px-3 py-1.5 text-[11px] font-medium cursor-pointer transition-all flex items-center justify-center gap-1.5",
                !focus
                  ? "bg-brand/10 border-brand/20 text-brand"
                  : "bg-background/50 border-border text-muted-foreground hover:text-foreground hover:bg-secondary/40"
              )}
            >
              <GitBranch size={11} />
              Show Overview
            </button>
          </div>

          {/* Detail panel */}
          <div className="flex-1 overflow-y-auto px-3 py-3 scrollbar-thin space-y-4">
            {focus ? (
              <div className="space-y-3">
                <div className="rounded-xl border border-brand/20 bg-brand/5 px-3 py-2">
                  <div className="font-code text-xs font-semibold text-brand break-all">{focus}</div>
                  <div className="mt-1 text-[10px] text-muted-foreground">
                    {totalRefs} reference{totalRefs !== 1 ? 's' : ''}
                    {overflowRefs.length > 0 && (
                      <span className="ml-1 text-brand">+{overflowRefs.length} more below</span>
                    )}
                  </div>
                </div>

                {sidebarRefs.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
                      All references
                    </div>
                    <div className="max-h-36 overflow-y-auto rounded-xl border border-border bg-background/30 p-1 space-y-0.5 scrollbar-thin">
                      {sidebarRefs.map((ref) => (
                        <div
                          key={ref}
                          className="truncate rounded-lg px-2 py-1 text-[10px] font-code text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors cursor-default"
                          title={ref}
                        >
                          {ref}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {sidebarRefs.length === 0 && (
                  <div className="rounded-xl border border-dashed border-border bg-background/50 p-3 text-center text-xs text-muted-foreground">
                    No references found for this symbol.
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-3.5">
                <p className="text-[10px] text-muted-foreground leading-relaxed">
                  Showing the 40 most-connected symbols and files, with their top referencing sources. Click any node to drill in.
                </p>

                {rawGraph && Object.keys(rawGraph).length > 0 && (
                  <div className="rounded-xl border border-border bg-background/50 px-3 py-2">
                    <div className="text-[10px] font-semibold text-muted-foreground">
                      Total symbols: {Object.keys(rawGraph).length.toLocaleString()}
                    </div>
                  </div>
                )}
                <div className="flex items-start gap-1.5 rounded-xl border border-border bg-background/50 px-2.5 py-2 text-[10px] text-muted-foreground">
                  <Info size={10} className="mt-0.5 flex-shrink-0" />
                  <span>Drag nodes to rearrange. Scroll to zoom. Click a hub to focus.</span>
                </div>
              </div>
            )}

            {/* Suggested views/important symbols — rendered always at the bottom */}
            {suggestedSymbols.length > 0 && (
              <div className="space-y-1.5 border-t border-border/60 pt-3">
                <div className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Suggested Views
                </div>
                <div className="space-y-1">
                  {suggestedSymbols.map((sym) => (
                    <button
                      key={sym.name}
                      type="button"
                      onClick={() => handleSelectSearchResult(sym.name)}
                      className={cn(
                        "w-full flex items-center justify-between rounded-lg border border-border px-2.5 py-1.5 text-left font-code text-[10px] transition-all cursor-pointer group",
                        focus === sym.name
                          ? "bg-brand/10 border-brand/20 text-brand"
                          : "bg-background/40 text-muted-foreground hover:bg-secondary hover:text-foreground"
                      )}
                    >
                      <span className="truncate group-hover:text-brand transition-colors">{truncateLabel(sym.name, 22)}</span>
                      <span className="flex-shrink-0 text-[9px] bg-secondary/80 px-1 py-0.5 rounded text-muted-foreground/80">{sym.count} refs</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </aside>

        {/* ── Graph canvas ──────────────────────────────────────────────── */}
        <div className="relative flex-1 bg-background/30">
          {/* Loading state */}
          {graphLoading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="flex flex-col items-center gap-3 text-muted-foreground">
                <Loader2 size={24} className="animate-spin text-brand" />
                <span className="text-sm">Loading relationship graph…</span>
              </div>
            </div>
          )}

          {/* Error state */}
          {!graphLoading && graphError && (
            <div className="absolute inset-0 flex items-center justify-center p-8">
              <div className="flex flex-col items-center gap-3 text-center">
                <AlertCircle size={24} className="text-destructive" />
                <p className="text-sm font-medium text-foreground">Failed to load graph</p>
                <p className="text-xs text-muted-foreground max-w-sm">{graphError}</p>
              </div>
            </div>
          )}

          {/* Empty graph state */}
          {!graphLoading && !graphError && rawGraph && Object.keys(rawGraph).length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center p-8">
              <div className="flex flex-col items-center gap-3 text-center">
                <GitBranch size={28} className="text-muted-foreground" />
                <p className="text-sm font-medium text-foreground">No relationship graph yet</p>
                <p className="text-xs text-muted-foreground max-w-sm">
                  This repository hasn&apos;t been indexed with the relationship graph feature.
                  Re-index the repository to generate it.
                </p>
              </div>
            </div>
          )}

          {/* Empty focus state */}
          {!graphLoading && !graphError && rawGraph && Object.keys(rawGraph).length > 0 && focus && (rawGraph[focus] ?? []).length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center p-8">
              <div className="flex flex-col items-center gap-3 text-center">
                <AlertCircle size={24} className="text-muted-foreground" />
                <p className="text-sm font-medium text-foreground">
                  No references for <code className="font-code text-brand text-xs">{focus}</code>
                </p>
                <p className="text-xs text-muted-foreground">
                  This symbol exists in the graph but has no recorded references.
                </p>
                <button
                  type="button"
                  onClick={handleBackToOverview}
                  className="mt-1 text-xs text-brand underline underline-offset-2 cursor-pointer"
                >
                  Back to overview
                </button>
              </div>
            </div>
          )}

          {/* SVG */}
          {!graphLoading && !graphError && graphData && graphData.nodes.length > 0 && (
            <svg
              ref={svgRef}
              className="h-full w-full"
              style={{ display: 'block' }}
              aria-label={focus ? `Graph for ${focus}` : 'Graph overview'}
            />
          )}



          {/* Mode chip */}
          {!graphLoading && !graphError && (
            <div className="absolute left-4 top-4 rounded-full border border-border bg-card/80 px-3 py-1 text-[10px] font-mono text-muted-foreground backdrop-blur-sm">
              {focus ? `focus: ${truncateLabel(focus, 20)}` : 'overview'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
