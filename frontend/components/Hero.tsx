import { Story } from "@/lib/api";
import { useOriginalHeadline } from "@/lib/OriginalHeadlineContext";
import { CategoryTag } from "./CategoryTag";
import { SourceAttribution } from "./SourceAttribution";
import { Timestamp } from "./Timestamp";

export function Hero({ story, onOpen }: { story: Story; onOpen: () => void }) {
  const { show } = useOriginalHeadline();
  const readOriginalUrl = story.sources[0]?.url;

  return (
    <article className="flex flex-col gap-4 border-b border-stone-200 pb-8">
      <button type="button" onClick={onOpen} className="cursor-pointer text-left">
        {story.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- arbitrary outlet-hosted image, see StoryCard
          <img
            src={story.image_url}
            alt=""
            className="aspect-[16/10] w-full rounded-xl object-cover sm:aspect-[21/9]"
          />
        ) : (
          <div className="aspect-[16/10] w-full rounded-xl bg-stone-100 sm:aspect-[21/9]" aria-hidden="true" />
        )}
      </button>

      <div className="flex flex-col gap-2.5">
        <div className="flex items-center gap-2">
          <CategoryTag category={story.category} />
          <span className="text-stone-300">·</span>
          <Timestamp publishedAt={story.published_at} className="text-xs font-medium text-stone-500" />
        </div>

        <button type="button" onClick={onOpen} className="cursor-pointer text-left">
          <h1 className="font-display text-3xl font-black leading-[1.05] tracking-tight text-foreground sm:text-4xl md:text-5xl">
            {story.headline}
          </h1>
        </button>

        {show && (
          <p className="text-sm italic text-stone-500">Original headline: “{story.original_headline}”</p>
        )}

        <p className="max-w-2xl text-base leading-relaxed text-stone-700">{story.summary}</p>

        <div className="flex flex-col gap-2 pt-1">
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
      </div>
    </article>
  );
}
