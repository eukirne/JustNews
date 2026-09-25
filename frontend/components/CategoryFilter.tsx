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
    <nav
      className="flex gap-5 overflow-x-auto px-4 sm:px-6"
      aria-label="Filter stories by category"
    >
      {options.map((category) => {
        const isActive = category === active;
        return (
          <button
            key={category ?? "all"}
            onClick={() => onChange(category)}
            className={`shrink-0 whitespace-nowrap border-b-2 py-3 text-sm font-bold uppercase tracking-wide transition-colors ${
              isActive
                ? "border-accent text-foreground"
                : "border-transparent text-stone-400 hover:text-stone-700"
            }`}
          >
            {category ?? "All"}
          </button>
        );
      })}
    </nav>
  );
}
