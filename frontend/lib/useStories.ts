"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetcher, Story } from "./api";

const REFRESH_MS = 3 * 60 * 1000; // auto-refresh every 3 minutes, no full page reload

export function useStories(category: string | null) {
  const path = category ? `/api/stories?limit=50&category=${encodeURIComponent(category)}` : "/api/stories?limit=50";

  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const { data, error, isLoading } = useSWR<Story[]>(path, fetcher, {
    refreshInterval: REFRESH_MS,
    revalidateOnFocus: true,
    keepPreviousData: true,
    onSuccess: () => setLastUpdated(new Date()),
  });

  return {
    stories: data ?? [],
    isLoading,
    error,
    lastUpdated,
  };
}
