import { Story } from "@/lib/api";
import { useOriginalHeadline } from "@/lib/OriginalHeadlineContext";
import { CategoryTag } from "./CategoryTag";
import { SourceAttribution } from "./SourceAttribution";

export function Hero({ story, onOpen }: { story: Story; onOpen: () => void }) {
  const { show } = useOriginalHeadline();
  const readOriginalUrl = story.sources[0]?.url;

  return (
    <article className="grid grid-cols-1 gap-6 border-b border-stone-200 pb-8 md:grid-cols-2 md:gap-10">
      <button type="button" onClick={onOpen} className="cursor-pointer text-left">
        {story.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- arbitrary outlet-hosted image, see StoryCard
          <img
            src={story.image_url}
            alt=""
            className="h-64 w-full rounded-lg object-cover md:h-full"
          />
        ) : (
          <div className="h-64 w-full rounded-lg bg-stone-100 md:h-full" aria-hidden="true" />
        )}
      </button>

      <div className="flex flex-col justify-center gap-3">
        <CategoryTag category={story.category} />
        <button type="button" onClick={onOpen} className="cursor-pointer text-left">
          <h1 className="font-serif text-3xl font-bold leading-tight text-stone-900 md:text-4xl">{story.headline}</h1>
        </button>

        {show && (
          <p className="text-sm italic text-stone-500">Original headline: “{story.original_headline}”</p>
        )}

        <p className="text-base leading-relaxed text-stone-700">{story.summary}</p>

        <div className="flex flex-col gap-2 pt-2">
          <SourceAttribution sources={story.sources} />
          {readOriginalUrl && (
            <a
              href={readOriginalUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-blue-800 hover:underline"
            >
              Read the original →
            </a>
          )}
        </div>
      </div>
    </article>
  );
}
