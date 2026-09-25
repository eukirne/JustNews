import { Story } from "@/lib/api";
import { useOriginalHeadline } from "@/lib/OriginalHeadlineContext";
import { CategoryTag } from "./CategoryTag";
import { SourceAttribution } from "./SourceAttribution";
import { Timestamp } from "./Timestamp";

export function StoryCard({ story, onOpen }: { story: Story; onOpen: () => void }) {
  const { show } = useOriginalHeadline();
  const readOriginalUrl = story.sources[0]?.url;

  return (
    <article className="flex flex-col gap-3 border-b border-stone-200 pb-6 sm:border-none sm:pb-0">
      <button type="button" onClick={onOpen} className="flex cursor-pointer flex-col gap-3 text-left">
        {story.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- images come from arbitrary outlet domains decided at runtime, unsuitable for next/image's static remotePatterns allowlist
          <img
            src={story.image_url}
            alt=""
            loading="lazy"
            className="aspect-video w-full rounded-xl object-cover"
          />
        ) : (
          <div className="aspect-video w-full rounded-xl bg-stone-100" aria-hidden="true" />
        )}

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <CategoryTag category={story.category} />
            <span className="text-stone-300">·</span>
            <Timestamp publishedAt={story.published_at} className="text-xs font-medium text-stone-500" />
          </div>

          <h3 className="font-display text-xl font-extrabold leading-[1.1] tracking-tight text-foreground">
            {story.headline}
          </h3>

          {show && (
            <p className="text-xs italic text-stone-500">Original headline: “{story.original_headline}”</p>
          )}

          <p className="line-clamp-2 text-sm leading-snug text-stone-600">{story.summary}</p>
        </div>
      </button>

      <div className="flex flex-col gap-1.5">
        <SourceAttribution sources={story.sources} />
        {readOriginalUrl && (
          <a
            href={readOriginalUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-bold text-accent-dark hover:underline"
          >
            Read the original →
          </a>
        )}
      </div>
    </article>
  );
}
