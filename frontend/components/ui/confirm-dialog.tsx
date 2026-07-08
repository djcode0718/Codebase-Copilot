"use client";

import { useState } from "react";

interface ConfirmDialogProps {
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => Promise<void>;
  trigger: React.ReactNode;
}

export function ConfirmDialog({
  title,
  description,
  confirmLabel = "Confirm",
  onConfirm,
  trigger,
}: ConfirmDialogProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const confirm = async () => {
    setLoading(true);
    try {
      await onConfirm();
      setOpen(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <span onClick={() => setOpen(true)}>{trigger}</span>
      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4">
            <h4 className="text-base font-semibold">{title}</h4>
            <p className="mt-2 text-sm text-[var(--text-secondary)]">{description}</p>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="rounded-md border border-[var(--border-subtle)] px-3 py-1.5 text-sm" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void confirm()}
                disabled={loading}
                className="rounded-md bg-[var(--error)] px-3 py-1.5 text-sm text-white disabled:opacity-60"
              >
                {loading ? "Working..." : confirmLabel}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

