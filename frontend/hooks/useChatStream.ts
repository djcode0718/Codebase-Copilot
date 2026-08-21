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
import type { ChatContextScope } from '@/lib/chat-context';

function parseSseEvents(chunk: string, flush = false): { events: ChatEvent[]; rest: string } {
  const normalized = chunk.replace(/\r\n/g, '\n');
  const lines = normalized.split('\n');
  let rest = lines.pop() ?? '';
  const events: ChatEvent[] = [];

  if (flush && rest.trim()) {
    lines.push(rest);
    rest = '';
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line.startsWith('data:')) continue;

    const payload = line.slice(5).trimStart();
    if (!payload) continue;

    try {
      events.push(JSON.parse(payload) as ChatEvent);
    } catch (e) {
      // Skip malformed SSE payloads and keep processing the stream.
      console.debug('[useChatStream] Failed to parse SSE payload:', payload?.slice(0, 80), e);
    }
  }

  return { events, rest };
}

export interface StreamedResponse {
  content: string;
  queryMode: QueryMode | null;
  retrievedFiles: RetrievedFile[];
  latencyRetrievalMs: number | null;
  latencyLlmMs: number | null;
  latencyTotalMs: number | null;
  llmProvider?: string | null;
  llmModel?: string | null;
  suggestions?: string[];
}

interface UseChatStreamResult {
  streaming: boolean;
  streamedText: string;
  streamedTextRef: React.MutableRefObject<string>;
  pendingMetadata: Omit<StreamedResponse, 'content'> | null;
  error: string | null;
  sendMessage: (
    chatId: string,
    query: string,
    token: string,
    displayText?: string,
    isCtaFollowup?: boolean,
    contextScope?: ChatContextScope | null,
  ) => Promise<StreamedResponse | null>;
  cancelStream: () => void;
}

function processStreamEvent(
  event: ChatEvent,
  state: {
    fullText: string;
    metadata: Omit<StreamedResponse, 'content'>;
    receivedErrorEvent: boolean;
  },
  setStreamedText: React.Dispatch<React.SetStateAction<string>>,
  streamedTextRef: React.MutableRefObject<string>,
  setPendingMetadata: React.Dispatch<React.SetStateAction<Omit<StreamedResponse, 'content'> | null>>,
): { shouldStop: boolean } {
  if (event.type === 'token') {
    state.fullText += event.content;
    streamedTextRef.current += event.content;
    setStreamedText((prev) => prev + event.content);
  } else if (event.type === 'metadata') {
    console.debug('[useChatStream] metadata received, query_mode=', event.query_mode, 'files=', event.retrieved_files?.length ?? 0);
    state.metadata = {
      queryMode: event.query_mode,
      retrievedFiles: event.retrieved_files,
      latencyRetrievalMs: event.latency_retrieval_ms,
      latencyLlmMs: event.latency_llm_ms,
      latencyTotalMs: event.latency_total_ms,
      llmProvider: event.llm_provider ?? null,
      llmModel: event.llm_model ?? null,
    };
    setPendingMetadata(state.metadata);
  } else if (event.type === 'suggestions') {
    state.metadata.suggestions = event.questions;
  } else if (event.type === 'error') {
    state.receivedErrorEvent = true;
    if (!state.fullText) {
      const errMsg = event.message || 'An error occurred. Please retry.';
      state.fullText += errMsg;
      setStreamedText((prev) => prev + errMsg);
    }
  } else if (event.type === 'done') {
    console.debug('[useChatStream] done received, fullText length=', state.fullText.length);
    return { shouldStop: true };
  }
  return { shouldStop: false };
}

async function readResponseStream(
  res: Response,
  state: {
    fullText: string;
    metadata: Omit<StreamedResponse, 'content'>;
    receivedErrorEvent: boolean;
  },
  setStreamedText: React.Dispatch<React.SetStateAction<string>>,
  streamedTextRef: React.MutableRefObject<string>,
  setPendingMetadata: React.Dispatch<React.SetStateAction<Omit<StreamedResponse, 'content'> | null>>,
): Promise<void> {
  if (!res.body) throw new Error('No response body');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let shouldStop = false;

  while (!shouldStop) {
    const { done, value } = await reader.read();
    buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });

    const parsed = parseSseEvents(buffer, done);
    buffer = parsed.rest;

    for (const event of parsed.events) {
      const result = processStreamEvent(event, state, setStreamedText, streamedTextRef, setPendingMetadata);
      if (result.shouldStop) { shouldStop = true; break; }
    }

    if (done) shouldStop = true;
  }
}

export function useChatStream(): UseChatStreamResult {
  const [streaming, setStreaming] = useState(false);
  const [streamedText, setStreamedText] = useState('');
  const streamedTextRef = useRef('');        // always holds latest value (no stale closure)
  const [pendingMetadata, setPendingMetadata] = useState<Omit<StreamedResponse, 'content'> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const apiBase = getApiBaseUrl();

  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    setStreaming(false);
  }, []);

  const sendMessage = useCallback(
    async (
      chatId: string,
      query: string,
      token: string,
      displayText?: string,
      isCtaFollowup?: boolean,
      contextScope?: ChatContextScope | null,
    ): Promise<StreamedResponse | null> => {
      // Cancel any in-progress stream
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setStreaming(true);
      setStreamedText('');
      streamedTextRef.current = '';
      setPendingMetadata(null);
      setError(null);

      let fullText = '';
      let receivedErrorEvent = false;
      let metadata: Omit<StreamedResponse, 'content'> = {
        queryMode: null,
        retrievedFiles: [],
        latencyRetrievalMs: null,
        latencyLlmMs: null,
        latencyTotalMs: null,
        llmProvider: null,
        llmModel: null,
      };
      const state = { fullText, metadata, receivedErrorEvent };

      try {
        const res = await fetch(`${apiBase}/api/chat/${chatId}/message/stream`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            query,
            display_text: displayText,
            is_cta_followup: isCtaFollowup,
            context_scope: contextScope || {},
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(err.detail ?? 'Stream request failed');
        }

        await readResponseStream(res, state, setStreamedText, streamedTextRef, setPendingMetadata);

        setStreaming(false);
        return { content: state.fullText, ...state.metadata };
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          setStreaming(false);
          // Return partial content if any tokens arrived before abort.
          if (streamedTextRef.current) {
            return { content: streamedTextRef.current, ...state.metadata };
          }
          return null;
        }
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setError(msg);
        setStreaming(false);
        // Return partial content if any tokens arrived before the error.
        if (streamedTextRef.current) {
          return { content: streamedTextRef.current, ...state.metadata };
        }
        return null;
      }
    },
    [apiBase]
  );

  return { streaming, streamedText, streamedTextRef, pendingMetadata, error, sendMessage, cancelStream };
}
