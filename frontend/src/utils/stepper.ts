// Task 98 Phase C: what each step of the Stepper shows -- the steps before
// the current one are done (check mark), the current one is highlighted,
// the rest are still to come.

export type StepState = "done" | "current" | "todo";

export function stepStates(count: number, currentIndex: number): StepState[] {
  return Array.from({ length: count }, (_, index) =>
    index < currentIndex ? "done" : index === currentIndex ? "current" : "todo",
  );
}

const STATE_WORDS: Record<StepState, string> = {
  done: "已完成",
  current: "目前步驟",
  todo: "尚未進行",
};

// The step button's accessible name: the label stays readable for a screen
// reader even where the screen hides it (narrow windows show only the
// current step's label).
export function stepAccessibleLabel(index: number, label: string, state: StepState): string {
  return `第 ${index + 1} 步：${label}（${STATE_WORDS[state]}）`;
}
