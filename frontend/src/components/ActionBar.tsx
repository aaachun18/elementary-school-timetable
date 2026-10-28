import type { ReactElement, ReactNode } from "react";
import { ACTION_BAR, ACTION_BAR_GROUP } from "../styles/ui";

// Task 98 Phase C: the wizard's step buttons, in one row under the step's
// card (Task 99: no longer a sticky bar). `start` holds the
// secondary actions (上一步), `end` the primary one (下一步) with anything
// that belongs to it (why it is disabled).
export default function ActionBar({ start, end }: { start?: ReactNode; end: ReactNode }): ReactElement {
  return (
    <div className={ACTION_BAR} role="group" aria-label="步驟操作">
      <div className={ACTION_BAR_GROUP}>{start}</div>
      <div className={ACTION_BAR_GROUP}>{end}</div>
    </div>
  );
}
