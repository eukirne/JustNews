"use client";

import { useEffect } from "react";
import { Story } from "@/lib/api";
import { useOriginalHeadline } from "@/lib/OriginalHeadlineContext";
import { CategoryTag } from "./CategoryTag";

export function StoryModal({ story, onClose }: { story: Story; onClose: () => void }) {
  const { show } = useOriginalHeadline();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 pt-10 sm:pt-16"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={story.headline}
        className="w-full max-w-2xl rounded-lg bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {story.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- arbitrary outlet-hosted image, see StoryCard
          <img src={story.image_url} alt="" className="h-56 w-full rounded-t-lg object-cover sm:h-72" />
        ) : (
          <div className="h-16 w-full rounded-t-lg bg-stone-100" aria-hidden="true" />
        )}

        <div className="flex flex-col gap-3 p-6">
          <div className="flex items-start justify-between gap-4">
            <CategoryTag category={story.category} />
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="shrink-0 rounded-full p-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-700"
            >
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="4" y1="4" x2="16" y2="16" />
                <line x1="16" y1="4" x2="4" y2="16" />
              </svg>
            </button>
          </div>

          <h2 className="font-serif text-2xl font-bold leading-tight text-stone-900">{story.headline}</h2>

          {show && (
            <p className="text-sm italic text-stone-500">Original headline: “{story.original_headline}”</p>
          )}

          <p className="text-base leading-relaxed text-stone-700">{story.summary}</p>

          <div className="flex flex-col gap-2 border-t border-stone-200 pt-4">
            <span className="text-xs font-semibold uppercase tracking-wide text-stone-400">Sources</span>
            <div className="flex flex-wrap gap-x-4 gap-y-1.5">
              {story.sources.map((source) => (
                <a
                  key={source.url}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-blue-800 hover:underline"
                >
                  {source.outlet} →
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
