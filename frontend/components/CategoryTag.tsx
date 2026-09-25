const CATEGORY_COLORS: Record<string, string> = {
  World: "text-blue-600",
  "UK/Local": "text-indigo-600",
  Politics: "text-stone-600",
  Economy: "text-amber-600",
  Science: "text-emerald-600",
  Health: "text-rose-600",
  Culture: "text-purple-600",
  Sports: "text-teal-600",
};

export function CategoryTag({ category }: { category: string }) {
  const color = CATEGORY_COLORS[category] ?? "text-stone-600";
  return (
    <span className={`text-xs font-extrabold uppercase tracking-wider ${color}`}>{category}</span>
  );
}
