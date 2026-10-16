import type { ReactElement } from "react";
import {
  UNKNOWN_VIOLATION_TYPE_HEADING,
  VIOLATION_TYPE_HEADINGS,
  VIOLATION_TYPE_SUGGESTIONS,
} from "../constants/errorMessages";
import { getViolationSentence, type NameLookups } from "../utils/failureDiagnostics";
import {
  groupMergedViolationsByType,
  isWarningItem,
  mergeViolationsBySentence,
  type MergedViolation,
} from "../utils/violationMerge";
import type { ConstraintViolationDetail } from "../types/scheduler";
import {
  BADGE_NEUTRAL,
  BADGE_WARNING,
  BUTTON_SECONDARY_SM,
  MUTED_TEXT,
  SUBSECTION_TITLE,
  SUCCESS_TEXT,
} from "../styles/ui";

interface ConflictChecklistProps {
  violations: ConstraintViolationDetail[];
  // Built by the caller from data it already has -- this component never
  // fetches anything, so it can be reused wherever violations show up
  // (the timetable's 檢查衝突, and later reassign/move previews).
  lookups: NameLookups;
  emptyText?: string;
  // When given, each line gets a 「在課表中查看」 button, called with the
  // line's first violation.
  onLocate?: (violation: ConstraintViolationDetail) => void;
  // Lets the caller hide the button for a line it can't locate.
  canLocate?: (violation: ConstraintViolationDetail) => boolean;
}

// Group order: the order VIOLATION_TYPE_HEADINGS lists the types in (the
// three conflicts first, then H4-H12, then the two service-level checks).
const TYPE_ORDER = Object.keys(VIOLATION_TYPE_HEADINGS);

function headingOf(type: string): string {
  return VIOLATION_TYPE_HEADINGS[type] ?? UNKNOWN_VIOLATION_TYPE_HEADING;
}

function ConflictItem({
  item,
  onLocate,
  canLocate,
}: {
  item: MergedViolation;
  onLocate?: (violation: ConstraintViolationDetail) => void;
  canLocate?: (violation: ConstraintViolationDetail) => boolean;
}): ReactElement {
  const representative = item.violations[0];
  const suggestion = VIOLATION_TYPE_SUGGESTIONS[item.type];
  const isLocatable = canLocate === undefined || canLocate(representative);
  // Task 90: a WARNING is a lighter line with a 「警告」 badge -- a reminder,
  // not a problem with the timetable.
  const isWarning = isWarningItem(item);
  return (
    <li
      className={
        isWarning
          ? "rounded-md border border-amber-200 bg-amber-50/40 p-3"
          : "rounded-md border border-gray-200 bg-white p-3"
      }
    >
      <p className={isWarning ? "text-sm text-gray-600" : "text-sm text-gray-800"}>
        {isWarning && <span className={`${BADGE_WARNING} mr-2`}>警告</span>}
        {item.sentence}
        {item.count > 1 && (
          <span
            className={`${BADGE_NEUTRAL} ml-2`}
            title={`同一個問題被回報了 ${item.count} 次（例如衝堂的兩堂課各回報一次）`}
          >
            ×{item.count}
          </span>
        )}
      </p>
      {suggestion !== undefined && <p className={`${MUTED_TEXT} mt-1`}>建議：{suggestion}</p>}
      {onLocate !== undefined && isLocatable && (
        <button
          type="button"
          onClick={() => onLocate(representative)}
          className={`${BUTTON_SECONDARY_SM} mt-2`}
        >
          在課表中查看
        </button>
      )}
    </li>
  );
}

// Task 68: a list of Hard Constraint violations as merged Chinese sentences
// (see utils/violationMerge.ts), grouped by type. The backend's English
// message is only ever shown as getViolationSentence()'s fallback for a type
// with no Chinese template; its English suggested_action is never shown --
// VIOLATION_TYPE_SUGGESTIONS gives a Chinese one per type instead.
export default function ConflictChecklist({
  violations,
  lookups,
  emptyText = "沒有發現衝突",
  onLocate,
  canLocate,
}: ConflictChecklistProps): ReactElement {
  if (violations.length === 0) {
    return <p className={SUCCESS_TEXT}>✓ {emptyText}</p>;
  }

  const merged = mergeViolationsBySentence(violations, (violation) =>
    getViolationSentence(violation, lookups),
  );
  const groups = groupMergedViolationsByType(merged, TYPE_ORDER);

  return (
    <div className="flex flex-col gap-4">
      {groups.map((group) => (
        <section key={group.type}>
          <h3 className={SUBSECTION_TITLE}>
            {headingOf(group.type)}（{group.items.length} 項）
          </h3>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {group.items.map((item) => (
              <ConflictItem
                key={item.sentence}
                item={item}
                onLocate={onLocate}
                canLocate={canLocate}
              />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
