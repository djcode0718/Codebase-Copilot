import type { RetrievedFile } from "@/lib/types";

export function RetrievedFilesChip({ files }: { files?: RetrievedFile[] }) {
  if (!files?.length) {
    return null;
  }

  return (
    <details className="rounded border border-[var(--border-subtle)] p-2 text-xs">
      <summary className="cursor-pointer text-[var(--text-secondary)]">Retrieved files ({files.length})</summary>
      <ul className="mt-2 space-y-1">
        {files.map((file, index) => (
          <li key={`${file.path}-${index}`} className="flex items-center justify-between gap-2">
            <code className="truncate">{file.path}</code>
            <span className="font-mono text-[var(--text-secondary)]">{file.score.toFixed(3)}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

