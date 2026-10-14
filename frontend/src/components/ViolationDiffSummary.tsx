import type { ReactElement } from "react";
import ConflictChecklist from "./ConflictChecklist";
import type { NameLookups } from "../utils/failureDiagnostics";
import type { ViolationDiff } from "../utils/violationMerge";
import { MUTED_TEXT, SUBSECTION_TITLE } from "../styles/ui";

interface ViolationDiffSummaryProps {
  // From diffViolations() (utils/violationMerge.ts): the check before vs.
  // after one change.
  diff: ViolationDiff;
  lookups: NameLookups;
  // e.g. 「異動」 or 「換人」, as in 「這次{noun}會新增的問題」.
  changeNoun: string;
}

// Task 69 (extracted in Task 70 so the move/swap and 換教師 previews share
// it): what ONE change does to the version's problems -- the ones it adds
// (red, via ConflictChecklist), the ones it resolves (green), existing ones
// it leaves unsolved but describes differently now (「仍未解決」), and only a
// count of the rest. The full "after" check also lists every problem that
// existed before, which would hide what this change itself caused.
export default function ViolationDiffSummary({
  diff,
  lookups,
  changeNoun,
}: ViolationDiffSummaryProps): ReactElement {
  // Task 71 fix: an existing problem the change doesn't fix but that now
  // reads differently (e.g. still off its fixed slot, in another slot) is
  // listed with its new wording; the rest are only counted.
  const stillUnresolved = diff.unchanged.filter((item) => item.descriptionChanged);
  const untouchedCount = diff.unchanged.length - stillUnresolved.length;
  return (
    <>
      {diff.added.length > 0 && (
        <section aria-label={`這次${changeNoun}會新增的問題`}>
          <h3 className={`${SUBSECTION_TITLE} text-red-700`}>
            這次{changeNoun}會新增的問題（{diff.added.length} 項）
          </h3>
          <ConflictChecklist
            violations={diff.added.flatMap((item) => item.violations)}
            lookups={lookups}
          />
        </section>
      )}
      {diff.resolved.length > 0 && (
        <section aria-label={`這次${changeNoun}會解決的問題`}>
          <h3 className={`${SUBSECTION_TITLE} text-green-700`}>
            這次{changeNoun}會解決的問題（{diff.resolved.length} 項）
          </h3>
          <ul className="m-0 flex list-none flex-col gap-1 p-0">
            {diff.resolved.map((item) => (
              <li key={item.sentence} className="text-sm text-green-700">
                ✓ {item.sentence}
              </li>
            ))}
          </ul>
        </section>
      )}
      {diff.added.length === 0 && diff.resolved.length === 0 && (
        <p className="text-sm text-gray-700">這次{changeNoun}不會新增或解決任何問題。</p>
      )}
      {stillUnresolved.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-1 p-0" aria-label="仍未解決的問題">
          {stillUnresolved.map((item) => (
            <li key={item.sentence} className="text-sm text-gray-700">
              仍未解決：{item.sentence}
              {item.count > 1 && ` ×${item.count}`}
            </li>
          ))}
        </ul>
      )}
      {untouchedCount > 0 && (
        <p className={MUTED_TEXT}>另有 {untouchedCount} 項既有問題不受這次{changeNoun}影響。</p>
      )}
    </>
  );
}
