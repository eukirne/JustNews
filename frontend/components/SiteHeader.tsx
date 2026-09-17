"use client";

import { useOriginalHeadline } from "@/lib/OriginalHeadlineContext";

export function SiteHeader({ lastUpdated }: { lastUpdated: Date | null }) {
  const { show, toggle } = useOriginalHeadline();

  return (
    <header className="border-b border-stone-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-serif text-3xl font-bold tracking-tight text-stone-900 sm:text-4xl">The Bright Side</h1>
          <p className="mt-1 text-sm text-stone-500">
            Real news, honestly framed — what&apos;s true, what&apos;s serious, and what&apos;s genuinely being done about it.
          </p>
        </div>

        <div className="flex flex-col items-start gap-2 sm:items-end">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-stone-600">
            <input type="checkbox" checked={show} onChange={toggle} className="h-4 w-4 accent-stone-900" />
            Show original headlines
          </label>
          {lastUpdated && (
            <span className="text-xs text-stone-400">Updated {lastUpdated.toLocaleTimeString()}</span>
          )}
        </div>
      </div>
    </header>
  );
}
