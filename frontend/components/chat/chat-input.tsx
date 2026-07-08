"use client";

import { useState } from "react";

export function ChatInput({
  disabled,
  onSend,
  initialValue,
}: {
  disabled?: boolean;
  onSend: (text: string) => Promise<void>;
  initialValue?: string;
}) {
  const [value, setValue] = useState(initialValue ?? "");

  const send = async () => {
    const text = value.trim();
    if (!text) {
      return;
    }
    setValue("");
    await onSend(text);
  };

  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-3">
      <textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Ask about this codebase..."
        rows={3}
        className="w-full resize-y rounded-md border border-[var(--border-subtle)] bg-[var(--bg-primary)] p-2 text-sm outline-none focus:border-[var(--accent)]"
        disabled={disabled}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void send();
          }
        }}
      />
      <div className="mt-2 flex justify-end">
        <button
          type="button"
          disabled={disabled}
          onClick={() => void send()}
          className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
        >
          Send
        </button>
      </div>
    </div>
  );
}
