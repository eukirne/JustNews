"use client";

import { useState } from "react";
import { CategoryFilter } from "@/components/CategoryFilter";
import { Hero } from "@/components/Hero";
import { SiteHeader } from "@/components/SiteHeader";
import { StoryCard } from "@/components/StoryCard";
import { StoryModal } from "@/components/StoryModal";
import { Story } from "@/lib/api";
import { useStories } from "@/lib/useStories";

export default function Home() {
  const [category, setCategory] = useState<string | null>(null);
  const { stories, isLoading, error, lastUpdated } = useStories(category);
  const [openStory, setOpenStory] = useState<Story | null>(null);

  const [hero, ...rest] = stories;

  return (
    <div className="min-h-full bg-stone-50">
      <SiteHeader lastUpdated={lastUpdated} />

      <main className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-8">
        <CategoryFilter active={category} onChange={setCategory} />

        {error && (
          <p className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Couldn&apos;t reach the story feed. Is the API running?
          </p>
        )}

        {!error && isLoading && stories.length === 0 && (
          <p className="text-sm text-stone-500">Loading stories…</p>
        )}

        {!error && !isLoading && stories.length === 0 && (
          <p className="text-sm text-stone-500">No stories yet for this category. Check back after the next refresh.</p>
        )}

        {hero && <Hero story={hero} onOpen={() => setOpenStory(hero)} />}

        {rest.length > 0 && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {rest.map((story) => (
              <StoryCard key={story.id} story={story} onOpen={() => setOpenStory(story)} />
            ))}
          </div>
        )}
      </main>

      <footer className="border-t border-stone-200 py-6 text-center text-xs text-stone-400">
        Stories are AI-reframed summaries of reporting from BBC, The Guardian, NPR, and other outlets. Always
        linked back to the original for full detail.
      </footer>

      {openStory && <StoryModal story={openStory} onClose={() => setOpenStory(null)} />}
    </div>
  );
}
