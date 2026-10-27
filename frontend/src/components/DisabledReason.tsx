import type { ReactElement } from "react";
import { DISABLED_REASON } from "../styles/ui";

// Task 98: the one small line next to a disabled button saying why
// (utils/disabledReason.ts decides the text). The button points at it with
// aria-describedby={id} and repeats it as its title; nothing is rendered
// when there is no reason.
export default function DisabledReason({ id, reason }: { id: string; reason: string | null }): ReactElement | null {
  if (reason === null) {
    return null;
  }
  return (
    <p id={id} className={DISABLED_REASON}>
      {reason}
    </p>
  );
}
