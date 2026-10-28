import type { ReactElement } from "react";
import { CheckIcon } from "./icons";
import { stepAccessibleLabel, stepStates } from "../utils/stepper";
import { LOCKED_STEP_HINT, type NavItemState } from "../utils/wizardNav";
import {
  STEP_CIRCLE_CURRENT,
  STEP_CIRCLE_DONE,
  STEP_CIRCLE_TODO,
  STEP_LABEL_CURRENT,
  STEP_LABEL_OTHER,
  STEP_LINE,
  STEPPER,
  STEPPER_BUTTON,
  STEPPER_ITEM,
  STEPPER_ITEM_LOCKED,
  STEPPER_ITEM_STATIC,
} from "../styles/ui";

const CIRCLE_CLASSES = {
  done: STEP_CIRCLE_DONE,
  current: STEP_CIRCLE_CURRENT,
  todo: STEP_CIRCLE_TODO,
} as const;

// Task 98 Phase C: the wizard's steps in one row -- numbered circles
// joined by lines (done = check mark, current = solid primary, not yet =
// gray). Task 102: which ones respond is the caller's (itemState,
// utils/wizardNav.ts): only "back" steps are buttons; the current, a
// locked (later) and a read-only step are plain, unfocusable items -- a
// locked one says why on hover.
export default function Stepper({
  steps,
  currentIndex,
  itemState,
  onJump,
  ariaLabel,
}: {
  steps: readonly { key: string; label: string }[];
  currentIndex: number;
  itemState: (index: number) => NavItemState;
  onJump: (index: number) => void;
  ariaLabel: string;
}): ReactElement {
  const states = stepStates(steps.length, currentIndex);
  return (
    <ol className={STEPPER} aria-label={ariaLabel}>
      {steps.map((step, index) => {
        const state = states[index];
        const navState = itemState(index);
        const content = (
          <>
            <span className={CIRCLE_CLASSES[state]} aria-hidden="true">
              {state === "done" ? <CheckIcon size={14} /> : index + 1}
            </span>
            <span className={state === "current" ? STEP_LABEL_CURRENT : STEP_LABEL_OTHER}>{step.label}</span>
          </>
        );
        return (
          <li key={step.key} className={STEPPER_ITEM}>
            {navState === "back" ? (
              <button
                type="button"
                onClick={() => onJump(index)}
                aria-label={stepAccessibleLabel(index, step.label, state)}
                title={step.label}
                className={STEPPER_BUTTON}
              >
                {content}
              </button>
            ) : (
              <span
                aria-current={state === "current" ? "step" : undefined}
                aria-disabled={navState === "current" ? undefined : "true"}
                aria-label={stepAccessibleLabel(index, step.label, state)}
                title={navState === "locked" ? LOCKED_STEP_HINT : step.label}
                className={navState === "locked" ? STEPPER_ITEM_LOCKED : STEPPER_ITEM_STATIC}
              >
                {content}
              </span>
            )}
            {index < steps.length - 1 && <span className={STEP_LINE} aria-hidden="true" />}
          </li>
        );
      })}
    </ol>
  );
}
