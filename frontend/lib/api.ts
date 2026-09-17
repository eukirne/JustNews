export type SourceLink = {
  outlet: string;
  url: string;
  title: string;
};

export type Story = {
  id: number;
  category: string;
  headline: string;
  original_headline: string;
  summary: string;
  image_url: string | null;
  sources: SourceLink[];
  published_at: string;
  updated_at: string;
};

// Trailing slash stripped so callers can safely do `${API_URL}${path}` even if
// NEXT_PUBLIC_API_URL was entered with one (a common copy-paste mistake that
// otherwise produces a double slash and a 404, e.g. "https://host//api/stories").
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

// "All" (no category selected) never includes Sports — it only shows up
// under its own tab. Keep this in sync with DEFAULT_HIDDEN_CATEGORIES in
// the backend's api.py.
export const CATEGORIES = [
  "World",
  "UK/Local",
  "Politics",
  "Economy",
  "Science",
  "Health",
  "Culture",
  "Sports",
] as const;

export async function fetcher<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) {
    throw new Error(`Request to ${path} failed with ${res.status}`);
  }
  return res.json() as Promise<T>;
}
