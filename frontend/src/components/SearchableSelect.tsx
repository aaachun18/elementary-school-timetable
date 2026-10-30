import { useId, useState, type KeyboardEvent, type ReactElement } from "react";
import { filterOptions, selectedLabel, type SearchableOption } from "../utils/searchableSelect";
import { INPUT, SELECT_RESELECT } from "../styles/ui";

const NO_HIGHLIGHT = -1;

// One row of the open list: an option, or the none choice (value null).
interface ListRow {
  value: number | null;
  label: string;
}

// A picker for teachers and classes the user can type into: closed, it
// shows the picked label; focused, the text can be typed over and the list
// under it keeps every option whose label contains what was typed. A click
// or ↑/↓ + Enter picks one, Esc or leaving the field gives up the typing
// (the picked value stays). The list floats over what follows (absolute),
// so a table row never grows while it is open.
export default function SearchableSelect({
  value,
  options,
  onChange,
  ariaLabel,
  placeholder = "輸入文字搜尋…",
  noneLabel = null,
  disabled = false,
  invalid = false,
  className = "",
  inputClassName = INPUT,
}: {
  value: number | null;
  options: readonly SearchableOption[];
  onChange: (value: number | null) => void;
  ariaLabel: string;
  placeholder?: string;
  // The first choice, meaning "nothing picked" (不指定…); null for none.
  noneLabel?: string | null;
  disabled?: boolean;
  // An amber frame (a 停用 value to pick again, components/ChoiceSelect.tsx).
  invalid?: boolean;
  // On the wrapper -- the width, typically.
  className?: string;
  inputClassName?: string;
}): ReactElement {
  const listId = useId();
  // null: not typing -- the field shows the picked label.
  const [query, setQuery] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState(NO_HIGHLIGHT);

  const isOpen = query !== null && !disabled;
  const rows: ListRow[] = [
    ...(noneLabel !== null && (query ?? "").trim() === "" ? [{ value: null, label: noneLabel }] : []),
    ...filterOptions(options, query ?? ""),
  ];

  function close(): void {
    setQuery(null);
    setHighlighted(NO_HIGHLIGHT);
  }

  function pick(row: ListRow): void {
    close();
    if (row.value !== value) {
      onChange(row.value);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "Escape" && isOpen) {
      event.preventDefault();
      event.stopPropagation();
      close();
      return;
    }
    if (!isOpen) {
      if (event.key === "ArrowDown") {
        setQuery("");
      }
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlighted((index) => Math.min(index + 1, rows.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlighted((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      // The highlighted row, else the only one left.
      const row = rows[highlighted] ?? (rows.length === 1 ? rows[0] : undefined);
      if (row !== undefined) {
        event.preventDefault();
        pick(row);
      }
    }
  }

  return (
    <div className={`relative ${className}`}>
      <input
        value={query ?? selectedLabel(options, value, noneLabel)}
        onChange={(event) => {
          setQuery(event.target.value);
          setHighlighted(NO_HIGHLIGHT);
        }}
        onFocus={(event) => {
          setQuery("");
          // Typing replaces the shown label right away.
          event.target.select();
        }}
        // Already focused after a pick: a click opens the list again.
        onClick={() => setQuery((previous) => previous ?? "")}
        onBlur={close}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={query !== null ? selectedLabel(options, value, noneLabel) || placeholder : placeholder}
        role="combobox"
        aria-label={ariaLabel}
        aria-expanded={isOpen}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-invalid={invalid || undefined}
        autoComplete="off"
        className={`${invalid ? SELECT_RESELECT : inputClassName} w-full pr-6`}
      />
      <span aria-hidden="true" className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-500">
        ▾
      </span>
      {isOpen && (
        <ul
          id={listId}
          role="listbox"
          className="scrollbar-blue absolute left-0 z-30 mt-1 max-h-60 w-full min-w-max overflow-y-auto rounded-md border border-gray-300 bg-white py-1 text-left text-sm shadow-lg"
        >
          {rows.length === 0 && <li className="px-2 py-1 text-gray-500">找不到符合的項目</li>}
          {rows.map((row, index) => (
            <li
              key={row.value ?? "none"}
              role="option"
              aria-selected={row.value === value}
              // mousedown, not click: the input keeps its focus (a blur
              // would close the list before the click lands).
              onMouseDown={(event) => {
                event.preventDefault();
                pick(row);
              }}
              onMouseEnter={() => setHighlighted(index)}
              className={`cursor-pointer whitespace-nowrap px-2 py-1 ${
                index === highlighted ? "bg-blue-50 text-blue-900" : row.value === value ? "font-medium text-blue-800" : "text-gray-900"
              }`}
            >
              {row.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
