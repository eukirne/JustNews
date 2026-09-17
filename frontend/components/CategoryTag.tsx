const CATEGORY_COLORS: Record<string, string> = {
  World: "bg-blue-50 text-blue-800",
  "UK/Local": "bg-indigo-50 text-indigo-800",
  Politics: "bg-stone-100 text-stone-800",
  Economy: "bg-amber-50 text-amber-800",
  Science: "bg-emerald-50 text-emerald-800",
  Health: "bg-rose-50 text-rose-800",
  Culture: "bg-purple-50 text-purple-800",
};

export function CategoryTag({ category }: { category: string }) {
  const colors = CATEGORY_COLORS[category] ?? "bg-stone-100 text-stone-800";
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${colors}`}>
      {category}
    </span>
  );
}
