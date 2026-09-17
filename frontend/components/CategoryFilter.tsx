import { CATEGORIES } from "@/lib/api";

export function CategoryFilter({
  active,
  onChange,
}: {
  active: string | null;
  onChange: (category: string | null) => void;
}) {
  const options: (string | null)[] = [null, ...CATEGORIES];

  return (
    <nav className="flex flex-wrap gap-2 overflow-x-auto pb-1" aria-label="Filter stories by category">
      {options.map((category) => {
        const isActive = category === active;
        return (
          <button
            key={category ?? "all"}
            onClick={() => onChange(category)}
            className={`shrink-0 rounded-full border px-3 py-1 text-sm font-medium transition-colors ${
              isActive
                ? "border-stone-900 bg-stone-900 text-white"
                : "border-stone-300 text-stone-600 hover:border-stone-400 hover:text-stone-900"
            }`}
          >
            {category ?? "All"}
          </button>
        );
      })}
    </nav>
  );
}
