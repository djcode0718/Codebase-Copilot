"use client";

import { useState } from "react";

interface RepoSourceInputProps {
  disabled?: boolean;
  onSubmit: (source: string) => Promise<void>;
}

export function RepoSourceInput({ disabled, onSubmit }: RepoSourceInputProps) {
  const [source, setSource] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = source.trim();
    if (!trimmed) {
      setError("Source must not be empty.");
      return;
    }

    setError(null);
    await onSubmit(trimmed);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4">
      <label className="block text-sm font-medium">Repository source</label>
      <input
        value={source}
        onChange={(event) => setSource(event.target.value)}
        placeholder="https://github.com/owner/repo.git or C:\\repos\\project"
        className="w-full rounded-md border border-[var(--border-subtle)] bg-[var(--bg-primary)] px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
        disabled={disabled}
      />
      {error ? <p className="text-xs text-[var(--error)]">{error}</p> : null}
      <button
        type="submit"
        disabled={disabled}
        className="rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
      >
        Start indexing
      </button>
    </form>
  );
}

