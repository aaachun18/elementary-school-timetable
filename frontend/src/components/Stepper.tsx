import type { ReactElement } from "react";
import { CheckIcon } from "./icons";
import { stepAccessibleLabel, stepStates } from "../utils/stepper";
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
} from "../styles/ui";

const CIRCLE_CLASSES = {
  done: STEP_CIRCLE_DONE,
  current: STEP_CIRCLE_CURRENT,
  todo: STEP_CIRCLE_TODO,
} as const;

// Task 98 Phase C: the wizard's steps in one row -- numbered circles
// joined by lines (done = check mark, current = solid primary, not yet =
// gray). Which steps can be clicked is the caller's (canJump): the wizard
// allows any step but the current one once the record exists
// (utils/wizard.ts canJumpToStep()).
export default function Stepper({
  steps,
  currentIndex,
  canJump,
  onJump,
  ariaLabel,
}: {
  steps: readonly { key: string; label: string }[];
  currentIndex: number;
  canJump: (index: number) => boolean;
  onJump: (index: number) => void;
  ariaLabel: string;
}): ReactElement {
  const states = stepStates(steps.length, currentIndex);
  return (
    <ol className={STEPPER} aria-label={ariaLabel}>
      {steps.map((step, index) => {
        const state = states[index];
        return (
          <li key={step.key} className={STEPPER_ITEM}>
            <button
              type="button"
              onClick={() => onJump(index)}
              disabled={!canJump(index)}
              aria-current={state === "current" ? "step" : undefined}
              aria-label={stepAccessibleLabel(index, step.label, state)}
              title={step.label}
              className={STEPPER_BUTTON}
            >
              <span className={CIRCLE_CLASSES[state]} aria-hidden="true">
                {state === "done" ? <CheckIcon size={14} /> : index + 1}
              </span>
              <span className={state === "current" ? STEP_LABEL_CURRENT : STEP_LABEL_OTHER}>{step.label}</span>
            </button>
            {index < steps.length - 1 && <span className={STEP_LINE} aria-hidden="true" />}
          </li>
        );
      })}
    </ol>
  );
}
