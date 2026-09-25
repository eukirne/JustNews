"use client";

import { useOriginalHeadline } from "@/lib/OriginalHeadlineContext";

export function SiteHeader({ lastUpdated }: { lastUpdated: Date | null }) {
  const { show, toggle } = useOriginalHeadline();

  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3 sm:px-6">
      <h1 className="font-display text-2xl font-black tracking-tight text-foreground sm:text-3xl">
        The Bright <span className="text-accent">Side</span>
      </h1>

      <div className="flex flex-col items-end gap-0.5">
        <label className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-stone-500">
          <input type="checkbox" checked={show} onChange={toggle} className="h-3.5 w-3.5 accent-accent" />
          <span className="hidden sm:inline">Show original headlines</span>
          <span className="sm:hidden">Originals</span>
        </label>
        {lastUpdated && (
          <span className="text-[11px] text-stone-400">Updated {lastUpdated.toLocaleTimeString()}</span>
        )}
      </div>
    </div>
  );
}
