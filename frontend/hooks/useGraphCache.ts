'use client';
/**
 * hooks/useGraphCache.ts
 * ──────────────────────
 * Module-level cache for relationship graph data, keyed by repoId.
 *
 * Cache persists for the lifetime of the browser session (page reload clears it).
 * This prevents redundant fetches when the user opens/closes the graph modal multiple
 * times or when MessageBubble checks hover eligibility.
 *
 * Three separate slots per repo:
 *   keys      — Set<string> of symbol names (from /relationship-graph/keys)
 *   graph     — full adjacency dict   (from /relationship-graph)
 *   keysStatus — 'loading' | 'available' | 'no_graph' | 'error'
 */

import { useCallback, useRef } from 'react';
import { getRelationshipGraph, getRelationshipGraphKeys, ApiNotFoundError } from '@/lib/api';
import type { GraphAvailability } from '@/lib/types';

interface CacheEntry {
  keys: Set<string> | null;
  keysStatus: GraphAvailability;
  graph: Record<string, string[]> | null;
  graphLoading: boolean;
}

// ── Module-level cache (shared across all hook instances) ─────────────────
const _cache = new Map<string, CacheEntry>();
// In-flight promises to prevent duplicate concurrent fetches for the same repo
const _keysInFlight = new Map<string, Promise<void>>();
const _graphInFlight = new Map<string, Promise<void>>();

function getEntry(repoId: string): CacheEntry {
  if (!_cache.has(repoId)) {
    _cache.set(repoId, { keys: null, keysStatus: 'loading', graph: null, graphLoading: false });
  }
  return _cache.get(repoId)!;
}

// ── Public hook ───────────────────────────────────────────────────────────

export interface UseGraphCacheReturn {
  /**
   * Fetch the lightweight key list for a repo.
   * Idempotent — safe to call multiple times; subsequent calls are no-ops if
   * the data is already cached or a fetch is already in flight.
   *
   * @returns the resolved GraphAvailability status
   */
  fetchKeys: (token: string, repoId: string) => Promise<GraphAvailability>;

  /**
   * Fetch the full graph for a repo.
   * Idempotent — safe to call multiple times.
   *
   * @returns the adjacency dict, or null on error
   */
  fetchGraph: (token: string, repoId: string) => Promise<Record<string, string[]> | null>;

  /**
   * Synchronous check — does the cached key set contain this symbol?
   * Returns false if keys haven't been fetched yet (safe for hover checks).
   */
  hasKey: (repoId: string, symbol: string) => boolean;

  /**
   * Current graph availability status for a repo.
   */
  getAvailability: (repoId: string) => GraphAvailability;

  /**
   * Cached full graph, or null if not yet fetched.
   */
  getGraph: (repoId: string) => Record<string, string[]> | null;

  /** True if the full graph is currently being fetched. */
  isGraphLoading: (repoId: string) => boolean;
}

export function useGraphCache(): UseGraphCacheReturn {
  // We use a ref trick to force re-renders when cache updates happen
  // (callers that need reactive updates should manage their own state).
  const _dummy = useRef(0); // not used for rendering, just structural

  const fetchKeys = useCallback(async (token: string, repoId: string): Promise<GraphAvailability> => {
    const entry = getEntry(repoId);

    // Already resolved — return immediately
    if (entry.keysStatus !== 'loading') {
      return entry.keysStatus;
    }

    // Already in flight — wait for it
    if (_keysInFlight.has(repoId)) {
      await _keysInFlight.get(repoId)!;
      return getEntry(repoId).keysStatus;
    }

    // Start a new fetch
    const promise = (async () => {
      try {
        const data = await getRelationshipGraphKeys(token, repoId);
        const entry = getEntry(repoId);
        entry.keys = new Set(data.keys);
        // An empty graph (indexed before the relationship-graph feature existed) is
        // effectively the same as no_graph — button should stay disabled.
        entry.keysStatus = data.keys.length > 0 ? 'available' : 'no_graph';
      } catch (err) {
        const entry = getEntry(repoId);
        if (err instanceof ApiNotFoundError) {
          entry.keysStatus = 'no_graph';
          entry.keys = new Set(); // empty but valid
        } else {
          // Network error, auth error, or unexpected server error
          entry.keysStatus = 'error';
          entry.keys = null;
        }
      } finally {
        _keysInFlight.delete(repoId);
      }
    })();

    _keysInFlight.set(repoId, promise);
    await promise;
    return getEntry(repoId).keysStatus;
  }, []);

  const fetchGraph = useCallback(async (token: string, repoId: string): Promise<Record<string, string[]> | null> => {
    const entry = getEntry(repoId);

    // Already cached
    if (entry.graph !== null) return entry.graph;

    // Already in flight
    if (_graphInFlight.has(repoId)) {
      await _graphInFlight.get(repoId)!;
      return getEntry(repoId).graph;
    }

    getEntry(repoId).graphLoading = true;

    const promise = (async () => {
      try {
        const data = await getRelationshipGraph(token, repoId);
        const entry = getEntry(repoId);
        entry.graph = data.graph;
        // If keys weren't fetched yet, populate them from the full graph too
        if (entry.keys === null) {
          entry.keys = new Set(Object.keys(data.graph));
          entry.keysStatus = 'available';
        }
      } catch (err) {
        const entry = getEntry(repoId);
        if (err instanceof ApiNotFoundError) {
          entry.graph = {};
          if (entry.keysStatus === 'loading') {
            entry.keysStatus = 'no_graph';
            entry.keys = new Set();
          }
        } else {
          entry.graph = null;
          if (entry.keysStatus === 'loading') {
            entry.keysStatus = 'error';
          }
        }
      } finally {
        getEntry(repoId).graphLoading = false;
        _graphInFlight.delete(repoId);
      }
    })();

    _graphInFlight.set(repoId, promise);
    await promise;
    return getEntry(repoId).graph;
  }, []);

  const hasKey = useCallback((repoId: string, symbol: string): boolean => {
    const entry = _cache.get(repoId);
    if (!entry || !entry.keys) return false;
    return entry.keys.has(symbol);
  }, []);

  const getAvailability = useCallback((repoId: string): GraphAvailability => {
    return _cache.get(repoId)?.keysStatus ?? 'loading';
  }, []);

  const getGraph = useCallback((repoId: string): Record<string, string[]> | null => {
    return _cache.get(repoId)?.graph ?? null;
  }, []);

  const isGraphLoading = useCallback((repoId: string): boolean => {
    return _cache.get(repoId)?.graphLoading ?? false;
  }, []);

  void _dummy;
  return { fetchKeys, fetchGraph, hasKey, getAvailability, getGraph, isGraphLoading };
}

/** Reset cache for a specific repo (e.g. after re-indexing). */
export function invalidateGraphCache(repoId: string): void {
  _cache.delete(repoId);
}
