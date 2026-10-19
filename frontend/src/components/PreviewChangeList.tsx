import { useId, useState, type ReactElement } from "react";
import { PREVIEW_VISIBLE_CHANGES, visibleItems } from "../utils/previewSummary";
import { PREVIEW_LIST, PREVIEW_NOTE, PREVIEW_TOGGLE } from "../styles/ui";

// Task 92A (shared since Task 93): the rows a lesson block change moves or
// places, at most PREVIEW_VISIBLE_CHANGES before 「另外 N 列」.
export default function PreviewChangeList({ lines }: { lines: string[] }): ReactElement {
  const [expanded, setExpanded] = useState(false);
  const listId = useId();
  const { shown, hiddenCount } = visibleItems(lines, PREVIEW_VISIBLE_CHANGES, expanded);
  const canCollapse = expanded && lines.length > PREVIEW_VISIBLE_CHANGES;
  return (
    <>
      <ul id={listId} className={`${PREVIEW_LIST} ${PREVIEW_NOTE}`} aria-label="會變動的課">
        {shown.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {(hiddenCount > 0 || canCollapse) && (
        <button
          type="button"
          className={PREVIEW_TOGGLE}
          aria-expanded={expanded}
          aria-controls={listId}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "收合" : `另外 ${hiddenCount} 列`}
        </button>
      )}
    </>
  );
}
