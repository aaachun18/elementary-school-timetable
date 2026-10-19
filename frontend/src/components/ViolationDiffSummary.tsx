import { useId, useState, type ReactElement } from "react";
import {
  PREVIEW_VISIBLE_LINES,
  visibleItems,
  type PreviewLine,
  type PreviewLineKind,
  type PreviewSummary,
} from "../utils/previewSummary";
import {
  PREVIEW_LINE,
  PREVIEW_LINE_LIGHT,
  PREVIEW_LIST,
  PREVIEW_NOTE,
  PREVIEW_TAG_ERROR,
  PREVIEW_TAG_RESOLVED,
  PREVIEW_TAG_UNRESOLVED,
  PREVIEW_TAG_WARNING,
  PREVIEW_TOGGLE,
  PREVIEW_VERDICT_OK,
  PREVIEW_VERDICT_PROBLEM,
} from "../styles/ui";

interface ViolationDiffSummaryProps {
  // From buildPreviewSummary() (utils/previewSummary.ts): what ONE change
  // does to the version's problems.
  summary: PreviewSummary;
  // e.g. 「異動」 or 「換人」, for the list's accessible name.
  changeNoun: string;
}

const TAG_CLASS: Record<PreviewLineKind, string> = {
  error: PREVIEW_TAG_ERROR,
  warning: PREVIEW_TAG_WARNING,
  unresolved: PREVIEW_TAG_UNRESOLVED,
  resolved: PREVIEW_TAG_RESOLVED,
};

function ProblemLine({ line }: { line: PreviewLine }): ReactElement {
  // The suggestion is only in title/aria-label (fullText): the line itself
  // stays one short 「類別：說明」.
  return (
    <li
      className={line.kind === "error" ? PREVIEW_LINE : PREVIEW_LINE_LIGHT}
      title={line.fullText}
      aria-label={line.fullText}
    >
      <span className={TAG_CLASS[line.kind]}>{line.category}</span>
      <span>
        {line.text}
        {line.countLabel}
      </span>
    </li>
  );
}

// Task 69 (shared by the move/swap and 換教師 previews since Task 70; Task
// 92A: one verdict line and a short list instead of grouped cards). The
// full "after" check also lists every problem that existed before, which
// would hide what this change itself causes -- so only the difference is
// shown, and the untouched rest is counted.
export default function ViolationDiffSummary({
  summary,
  changeNoun,
}: ViolationDiffSummaryProps): ReactElement {
  const [expanded, setExpanded] = useState(false);
  const listId = useId();
  const { shown, hiddenCount } = visibleItems(summary.lines, PREVIEW_VISIBLE_LINES, expanded);
  const canCollapse = expanded && summary.lines.length > PREVIEW_VISIBLE_LINES;
  return (
    <>
      <p className={summary.verdict.tone === "ok" ? PREVIEW_VERDICT_OK : PREVIEW_VERDICT_PROBLEM}>
        {summary.verdict.text}
      </p>
      {summary.lines.length > 0 && (
        <ul id={listId} className={PREVIEW_LIST} aria-label={`這次${changeNoun}影響的問題`}>
          {shown.map((line) => (
            <ProblemLine key={line.key} line={line} />
          ))}
        </ul>
      )}
      {(hiddenCount > 0 || canCollapse) && (
        <button
          type="button"
          className={PREVIEW_TOGGLE}
          aria-expanded={expanded}
          aria-controls={listId}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "收合" : `另外 ${hiddenCount} 項`}
        </button>
      )}
      {summary.untouchedCount > 0 && (
        <p className={PREVIEW_NOTE}>
          另有 {summary.untouchedCount} 項既有問題不受這次{changeNoun}影響
        </p>
      )}
    </>
  );
}
