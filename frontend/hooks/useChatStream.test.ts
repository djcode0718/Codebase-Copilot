// @vitest-environment jsdom
/**
 * hooks/useChatStream.test.ts
 * Tests for SSE parsing, token accumulation, mid-stream failure resilience,
 * and terminal state guarantees.
 */
import { describe, it, expect, vi } from 'vitest';
import {
  parseSseEvents,
  processStreamEvent,
  type StreamState,
  type StreamCallbacks,
} from './useChatStream';
import type { ChatEvent } from '@/lib/types';

describe('useChatStream SSE resilience', () => {
  it('parses standard SSE events and buffers trailing partial lines', () => {
    const raw = 'data: {"type":"token","content":"Hello"}\n\ndata: {"type":"token","content":" world"}\n\ndata: {"type":';
    const { events, rest } = parseSseEvents(raw);

    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ type: 'token', content: 'Hello' });
    expect(events[1]).toEqual({ type: 'token', content: ' world' });
    expect(rest).toBe('data: {"type":');
  });

  it('accumulates tokens correctly in stream state', () => {
    const state: StreamState = {
      fullText: '',
      receivedErrorEvent: false,
      receivedDoneEvent: false,
      errorMessage: null,
      metadata: {
        queryMode: null,
        retrievedFiles: [],
        latencyRetrievalMs: null,
        latencyLlmMs: null,
        latencyTotalMs: null,
        llmProvider: null,
        llmModel: null,
      },
    };
    const setStreamedText = vi.fn();
    const streamedTextRef = { current: '' };
    const setPendingMetadata = vi.fn();

    processStreamEvent(
      { type: 'token', content: 'First ' },
      state,
      setStreamedText,
      streamedTextRef,
      setPendingMetadata
    );
    processStreamEvent(
      { type: 'token', content: 'Second' },
      state,
      setStreamedText,
      streamedTextRef,
      setPendingMetadata
    );

    expect(state.fullText).toBe('First Second');
    expect(streamedTextRef.current).toBe('First Second');
  });

  it('preserves partial output on mid-stream error and calls onError on done', () => {
    const state: StreamState = {
      fullText: 'Partial output received before failure.',
      receivedErrorEvent: false,
      receivedDoneEvent: false,
      errorMessage: null,
      metadata: {
        queryMode: null,
        retrievedFiles: [],
        latencyRetrievalMs: null,
        latencyLlmMs: null,
        latencyTotalMs: null,
        llmProvider: null,
        llmModel: null,
      },
    };
    const setStreamedText = vi.fn();
    const streamedTextRef = { current: state.fullText };
    const setPendingMetadata = vi.fn();

    const callbacks: StreamCallbacks = {
      onTextDone: vi.fn(),
      onError: vi.fn(),
    };

    // 1. Disclaimer token emitted by backend
    processStreamEvent(
      { type: 'token', content: '\n\n[Response interrupted: Rate limit reached]' },
      state,
      setStreamedText,
      streamedTextRef,
      setPendingMetadata,
      callbacks
    );

    // 2. Error event received
    processStreamEvent(
      { type: 'error', message: 'The model provider is rate-limited right now.' },
      state,
      setStreamedText,
      streamedTextRef,
      setPendingMetadata,
      callbacks
    );

    expect(state.receivedErrorEvent).toBe(true);
    expect(state.errorMessage).toBe('The model provider is rate-limited right now.');
    // Partial output must not be wiped out
    expect(state.fullText).toContain('Partial output received before failure.');
    expect(state.fullText).toContain('[Response interrupted: Rate limit reached]');

    // 3. Done event received after error
    processStreamEvent(
      { type: 'done' },
      state,
      setStreamedText,
      streamedTextRef,
      setPendingMetadata,
      callbacks
    );

    // onTextDone must NOT be called on error
    expect(callbacks.onTextDone).not.toHaveBeenCalled();
    // onError MUST be called with message and partial content
    expect(callbacks.onError).toHaveBeenCalledWith(
      'The model provider is rate-limited right now.',
      state.fullText
    );
  });

  it('displays error directly in text if error arrives before any token', () => {
    const state: StreamState = {
      fullText: '',
      receivedErrorEvent: false,
      receivedDoneEvent: false,
      errorMessage: null,
      metadata: {
        queryMode: null,
        retrievedFiles: [],
        latencyRetrievalMs: null,
        latencyLlmMs: null,
        latencyTotalMs: null,
        llmProvider: null,
        llmModel: null,
      },
    };
    let currentText = '';
    const setStreamedText = vi.fn((update) => {
      currentText = typeof update === 'function' ? update(currentText) : update;
    });
    const streamedTextRef = { current: '' };
    const setPendingMetadata = vi.fn();

    processStreamEvent(
      { type: 'error', message: 'Quota exceeded. Please retry in a moment.' },
      state,
      setStreamedText,
      streamedTextRef,
      setPendingMetadata
    );

    expect(state.receivedErrorEvent).toBe(true);
    expect(state.errorMessage).toBe('Quota exceeded. Please retry in a moment.');
    expect(state.fullText).toBe('Quota exceeded. Please retry in a moment.');
    expect(streamedTextRef.current).toBe('Quota exceeded. Please retry in a moment.');
  });

  it('guards safely against duplicate done events', () => {
    const state: StreamState = {
      fullText: 'Complete response.',
      receivedErrorEvent: false,
      receivedDoneEvent: false,
      errorMessage: null,
      metadata: {
        queryMode: null,
        retrievedFiles: [],
        latencyRetrievalMs: null,
        latencyLlmMs: null,
        latencyTotalMs: null,
        llmProvider: null,
        llmModel: null,
      },
    };
    const setStreamedText = vi.fn();
    const streamedTextRef = { current: state.fullText };
    const setPendingMetadata = vi.fn();

    const callbacks: StreamCallbacks = {
      onTextDone: vi.fn(),
    };

    // First done event
    processStreamEvent(
      { type: 'done' },
      state,
      setStreamedText,
      streamedTextRef,
      setPendingMetadata,
      callbacks
    );
    expect(callbacks.onTextDone).toHaveBeenCalledTimes(1);

    // Duplicate done event
    processStreamEvent(
      { type: 'done' },
      state,
      setStreamedText,
      streamedTextRef,
      setPendingMetadata,
      callbacks
    );
    expect(callbacks.onTextDone).toHaveBeenCalledTimes(1);
  });
});

