import { Story } from "@/lib/api";
import { useOriginalHeadline } from "@/lib/OriginalHeadlineContext";
import { CategoryTag } from "./CategoryTag";
import { SourceAttribution } from "./SourceAttribution";

export function StoryCard({ story, onOpen }: { story: Story; onOpen: () => void }) {
  const { show } = useOriginalHeadline();
  const readOriginalUrl = story.sources[0]?.url;

  return (
    <article className="flex flex-col overflow-hidden rounded-lg border border-stone-200 bg-white transition-shadow hover:shadow-md">
      <button type="button" onClick={onOpen} className="flex flex-1 cursor-pointer flex-col text-left">
        {story.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- images come from arbitrary outlet domains decided at runtime, unsuitable for next/image's static remotePatterns allowlist
          <img
            src={story.image_url}
            alt=""
            loading="lazy"
            className="h-44 w-full object-cover"
          />
        ) : (
          <div className="h-44 w-full bg-stone-100" aria-hidden="true" />
        )}

        <div className="flex flex-1 flex-col gap-2 p-4">
          <CategoryTag category={story.category} />

          <h3 className="font-serif text-lg font-semibold leading-snug text-stone-900">{story.headline}</h3>

          {show && (
            <p className="text-xs italic text-stone-500">Original headline: “{story.original_headline}”</p>
          )}

          <p className="line-clamp-2 text-sm text-stone-600">{story.summary}</p>
        </div>
      </button>

      <div className="flex flex-col gap-2 px-4 pb-4">
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
    </article>
  );
}
