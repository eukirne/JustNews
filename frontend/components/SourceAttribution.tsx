import { SourceLink } from "@/lib/api";

export function SourceAttribution({ sources }: { sources: SourceLink[] }) {
  if (sources.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-stone-500">
      <span>Sources:</span>
      {sources.map((source, i) => (
        <span key={source.url} className="flex items-center gap-2">
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline decoration-stone-300 underline-offset-2 hover:text-stone-800 hover:decoration-stone-500"
          >
            {source.outlet}
          </a>
          {i < sources.length - 1 && <span className="text-stone-300">·</span>}
        </span>
      ))}
    </div>
  );
}
