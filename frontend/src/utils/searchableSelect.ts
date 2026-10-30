// The filtering behind components/SearchableSelect.tsx: a teacher / class
// picker the user can type into -- every option whose label contains what
// was typed. Pure, no React.

export interface SearchableOption {
  value: number;
  label: string;
}

// Case-insensitive "contains", spaces around the query ignored; an empty
// query keeps every option.
export function filterOptions<T extends SearchableOption>(options: readonly T[], query: string): T[] {
  const needle = query.trim().toLowerCase();
  if (needle === "") {
    return [...options];
  }
  return options.filter((option) => option.label.toLowerCase().includes(needle));
}

// What the closed picker shows: the picked option's label, else the
// none choice's label (when there is one), else nothing.
export function selectedLabel(
  options: readonly SearchableOption[],
  value: number | null,
  noneLabel: string | null,
): string {
  if (value === null) {
    return noneLabel ?? "";
  }
  return options.find((option) => option.value === value)?.label ?? "";
}
