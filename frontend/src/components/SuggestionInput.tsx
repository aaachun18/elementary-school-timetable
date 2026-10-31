import { useId, useState, type KeyboardEvent, type ReactElement } from "react";
import { INPUT } from "../styles/ui";

const NO_HIGHLIGHT = -1;

// A free-text field with a list of suggestions under it while focused --
// what <datalist> did, but drawn by the page (the browser's own datalist
// popup can't be styled to match). The list sits in the flow, not
// floating, so it never makes the surrounding dialog scroll. Typing filters
// it; a click or ↑/↓ + Enter picks one.
export default function SuggestionInput({
  value,
  suggestions,
  onChange,
  disabled = false,
  placeholder,
  ariaLabel,
}: {
  value: string;
  suggestions: readonly string[];
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  ariaLabel: string;
}): ReactElement {
  const listId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(NO_HIGHLIGHT);

  const query = value.trim().toLowerCase();
  const shown = suggestions.filter((item) => item.toLowerCase().includes(query) && item !== value);
  const isListShown = isOpen && !disabled && shown.length > 0;

  function pick(item: string): void {
    onChange(item);
    setIsOpen(false);
    setHighlighted(NO_HIGHLIGHT);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (!isListShown) {
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlighted((index) => Math.min(index + 1, shown.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlighted((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter" && shown[highlighted] !== undefined) {
      event.preventDefault();
      pick(shown[highlighted]);
    }
  }

  return (
    <div className="flex flex-col">
      <input
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
          setIsOpen(true);
          setHighlighted(NO_HIGHLIGHT);
        }}
        onFocus={() => setIsOpen(true)}
        onClick={() => setIsOpen(true)}
        onBlur={() => setIsOpen(false)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder}
        role="combobox"
        aria-label={ariaLabel}
        aria-expanded={isListShown}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        className={`${INPUT} w-full`}
      />
      {isListShown && (
        <ul
          id={listId}
          role="listbox"
          className="mt-1 max-h-40 overflow-y-auto rounded-md border border-gray-300 bg-white py-1 text-sm shadow-sm"
        >
          {shown.map((item, index) => (
            <li
              key={item}
              role="option"
              aria-selected={index === highlighted}
              // mousedown, not click: the input keeps its focus (a blur
              // would close the list before the click lands).
              onMouseDown={(event) => {
                event.preventDefault();
                pick(item);
              }}
              onMouseEnter={() => setHighlighted(index)}
              className={`cursor-pointer px-2 py-1 ${index === highlighted ? "bg-blue-50 text-blue-900" : "text-gray-900"}`}
            >
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
