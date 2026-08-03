'use client';
/**
 * hooks/useChatStream.ts
 * Streams POST /api/chat/{chatId}/message/stream
 * Handles token accumulation, metadata parsing, and stream cleanup.
 * Verified against chat_service.py SSE event shapes.
 */
import { useState, useRef, useCallback } from 'react';
import { getApiBaseUrl } from '@/lib/api';
import type { ChatEvent, RetrievedFile, QueryMode } from '@/lib/types';

export interface StreamedResponse {
  content: string;
  queryMode: QueryMode | null;
  retrievedFiles: RetrievedFile[];
  latencyRetrievalMs: number | null;
  latencyLlmMs: number | null;
  latencyTotalMs: number | null;
  suggestions?: string[];
}

interface UseChatStreamResult {
  streaming: boolean;
  streamedText: string;
  pendingMetadata: Omit<StreamedResponse, 'content'> | null;
  error: string | null;
  sendMessage: (chatId: string, query: string, token: string) => Promise<StreamedResponse | null>;
  cancelStream: () => void;
}

export function useChatStream(): UseChatStreamResult {
  const [streaming, setStreaming] = useState(false);
  const [streamedText, setStreamedText] = useState('');
  const [pendingMetadata, setPendingMetadata] = useState<Omit<StreamedResponse, 'content'> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const apiBase = getApiBaseUrl();

  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    setStreaming(false);
  }, []);

  const sendMessage = useCallback(
    async (chatId: string, query: string, token: string): Promise<StreamedResponse | null> => {
      // Cancel any in-progress stream
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setStreaming(true);
      setStreamedText('');
      setPendingMetadata(null);
      setError(null);

      let fullText = '';
      let metadata: Omit<StreamedResponse, 'content'> = {
        queryMode: null,
        retrievedFiles: [],
        latencyRetrievalMs: null,
        latencyLlmMs: null,
        latencyTotalMs: null,
      };

      try {
        const res = await fetch(`${apiBase}/api/chat/${chatId}/message/stream`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ query }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(err.detail ?? 'Stream request failed');
        }

        if (!res.body) throw new Error('No response body');

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data: ')) continue;

            let event: ChatEvent;
            try {
              event = JSON.parse(trimmed.slice(6));
            } catch {
              continue;
            }

            if (event.type === 'token') {
              fullText += event.content;
              setStreamedText((prev) => prev + event.content);
            } else if (event.type === 'metadata') {
              metadata = {
                queryMode: event.query_mode,
                retrievedFiles: event.retrieved_files,
                latencyRetrievalMs: event.latency_retrieval_ms,
                latencyLlmMs: event.latency_llm_ms,
                latencyTotalMs: event.latency_total_ms,
              };
              setPendingMetadata(metadata);
            } else if (event.type === 'suggestions') {
              metadata.suggestions = event.questions;
            } else if (event.type === 'error') {
              throw new Error(event.message);
            } else if (event.type === 'done') {
              break;
            }
          }
        }

        setStreaming(false);
        return { content: fullText, ...metadata };
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          setStreaming(false);
          return null;
        }
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setError(msg);
        setStreaming(false);
        return null;
      }
    },
    [apiBase]
  );

  return { streaming, streamedText, pendingMetadata, error, sendMessage, cancelStream };
}
